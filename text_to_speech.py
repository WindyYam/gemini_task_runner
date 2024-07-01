import RealtimeTTS
import os
import wave
import pygame
import langdetect

class TextToSpeech:
    def __init__(self):
        self.DEFAULT_VOICE = 'RA.wav'
        self.MIMIC_VOICE = 'mimic.wav'
        self.TRUMP_VOICE = 'trump3.wav'
        self.BIDEN_VOICE = 'biden.wav'
        self.VADER_VOICE = 'vader.wav'
        self.ROBOT_VOICE = 'goliath.wav'

        self.eng = RealtimeTTS.CoquiEngine(   
            voice=self.DEFAULT_VOICE,
            specific_model='v2.0.3',
            stream_chunk_size=40,
            speed=1.1,
            pretrained=True,
            comma_silence_duration=0.2,
            sentence_silence_duration=0.4,
            default_silence_duration=0.2,
            language='en')
        self.stream = RealtimeTTS.TextToAudioStream(self.eng)
        
        self.vader_breath = pygame.mixer.Sound("breathing.mp3")
        self.vader_breath.set_volume(0.1)

    def stop(self):
        if(self.stream.is_playing()):
            self.stream.stop()

    def speak(self, text):
        text = text.replace('*', ' ')
        lang = langdetect.detect(text)
        if('en' in lang):
            lang = 'en'
        elif('ja' in lang):
            lang = 'ja'
        elif('kn' in lang):
            lang = 'kn'
        else:
            lang = 'zh'
        self.eng.language = lang
        self.stream.feed(text)
        self.stream.play_async(sentence_fragment_delimiters = ".?!;,\n…{[())]}。-？，")

    def switch_user_voice(self, recorder):
        self.vader_breath.stop()
        samplerate = 16000
        audio = (recorder.audio * (2 ** 15 - 1)).astype("<h")
        with wave.open(self.MIMIC_VOICE, "w") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(samplerate)
            f.writeframes(audio)
        mimic_latent = self.MIMIC_VOICE[:-4]+'.json'
        if os.path.exists(mimic_latent):
            os.remove(mimic_latent)
        self.eng.set_voice(voice=self.MIMIC_VOICE[:-4])

    def revert_default_role(self):
        self.vader_breath.stop()
        self.eng.set_voice(voice=self.DEFAULT_VOICE[:-4])

    def switch_trump_role(self):
        self.vader_breath.stop()
        self.eng.set_voice(voice=self.TRUMP_VOICE[:-4])
    
    def switch_biden_role(self):
        self.vader_breath.stop()
        self.eng.set_voice(voice=self.BIDEN_VOICE[:-4])

    def switch_vader_role(self):
        self.vader_breath.play(-1)
        self.eng.set_voice(voice=self.VADER_VOICE[:-4])
    
    def switch_robot_role(self):
        self.vader_breath.stop()
        self.eng.set_voice(voice=self.ROBOT_VOICE[:-4])