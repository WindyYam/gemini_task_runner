from RealtimeSTT import AudioToTextRecorder
import pygame
import keyboard
import threading

class VoiceRecognition:
    def __init__(self):
        self.recorder_config = {
            'spinner': False,
            'model': 'small',
            'language': '',
            'silero_sensitivity': 1,
            'webrtc_sensitivity': 3,
            'post_speech_silence_duration': 0.2,
            'min_length_of_recording': 0.5,
            'min_gap_between_recordings': 0,
        }
        self.recorder = AudioToTextRecorder(**self.recorder_config)
        self.on_sound = pygame.mixer.Sound("sonar.mp3")
        self.off_sound = pygame.mixer.Sound("droplet.mp3")
        self.evt_enter = threading.Event()
        
    def _trigger_button(self):
        self.evt_enter.set()

    def listen(self):
        keyboard.add_hotkey(-179, self._trigger_button, suppress=True, trigger_on_release=False)
        keyboard.add_hotkey('space', self._trigger_button, suppress=True, trigger_on_release=False)
        print("Waiting for trigger...")
        self.evt_enter.wait()
        self.evt_enter.clear()
        
        print("Listening ...")
        self.on_sound.play()
        self.recorder.start()
        
        self.evt_enter.wait()
        self.evt_enter.clear()
        
        self.off_sound.play()
        text = self.recorder.stop().text()

        keyboard.remove_hotkey(-179)
        keyboard.remove_hotkey('space')
        return text