import logging
import queue
import re
import threading
import time
from typing import Iterator

import numpy as np
import pyaudio


class TextStreamToAudioStream:
    """Lightweight text-stream to audio-stream bridge for one synthesis engine."""

    def __init__(self, engine, output_device_index=None):
        self.engine = engine
        self.output_device_index = output_device_index

        self.is_playing_flag = False
        self.stream_running = False

        self._pyaudio = pyaudio.PyAudio()
        self._audio_stream = None
        self._audio_stream_lock = threading.Lock()
        self._audio_listener_lock = threading.Lock()
        self._audio_listeners = []

        self._shutdown_event = threading.Event()
        self._paused_event = threading.Event()
        self._paused_event.clear()
        self._writing_audio = threading.Event()

        self.sentence_queue = queue.Queue()
        self._parser_thread = None
        self._synth_thread = None
        self._audio_thread = None

        self._sentence_fragment_delimiters = ".?!;:,\n...)]}。-"

    def play_async(
        self,
        external_text_iterator: Iterator[str],
        fast_sentence_fragment: bool = True,
        buffer_threshold_seconds: float = 0.0,
        minimum_sentence_length: int = 10,
        minimum_first_fragment_length: int = 10,
        log_synthesized_text=False,
        reset_generated_text: bool = True,
        output_wavfile: str = None,
        on_sentence_synthesized=None,
        before_sentence_synthesized=None,
        on_audio_chunk=None,
        tokenizer: str = "",
        tokenize_sentences=None,
        language: str = "",
        context_size: int = 12,
        muted: bool = False,
        sentence_fragment_delimiters: str = ".?!;:,\n...)]}。-",
        force_first_fragment_after_words=15,
    ):
        # Keep signature compatibility with previous implementation. Most args are not needed.
        del (
            fast_sentence_fragment,
            buffer_threshold_seconds,
            minimum_sentence_length,
            minimum_first_fragment_length,
            reset_generated_text,
            output_wavfile,
            on_audio_chunk,
            tokenizer,
            tokenize_sentences,
            language,
            context_size,
            force_first_fragment_after_words,
        )

        if self.stream_running:
            return

        self._sentence_fragment_delimiters = sentence_fragment_delimiters or self._sentence_fragment_delimiters
        self.stream_running = True
        self.is_playing_flag = True

        if muted:
            self._paused_event.set()
        else:
            self._paused_event.clear()

        self._ensure_audio_stream_started()

        self._parser_thread = threading.Thread(
            target=self._parser_worker,
            args=(external_text_iterator,),
            daemon=True,
        )
        self._synth_thread = threading.Thread(
            target=self._synth_worker,
            args=(log_synthesized_text, before_sentence_synthesized, on_sentence_synthesized),
            daemon=True,
        )
        self._audio_thread = threading.Thread(target=self._audio_worker, daemon=True)

        self._parser_thread.start()
        self._synth_thread.start()
        self._audio_thread.start()

    def _ensure_audio_stream_started(self):
        with self._audio_stream_lock:
            if self._audio_stream is None:
                fmt, channels, rate = self.engine.get_stream_info()
                kwargs = {
                    "format": fmt,
                    "channels": channels,
                    "rate": rate,
                    "output": True,
                }
                if self.output_device_index is not None:
                    kwargs["output_device_index"] = self.output_device_index
                self._audio_stream = self._pyaudio.open(**kwargs)

            if self._audio_stream.is_stopped():
                self._audio_stream.start_stream()

    def _parser_worker(self, external_text_iterator: Iterator[str]):
        pattern = self._build_sentence_pattern(self._sentence_fragment_delimiters)
        buffer = ""

        for chunk in external_text_iterator:
            if self._shutdown_event.is_set():
                break

            if not chunk:
                continue

            buffer += str(chunk)
            matches = list(re.finditer(pattern, buffer))
            for match in matches:
                sentence = self._sanitize_text(match.group(1)).strip()
                if sentence:
                    self.sentence_queue.put(sentence)

            if matches:
                buffer = re.sub(pattern, "", buffer, count=len(matches))

    def _synth_worker(self, log_synthesized_text, before_sentence_synthesized, on_sentence_synthesized):
        while not self._shutdown_event.is_set():
            sentence = self.sentence_queue.get()
            try:
                if sentence is None:
                    continue

                if log_synthesized_text:
                    logging.info(f"synthesizing: {sentence}")

                if before_sentence_synthesized:
                    before_sentence_synthesized(sentence)

                success = self.engine.synthesize(sentence)
                if success and on_sentence_synthesized:
                    on_sentence_synthesized(sentence)
            except Exception as exc:
                logging.warning(f"synthesis failed: {exc}")
            finally:
                self.sentence_queue.task_done()

    def _audio_worker(self):
        while not self._shutdown_event.is_set():
            if self._paused_event.is_set():
                self._writing_audio.clear()
                time.sleep(0.02)
                continue

            try:
                chunk = self.engine.queue.get(timeout=0.1)
            except queue.Empty:
                self._writing_audio.clear()
                continue

            try:
                self._writing_audio.set()
                self._ensure_audio_stream_started()
                raw = self._to_bytes(chunk)
                if raw:
                    with self._audio_listener_lock:
                        listeners = list(self._audio_listeners)
                    for callback in listeners:
                        try:
                            callback(raw)
                        except Exception as exc:
                            logging.warning(f"audio listener failed: {exc}")
                    self._audio_stream.write(raw)
            except Exception as exc:
                logging.warning(f"audio playback failed: {exc}")
            finally:
                self.engine.queue.task_done()
                self._writing_audio.clear()

    @staticmethod
    def _build_sentence_pattern(delimiters: str) -> str:
        escaped = re.escape(delimiters)
        return f"([^{escaped}]+[{escaped}]+)"

    @staticmethod
    def _sanitize_text(text: str) -> str:
        # Strip URLs and non-text symbols that are noisy for TTS.
        text = re.sub(
            r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            "",
            text,
        )
        text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
        return text

    @staticmethod
    def _to_bytes(chunk) -> bytes:
        if chunk is None:
            return b""
        if isinstance(chunk, bytes):
            return chunk
        if isinstance(chunk, bytearray):
            return bytes(chunk)
        if isinstance(chunk, np.ndarray):
            if chunk.dtype != np.float32:
                chunk = chunk.astype(np.float32)
            return np.ascontiguousarray(chunk).tobytes()

        arr = np.asarray(chunk, dtype=np.float32)
        return np.ascontiguousarray(arr).tobytes()

    @staticmethod
    def _clear_queue(q: queue.Queue):
        with q.mutex:
            q.queue.clear()

    def check_player(self):
        self._paused_event.clear()
        self._ensure_audio_stream_started()

    def add_audio_listener(self, callback):
        with self._audio_listener_lock:
            if callback not in self._audio_listeners:
                self._audio_listeners.append(callback)

    def remove_audio_listener(self, callback):
        with self._audio_listener_lock:
            self._audio_listeners = [cb for cb in self._audio_listeners if cb != callback]

    def stop(self):
        self._paused_event.set()
        self._clear_queue(self.sentence_queue)
        self._clear_queue(self.engine.queue)

        try:
            self.engine.sync()
        except Exception as exc:
            logging.warning(f"engine sync failed during stop: {exc}")

        # Clear again after sync to drop any chunks enqueued while waiting
        # for the synchronization barrier.
        self._clear_queue(self.sentence_queue)
        self._clear_queue(self.engine.queue)

        with self._audio_stream_lock:
            if self._audio_stream and self._audio_stream.is_active():
                self._audio_stream.stop_stream()

    def is_still_playing(self):
        has_pending_sentences = self.sentence_queue.qsize() > 0
        has_pending_audio = self.engine.queue.qsize() > 0
        return has_pending_sentences or has_pending_audio or self._writing_audio.is_set()

    def shutdown(self):
        self._shutdown_event.set()
        self.stop()

        with self._audio_stream_lock:
            if self._audio_stream is not None:
                self._audio_stream.close()
                self._audio_stream = None

        self._pyaudio.terminate()
