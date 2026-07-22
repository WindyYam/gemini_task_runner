from abc import ABC, ABCMeta
from typing import Union
import shutil
import queue


class BaseInitMeta(ABCMeta):
    """Call BaseEngine initialization after subclass construction."""

    def __call__(cls, *args, **kwargs):
        instance = super().__call__(*args, **kwargs)
        BaseEngine.__init__(instance)
        if hasattr(instance, "post_init"):
            instance.post_init()
        return instance


class BaseEngine(ABC, metaclass=BaseInitMeta):
    def __init__(self):
        self.engine_name = "unknown"
        self.can_consume_generators = False
        self.queue = queue.Queue()
        self.on_audio_chunk = None
        self.on_playback_start = None

    def get_stream_info(self):
        raise NotImplementedError(
            "The get_stream_info method must be implemented by the derived class."
        )

    def synthesize(self, text: str) -> bool:
        raise NotImplementedError(
            "The synthesize method must be implemented by the derived class."
        )

    def get_voices(self):
        raise NotImplementedError(
            "The get_voices method must be implemented by the derived class."
        )

    def set_voice(self, voice: Union[str, object]):
        raise NotImplementedError(
            "The set_voice method must be implemented by the derived class."
        )

    def set_voice_parameters(self, **voice_parameters):
        raise NotImplementedError(
            "The set_voice_parameters method must be implemented by the derived class."
        )

    def shutdown(self):
        pass

    def is_installed(self, lib_name: str) -> bool:
        return shutil.which(lib_name) is not None
