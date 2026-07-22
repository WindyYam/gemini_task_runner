"""
Local recorder/transcriber used to replace RealtimeSTT dependency.
Provides the subset of the old interface used by this project.

Important behavior:
- During auto listen, we launch async transcribe when silence starts.
- If silence reaches post_speech_silence_duration, we can return an already
  computed result quickly (matching the original overlap idea).
"""

import logging
import threading
import time
import collections
import queue
from typing import Callable, Optional

import numpy as np
import pyaudio
import torch

INT16_MAX_ABS_VALUE = 32768.0


class FasterAudioRecorder:
    def __init__(
        self,
        spinner=False,
        model="medium",
        language="",
        silero_sensitivity=0.3,
        silero_use_onnx=True,
        webrtc_sensitivity=1,
        post_speech_silence_duration=0.4,
        min_length_of_recording=0.5,
        min_gap_between_recordings=0,
        compute_type="default",
        input_device_index=None,
        on_recording_start=None,
        sample_rate=16000,
        chunk_size=512,
        **kwargs,
    ):
        del spinner, silero_use_onnx, webrtc_sensitivity, min_gap_between_recordings, kwargs

        self.model_name = model
        self.language = language or None
        self.compute_type = "auto" if compute_type == "default" else compute_type
        self.input_device_index = input_device_index
        self.on_recording_start = on_recording_start

        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.post_speech_silence_duration = post_speech_silence_duration
        self.min_length_of_recording = min_length_of_recording
        self.pre_roll_duration = 0.25
        self.start_speech_frames = 2

        self.silero_sensitivity = silero_sensitivity
        self.silero_off_sensitivity = silero_sensitivity

        self.recording_judger: Callable[[], bool] = lambda: True

        self.audio = np.array([], dtype=np.float32)
        self.frames = []

        self.is_recording = False
        self._manual_mode = False

        self._record_stop_event = threading.Event()
        self._record_thread: Optional[threading.Thread] = None

        self._state = "inactive"
        self.last_transcription_bytes = None

        self._pyaudio = pyaudio.PyAudio()
        self._stream = self._pyaudio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.input_device_index,
            frames_per_buffer=self.chunk_size,
        )

        self._whisper_model = None
        self._silero_vad_model = None
        self._silero_enabled = False
        self._load_silero_vad_model()

        # Async transcribe pipeline for overlap behavior.
        self._transcribe_jobs = queue.Queue()
        self._transcribe_results = {}
        self._transcribe_lock = threading.Lock()
        self._transcribe_cv = threading.Condition(self._transcribe_lock)
        self._transcribe_stop = threading.Event()
        self._transcribe_thread = threading.Thread(target=self._transcribe_worker, daemon=True)
        self._transcribe_thread.start()

        # Warm up model eagerly so first utterance does not pay model init cost.
        self._warmup_thread = threading.Thread(target=self._warmup_transcriber, daemon=True)
        self._warmup_thread.start()

        self._job_id = 0
        self._session_id = 0
        self._latest_preview = {}
        self._current_final_job_id = None
        self._current_session_id = None
        self._prefetched_text = None
        self._latest_requested_job_id = None

    def _set_state(self, state: str):
        self._state = state

    @staticmethod
    def _preprocess_output(text: str) -> str:
        return (text or "").strip()

    def _energy(self, pcm_bytes: bytes) -> float:
        pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
        if pcm.size == 0:
            return 0.0
        return float(np.sqrt(np.mean((pcm.astype(np.float32) / INT16_MAX_ABS_VALUE) ** 2)))

    def _speech_threshold(self) -> float:
        return max(0.003, 0.015 * (1.0 - float(self.silero_sensitivity)))

    def _silence_threshold(self) -> float:
        return max(0.0025, 0.012 * (1.0 - float(self.silero_off_sensitivity)))

    def _load_silero_vad_model(self):
        try:
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                trust_repo=True,
                onnx=False,
            )
            self._silero_vad_model = model
            self._silero_enabled = True
        except Exception as exc:
            logging.warning(f"silero VAD unavailable, falling back to energy VAD: {exc}")
            self._silero_vad_model = None
            self._silero_enabled = False

    def _silero_voice_probability(self, pcm_bytes: bytes) -> Optional[float]:
        if not self._silero_enabled or self._silero_vad_model is None:
            return None

        audio_chunk = np.frombuffer(pcm_bytes, dtype=np.int16)
        if audio_chunk.size == 0:
            return 0.0

        # Silero VAD expects fixed frame sizes:
        # - 512 samples for 16kHz
        # - 256 samples for 8kHz
        frame_size = 512 if self.sample_rate == 16000 else 256

        audio_f32 = audio_chunk.astype(np.float32) / INT16_MAX_ABS_VALUE
        probs = []
        for start in range(0, audio_f32.size, frame_size):
            frame = audio_f32[start:start + frame_size]
            if frame.size < frame_size:
                frame = np.pad(frame, (0, frame_size - frame.size), mode="constant")

            tensor = torch.from_numpy(frame)
            with torch.no_grad():
                probs.append(float(self._silero_vad_model(tensor, self.sample_rate).item()))

        if not probs:
            return 0.0
        return max(probs)

    def _is_voice_active(self, pcm_bytes: bytes) -> bool:
        vad_prob = self._silero_voice_probability(pcm_bytes)
        if vad_prob is not None:
            return vad_prob >= self.silero_sensitivity
        return self._energy(pcm_bytes) >= self._speech_threshold()

    def _is_voice_inactive(self, pcm_bytes: bytes) -> bool:
        vad_prob = self._silero_voice_probability(pcm_bytes)
        if vad_prob is not None:
            return vad_prob < (1.0 - self.silero_off_sensitivity)
        return self._energy(pcm_bytes) < self._silence_threshold()

    def _finalize_frames(self, frames):
        if not frames:
            self.audio = np.array([], dtype=np.float32)
            return
        audio_i16 = np.frombuffer(b"".join(frames), dtype=np.int16)
        self.audio = (audio_i16.astype(np.float32) / INT16_MAX_ABS_VALUE).copy()

    def _manual_record_worker(self):
        local_frames = []
        while not self._record_stop_event.is_set():
            if not self.recording_judger():
                time.sleep(0.01)
                continue
            data = self._stream.read(self.chunk_size, exception_on_overflow=False)
            local_frames.append(data)

        self.frames = local_frames
        self._finalize_frames(local_frames)
        self.is_recording = False
        self._set_state("inactive")

    def start(self):
        if self.is_recording:
            return
        if not self.recording_judger():
            return

        self._manual_mode = True
        self.frames = []
        self.audio = np.array([], dtype=np.float32)
        self._record_stop_event.clear()
        self.is_recording = True
        self._set_state("recording")

        if self.on_recording_start:
            try:
                self.on_recording_start()
            except Exception as exc:
                logging.warning(f"on_recording_start failed: {exc}")

        self._record_thread = threading.Thread(target=self._manual_record_worker, daemon=True)
        self._record_thread.start()

    def stop(self):
        if not self.is_recording:
            return
        self._record_stop_event.set()

    def _get_whisper_model(self):
        if self._whisper_model is None:
            from faster_whisper import WhisperModel

            self._whisper_model = WhisperModel(self.model_name, compute_type=self.compute_type)
        return self._whisper_model

    def _warmup_transcriber(self):
        try:
            self._get_whisper_model()
        except Exception as exc:
            logging.warning(f"transcriber warmup failed: {exc}")

    def _drop_pending_jobs(self):
        while True:
            try:
                item = self._transcribe_jobs.get_nowait()
                if item is None:
                    self._transcribe_jobs.put(None)
                    break
            except queue.Empty:
                break

    def _submit_transcribe_job(
        self,
        audio_np: np.ndarray,
        session_id: int,
        is_preview: bool,
        replace_pending: bool = False,
    ) -> int:
        if replace_pending:
            self._drop_pending_jobs()
        with self._transcribe_lock:
            self._job_id += 1
            jid = self._job_id
        self._transcribe_jobs.put((jid, session_id, is_preview, audio_np.copy()))
        self._latest_requested_job_id = jid
        return jid

    def _transcribe_worker(self):
        while not self._transcribe_stop.is_set():
            try:
                item = self._transcribe_jobs.get(timeout=0.1)
            except queue.Empty:
                continue

            if item is None:
                break

            jid, session_id, is_preview, audio_np = item
            text = ""
            try:
                min_samples = int(self.min_length_of_recording * self.sample_rate)
                if audio_np.size >= min_samples:
                    model = self._get_whisper_model()
                    segments, _ = model.transcribe(audio_np, language=self.language)
                    text = self._preprocess_output(" ".join(segment.text for segment in segments))
            except Exception as exc:
                logging.warning(f"async transcribe failed: {exc}")

            with self._transcribe_cv:
                self._transcribe_results[jid] = {
                    "session_id": session_id,
                    "text": text,
                    "audio_len": int(audio_np.size),
                    "is_preview": is_preview,
                }
                if is_preview:
                    prev = self._latest_preview.get(session_id)
                    if (not prev) or (audio_np.size >= prev["audio_len"]):
                        self._latest_preview[session_id] = {
                            "job_id": jid,
                            "text": text,
                            "audio_len": int(audio_np.size),
                        }
                self._transcribe_cv.notify_all()

    def wait_audio(self):
        # Manual push-to-talk mode: wait until stop() ended recording thread.
        if self._manual_mode:
            if self._record_thread:
                self._record_thread.join()
            self._manual_mode = False
            return

        # Auto mode: block until voice activity then stop after silence.
        self.frames = []
        self.audio = np.array([], dtype=np.float32)
        self._prefetched_text = None
        self._current_final_job_id = None
        self._latest_requested_job_id = None
        self._session_id += 1
        self._current_session_id = self._session_id

        speech_started = False
        frame_seconds = self.chunk_size / float(self.sample_rate)
        end_silence_frames = max(1, int(self.post_speech_silence_duration / frame_seconds))
        pre_roll_frames = max(1, int(self.pre_roll_duration / frame_seconds))

        pre_buffer = collections.deque(maxlen=pre_roll_frames)
        consecutive_speech = 0
        consecutive_silence = 0
        preview_submitted_in_current_silence = False

        while True:
            if not self.recording_judger():
                time.sleep(0.01)
                continue

            data = self._stream.read(self.chunk_size, exception_on_overflow=False)

            if not speech_started:
                pre_buffer.append(data)
                if self._is_voice_active(data):
                    consecutive_speech += 1
                else:
                    consecutive_speech = 0

                if consecutive_speech >= self.start_speech_frames:
                    speech_started = True
                    self.is_recording = True
                    self._set_state("recording")
                    if self.on_recording_start:
                        try:
                            self.on_recording_start()
                        except Exception as exc:
                            logging.warning(f"on_recording_start failed: {exc}")
                    self.frames.extend(pre_buffer)
                    self.frames.append(data)
                continue

            self.frames.append(data)
            if self._is_voice_inactive(data):
                consecutive_silence += 1

                # Start async transcribe immediately when silence starts.
                if not preview_submitted_in_current_silence:
                    audio_i16 = np.frombuffer(b"".join(self.frames), dtype=np.int16)
                    audio_np = audio_i16.astype(np.float32) / INT16_MAX_ABS_VALUE
                    self._submit_transcribe_job(
                        audio_np,
                        self._current_session_id,
                        is_preview=True,
                        replace_pending=True,
                    )
                    preview_submitted_in_current_silence = True

                if consecutive_silence >= end_silence_frames:
                    break
            else:
                consecutive_silence = 0
                preview_submitted_in_current_silence = False
                # User resumed speaking, discard stale queued preview tasks.
                self._drop_pending_jobs()

        self._finalize_frames(self.frames)

        preview = self._latest_preview.get(self._current_session_id)
        if preview:
            final_len = int(self.audio.size)
            if final_len > 0 and preview["audio_len"] >= int(0.80 * final_len):
                self._prefetched_text = preview["text"]

        self.is_recording = False
        self._set_state("inactive")

    def transcribe(self) -> str:
        self._set_state("transcribing")
        try:
            if self.audio.size == 0:
                return ""

            min_samples = int(self.min_length_of_recording * self.sample_rate)
            if self.audio.size < min_samples:
                return ""

            if self._prefetched_text:
                self.last_transcription_bytes = self.audio.copy()
                return self._prefetched_text

            # Original-like behavior: wait for the latest silence-triggered async job.
            # If none exists, submit current audio once and wait for it.
            if self._latest_requested_job_id is None:
                self._latest_requested_job_id = self._submit_transcribe_job(
                    self.audio,
                    self._current_session_id or 0,
                    is_preview=False,
                    replace_pending=True,
                )

            target_job_id = self._latest_requested_job_id
            with self._transcribe_cv:
                while target_job_id not in self._transcribe_results:
                    self._transcribe_cv.wait(timeout=0.05)

                result = self._transcribe_results.get(target_job_id, {})

            self.last_transcription_bytes = self.audio.copy()
            return self._preprocess_output(result.get("text", ""))
        finally:
            self._set_state("inactive")

    def set_recording_judger(self, judger):
        self.recording_judger = judger

    def set_silero_off_sensitivity(self, off_sens):
        self.silero_off_sensitivity = off_sens

    def __del__(self):
        try:
            self._transcribe_stop.set()
            self._transcribe_jobs.put(None)
            if self._transcribe_thread is not None and self._transcribe_thread.is_alive():
                self._transcribe_thread.join(timeout=0.3)
        except Exception:
            pass
        try:
            if self._stream is not None:
                self._stream.stop_stream()
                self._stream.close()
        except Exception:
            pass
        try:
            if self._pyaudio is not None:
                self._pyaudio.terminate()
        except Exception:
            pass
