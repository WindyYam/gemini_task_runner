import queue
import os
import wave
import numpy as np
import pyaudio
from auto_lang_coqui_engine import AutoLangCoquiEngine
from text_stream_to_stream import TextStreamToAudioStream
class TextToSpeech:
    def __init__(self, voice_path, device_name = None):
        self.DEFAULT_VOICE = 'default'
        self.MIMIC_VOICE = 'mimic'
        self.TRUMP_VOICE = 'trump3'
        self.BIDEN_VOICE = 'biden'
        self.VADER_VOICE = 'vader'
        self.ROBOT_VOICE = 'robot'
        self.FEMALE_VOICE = 'female'
        self.voice_path = voice_path
        self.mSpeakQueue = queue.Queue()
        self.eng = AutoLangCoquiEngine(   
            voice=self.DEFAULT_VOICE,
            specific_model='v2.0.3',
            stream_chunk_size=20,
            speed=1.3,
            pretrained=False,
            comma_silence_duration=0.2,
            sentence_silence_duration=0.4,
            default_silence_duration=0.2,
            voices_path=voice_path,
            language='en')
        
        audio = pyaudio.PyAudio()
        info = audio.get_default_host_api_info()
        numdevices = info.get('deviceCount')
        device_index = None

        if device_name:
            for i in range(0, numdevices):
                if audio.get_device_info_by_host_api_device_index(0, i).get('maxOutputChannels') > 0:
                    if device_name in audio.get_device_info_by_host_api_device_index(0, i).get('name'):
                        device_index = i
        if device_index:
            print('Setting Speaker: ', audio.get_device_info_by_host_api_device_index(0, device_index).get('name'))
        else:
            print('Setting Speaker: ', audio.get_default_output_device_info().get('name'))
        self.stream = TextStreamToAudioStream(self.eng, output_device_index=device_index)

        def iterator():
            while True:
                chunk = self.mSpeakQueue.get()  # Blocks if queue is empty
                yield chunk  # Yield the next chunk
        self.stream.play_async(external_text_iterator = iterator(), sentence_fragment_delimiters = ".?!;\n…))]}。？")

    def stop(self):
        with self.mSpeakQueue.mutex:
            self.mSpeakQueue.queue.clear()
        self.stream.stop()
        with self.mSpeakQueue.mutex:
            self.mSpeakQueue.queue.clear()

    def feed(self, text:str):
        self.stream.check_player()
        text = text.replace('*', ' ')
        self.mSpeakQueue.put(text)

    def add_audio_listener(self, callback):
        self.stream.add_audio_listener(callback)

    def remove_audio_listener(self, callback):
        self.stream.remove_audio_listener(callback)

    def switch_user_voice(self, audio):
        samplerate = 16000
        audio = audio / np.max(np.abs(audio))
        audio = (audio * (2 ** 15 - 1)).astype(np.int16)
        with wave.open(self.voice_path + self.MIMIC_VOICE + ".wav", "w") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(samplerate)
            f.writeframes(audio)
        mimic_latent = self.voice_path + self.MIMIC_VOICE+'.json'
        if os.path.exists(mimic_latent):
            os.remove(mimic_latent)
        self.eng.set_voice(voice=self.MIMIC_VOICE)

    def switch_default_mode(self):
        self.eng.set_voice(voice=self.DEFAULT_VOICE)

    def switch_trump_mode(self):
        self.eng.set_voice(voice=self.TRUMP_VOICE)
    
    def switch_biden_mode(self):
        self.eng.set_voice(voice=self.BIDEN_VOICE)

    def switch_vader_mode(self):
        self.eng.set_voice(voice=self.VADER_VOICE)
    
    def switch_robot_mode(self):
        self.eng.set_voice(voice=self.ROBOT_VOICE)

    def switch_female_mode(self):
        self.eng.set_voice(voice=self.FEMALE_VOICE)