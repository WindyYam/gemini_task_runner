from RealtimeSTT import AudioToTextRecorder
from resemblyzer import preprocess_wav, VoiceEncoder
import numpy as np

class VoiceRecognition:
    def __init__(self, on_recording_start):
        self.recorder_config = {
            'spinner': False,
            'model': 'small',
            'language': '',
            'silero_sensitivity': 0.1,
            'silero_use_onnx': True,
            'webrtc_sensitivity': 1,
            'post_speech_silence_duration': 0.2,
            'min_length_of_recording': 0.5,
            'min_gap_between_recordings': 0,
            'on_recording_start':on_recording_start
        }
        self.recorder = AudioToTextRecorder(**self.recorder_config)
        self.encoder = VoiceEncoder("cpu")

    def generate_embed(self, audio):
        return self.encoder.embed_utterance(preprocess_wav(audio))
    
    def verify_speaker(self, original_embed, new_embed):
        similarity = np.inner(original_embed, new_embed)
        return similarity

    def start_listen(self):
        self.recorder.set_microphone(True)
        self.recorder.start()

    def stop_listen(self) -> str:
        self.recorder.set_microphone(False)
        self.recorder.stop()
        self.recorder.wait_audio()

    def transcribe_voice(self) -> str:
        return self.recorder.transcribe()

    def listen(self):
        self.recorder.set_microphone(True)
        self.recorder.wait_audio()
        self.recorder.set_microphone(False)