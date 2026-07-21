"""
Local recorder/transcriber used to replace RealtimeSTT dependency.
Provides the subset of the old interface used by this project.
"""

import logging
import threading
import time
import collections
from typing import Callable, Optional

import numpy as np
import pyaudio

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
        chunk_size=1024,
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
        # Higher sensitivity means lower threshold.
        return max(0.003, 0.015 * (1.0 - float(self.silero_sensitivity)))

    def _silence_threshold(self) -> float:
        return max(0.0025, 0.012 * (1.0 - float(self.silero_off_sensitivity)))

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
        speech_started = False
        speech_threshold_base = self._speech_threshold()
        silence_threshold_base = self._silence_threshold()
        frame_seconds = self.chunk_size / float(self.sample_rate)
        end_silence_frames = max(1, int(self.post_speech_silence_duration / frame_seconds))
        pre_roll_frames = max(1, int(self.pre_roll_duration / frame_seconds))

        pre_buffer = collections.deque(maxlen=pre_roll_frames)
        consecutive_speech = 0
        consecutive_silence = 0
        noise_floor = 0.004

        while True:
            if not self.recording_judger():
                time.sleep(0.01)
                continue

            data = self._stream.read(self.chunk_size, exception_on_overflow=False)
            e = self._energy(data)
            speech_threshold = max(speech_threshold_base, noise_floor * 3.0)
            silence_threshold = max(silence_threshold_base, noise_floor * 1.8)

            if not speech_started:
                pre_buffer.append(data)
                if e >= speech_threshold:
                    consecutive_speech += 1
                else:
                    consecutive_speech = 0
                    noise_floor = 0.98 * noise_floor + 0.02 * e

                if consecutive_speech >= self.start_speech_frames:
                    speech_started = True
                    self.is_recording = True
                    self._set_state("recording")
                    if self.on_recording_start:
                        try:
                            self.on_recording_start()
                        except Exception as exc:
                            logging.warning(f"on_recording_start failed: {exc}")
                    # Keep a short pre-roll so the utterance start is not clipped.
                    self.frames.extend(pre_buffer)
                    self.frames.append(data)
                continue

            self.frames.append(data)
            if e < silence_threshold:
                consecutive_silence += 1
                if consecutive_silence >= end_silence_frames:
                    break
            else:
                consecutive_silence = 0

        self._finalize_frames(self.frames)
        self.is_recording = False
        self._set_state("inactive")

    def _get_whisper_model(self):
        if self._whisper_model is None:
            from faster_whisper import WhisperModel

            self._whisper_model = WhisperModel(self.model_name, compute_type=self.compute_type)
        return self._whisper_model

    def transcribe(self) -> str:
        self._set_state("transcribing")
        try:
            if self.audio.size == 0:
                return ""

            min_samples = int(self.min_length_of_recording * self.sample_rate)
            if self.audio.size < min_samples:
                return ""

            model = self._get_whisper_model()
            segments, _ = model.transcribe(self.audio, language=self.language)
            text = " ".join(segment.text for segment in segments)
            self.last_transcription_bytes = self.audio.copy()
            return self._preprocess_output(text)
        finally:
            self._set_state("inactive")

    # Kept for compatibility with old custom recorder behavior.
    def set_recording_judger(self, judger):
        self.recording_judger = judger

    def set_silero_off_sensitivity(self, off_sens):
        self.silero_off_sensitivity = off_sens

    def __del__(self):
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
