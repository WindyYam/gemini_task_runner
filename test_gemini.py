# Voice assistant for smart home control
# conceptual test
# 

if __name__ == "__main__":
    import google.generativeai as genai
    from datetime import date
    import datetime
    import time
    import io
    import os
    from typing import Literal
    from RealtimeSTT import AudioToTextRecorder
    import RealtimeTTS
    import threading
    import pygame
    import pygame.camera
    import keyboard
    from extern_api import *
    import langdetect
    import wave

    MAX_HISTORY = 40
    keyboard_test_mode = False
    DEFAULT_VOICE = 'RA.wav'
    MIMIC_VOICE = 'mimic.wav'
    TRUMP_VOICE = 'trump3.wav'
    BIDEN_VOICE = 'biden.wav'
    VADER_VOICE = 'vader.wav'
    ROBOT_VOICE = 'goliath.wav'

    context = {
        'talk':[],
        'query_response':'',
        'image': None,
        'photo_file': None,
        'continuous_photo_mode': False
    }

    keycode = 'Jarvis'

    recorder_config = {
        'spinner': False,
        'model': 'small',
        'language': '',
        'silero_sensitivity': 1,
        'webrtc_sensitivity': 3,
        'post_speech_silence_duration': 0.2,
        'min_length_of_recording': 0.5,
        'min_gap_between_recordings': 0,        
        # 'enable_realtime_transcription': True,
        # 'realtime_processing_pause': 0.2,
        # 'realtime_model_type': 'tiny',
        # 'on_realtime_transcription_update': text_detected, 
        #'on_realtime_transcription_stabilized': text_detected,
    }

    if not keyboard_test_mode:
        recorder = AudioToTextRecorder(**recorder_config)

    # eng = RealtimeTTS.AzureEngine(        
    #     speech_key = os.environ.get("AZURE_API_KEY"),
    #     service_region = 'australiaeast',
    #     rate = 0.5,
    #     voice ='zh-CN-XiaorouNeural')
    # eng.set_emotion('cheerful')

    eng = RealtimeTTS.CoquiEngine(   
        voice=DEFAULT_VOICE,
        specific_model='v2.0.3',
        stream_chunk_size=40,
        speed=1.1,
        pretrained=True,
        comma_silence_duration=0.2,
        sentence_silence_duration=0.4,
        default_silence_duration=0.2,
        language='en')
    stream = RealtimeTTS.TextToAudioStream(eng)
    #os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

    # set the Google Gemini API key as a system environment variable or add it here
    genai.configure(api_key= os.environ.get("GEMINI_API_KEY"))

    today = str(date.today())

    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)

    lists = genai.list_files()
    for item in lists:
        print(item.name)
        genai.delete_file(item)

    pygame.init()
    # initializing  the camera 
    pygame.camera.init() 

    # make the list of all available cameras 
    camlist = pygame.camera.list_cameras() 

    img_size = (420, 240)

    if camlist: 
        # initializing the cam variable with default camera 
        cam = pygame.camera.Camera(camlist[0], img_size) 

    on_sound = pygame.mixer.Sound("sonar.mp3")
    off_sound = pygame.mixer.Sound("droplet.mp3")
    vader_breath = pygame.mixer.Sound("breathing.mp3")
    vader_breath.set_volume(0.1)

    display = None
    
    lock = threading.Lock()
    def event_thread():
        global display
        clock = pygame.time.Clock()
        display = pygame.display.set_mode(img_size, 0)
        while(True):
            clock.tick(24)
            if context['continuous_photo_mode']:
                while(not cam.query_image()):
                    pass
                # capturing the single image 
                lock.acquire()
                context['image'] = cam.get_image() 
                lock.release()
                display.blit(context['image'], (0,0))
                pygame.display.flip()
            else:
                pygame.event.wait()
            pygame.event.pump()

    threading.Thread(target=event_thread).start()

    def strip_history():
        if(len(context['talk']) > MAX_HISTORY):
            context['talk'] = context['talk'][len(context['talk']) - MAX_HISTORY :]

    def photo_stream_mode(on:bool):
        if(on):
            cam.start()
            context['continuous_photo_mode'] = True
        else:
            context['continuous_photo_mode'] = False
            cam.stop()
        

    def capture()->str:
        # opening the camera 
        if not context['continuous_photo_mode']:
            cam.start() 
            while(not cam.query_image()):
                pass
            time.sleep(0.1)
            # capturing the single image 
            image = cam.get_image() 
            cam.stop()
            photo_name = "camera.jpg"
            # saving the image 
            pygame.image.save(image, photo_name)
            return photo_name
        else:
            return ''

    def feed_text(text:str):
        text = text.replace('*', ' ')
        stream.feed(text)
        #eng.synthesize(text)

    def speak():
        stream.play_async(sentence_fragment_delimiters = ".?!;,\n…{[())]}。-？，")
        #print('\a')

    def extract_code(input_string:str):
        start = input_string.find('```python')
        end = -1
        if(start >= 0):
            start = start + 9
            end = input_string.find('```', start)
        if start == -1 or end == -1:
            return ''
        return input_string[start:end]
    
    def strip_code(input_string:str):
        start = input_string.find('```python')
        end = input_string.find('```', start + 9)
        if start == -1 or end == -1:
            return input_string
        return input_string[0:start] + input_string[end + 3:-1]
    
    def exec_code(code:str):
        try:
            d = dict(locals(), **globals())
            exec(code, d, d)
        except Exception as e:
            print("Code exec exception: ", e)

    def attach_to_context(*values: object,
            sep: str | None = " ",
            end: str | None = "\n",
            flush: Literal[False] = False,):
        string_output = io.StringIO()
        print(*values, file=string_output, sep=sep, end=end, flush=flush)
        context['query_response'] = string_output.getvalue().strip()
        if(context['query_response'].endswith('.jpg')):
            image_file = string_output.getvalue().strip()
            if(not context['continuous_photo_mode']):
                img = pygame.image.load(image_file).convert()
                display.blit(img, (0, 0))
                pygame.display.flip()

            context['photo_file'] = genai.upload_file(path=image_file,
                                    display_name="photo")
        string_output.close()
    
    def switch_user_voice():
        vader_breath.stop()
        samplerate = 16000
        audio = (recorder.audio * (2 ** 15 - 1)).astype("<h")
        with wave.open(MIMIC_VOICE, "w") as f:
            # 1 Channels.
            f.setnchannels(1)
            # 2 bytes per sample.
            f.setsampwidth(2)
            f.setframerate(samplerate)
            f.writeframes(audio)
        mimic_latent = MIMIC_VOICE[:-4]+'.json'
        if os.path.exists(mimic_latent):
            os.remove(mimic_latent)
        eng.set_voice(voice=MIMIC_VOICE[:-4])
        # # let the AI use new voice
    
    def revert_default_role():
        vader_breath.stop()
        eng.set_voice(voice=DEFAULT_VOICE[:-4])

    def switch_trump_role():
        vader_breath.stop()
        eng.set_voice(voice=TRUMP_VOICE[:-4])
    
    def switch_biden_role():
        vader_breath.stop()
        eng.set_voice(voice=BIDEN_VOICE[:-4])

    def switch_vader_role():
        vader_breath.play(-1)
        eng.set_voice(voice=VADER_VOICE[:-4])
    
    def switch_robot_role():
        vader_breath.stop()
        eng.set_voice(voice=ROBOT_VOICE[:-4])

    function_file = genai.upload_file(path="extern_api.py",
                                    display_name="Python API")
    talk_header = [{'role': 'user', 'parts': [function_file, 'This is the python APIs you can execute. To execute them, put them in python code snippet at the end of your response']},
                {'role': 'model', 'parts': [f"Understood, I'll remember to always check this file for available API calls to execute.\n"]}]
    now = datetime.now()
    dt_string = now.strftime("%d/%B/%Y")
    # model of Google Gemini API
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    model = genai.GenerativeModel(model_name='gemini-1.5-flash', safety_settings={
                                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                                    },
                                  system_instruction=[f'Remember, today is {dt_string}, your name is {keycode}, a well educated assistant with character, have great knowledge on everything. \
                                                                                     Keep in mind that you are my AI assistant, with voice synthesis output from response text as part of the system. \
                                                                                     The input system will always attach a timestamp for your reference. \
                                                                                     The python function API and information API and the usage description you can interact with is in the uploaded python file. \
                                                                                     To execute the python code, put the code as python snippet at the end of the response, then any code in the snippet in response will be executed. \
                                                                                     If you want to get the return value of an API, call attach_to_context(value) on that value in the code snippet, which forces me to relay the value to you. \
                                                                                     Be sure to always check the matching snippet APIs before generating response. You are to answer questions as short as possible, and always in a humorous way.'])
    
    # save conversation to a log file 
    def append2log(text):
        fname = 'chatlog-' + today + '.txt'
        with open(fname, "a", encoding='utf8') as f:
            f.write(text + "\n")

    # Main function for conversation
    def main():
        sleeping = False 

        evtEnter = threading.Event()
        def btn():
            evtEnter.set()
        #-179 is the play/pause media key
        keyboard.add_hotkey(-179, btn, suppress=True, trigger_on_release=False)
        keyboard.add_hotkey('space', btn, suppress=True, trigger_on_release=False)
        #keyup = keyboard.add_hotkey(-179, lambda: evtExit.set(), suppress=True, trigger_on_release=True)
        feed_text(f"I'm {keycode}, how can I help you?")
        print('\a')
        speak()

        while True:
            try: 
                if(context['query_response'] == ''):
                    if keyboard_test_mode:
                        text = input('Input:')
                    else:
                        evtEnter.wait()
                        evtEnter.clear()
                        print("Listening ...")
                        on_sound.play()
                        recorder.start()
                        #text = input()
                        evtEnter.wait()
                        evtEnter.clear()
                        off_sound.play()
                        text = recorder.stop().text()
                    print(text)
                    if(text != ''):
                        print('\a')
                    # AI is in sleeping mode
                    if sleeping == True:
                        if keycode.lower() in text.lower():
                            sleeping = False
                            # AI is awake now, 
                            # start a new conversation 
                            append2log(f"_"*40)
                        else:
                            stream.feed('I am deactivated.')
                            stream.play_async()
                            continue
                        
                    # AI is awake         
                    request = text.strip()
                    if(len(request) <= 1):
                        continue
                    request_low = request.lower()
                    if ("that's all" in request_low) or ("see you" in request_low) or ("bye" in request_low):
                                                
                        append2log(f"You: {request}\n")
                        revert_default_role()

                        feed_text("OK, see you soon.")
                        speak()

                        append2log(f"AI: OK, see you soon.\n")
                        
                        sleeping = True
                        # AI goes back to speeling mode
                        continue   
                    
                    # process user's request (question)
                else:
                    request = context['query_response']
                    context['query_response'] = ''

                if context['continuous_photo_mode']:
                    filename = "camera.jpg"
                    # saving the image 
                    lock.acquire()
                    pygame.image.save(context['image'], filename)
                    lock.release()
                    context['photo_file'] = genai.upload_file(path=filename,
                                        display_name="photo")
                
                temp = talk_header + context['talk']
                
                new_item = None
                now = datetime.now()
                dt_string = now.strftime("%H:%M:%S")
                if context['photo_file']:
                    new_item = {'role':'user', 'parts':[context['photo_file'], request, dt_string]} 
                    context['photo_file'] = None
                else:
                    new_item = {'role':'user', 'parts':[request, dt_string]}
                
                context['talk'].append(new_item)

                temp.append(new_item)

                print(f"You: {new_item['parts']}" )
                
                # to make sure always be pair in conversation
                reply = {'role':'model', 'parts':['']}

                response = model.generate_content(temp, stream=False,
                #generation_config=genai.types.GenerationConfig(
                # Only one candidate for now.
                #max_output_tokens=125) 
                )

                print("AI: ", end='')

                for chunk in response:
                    chunk_text = chunk.text
                    print(chunk_text, end='')

                print('')

                all_text = response.text
                pythoncode = extract_code(response.text)
                voice_text = strip_code(all_text)

                if voice_text != '':
                    if stream.is_playing():
                        stream.stop()

                thread = None
                if(pythoncode != ''):
                    print(f'code: {pythoncode}')
                    thread = threading.Thread(target=exec_code, args=(pythoncode,))
                    # Start the thread
                    thread.start()

                if (not keyboard_test_mode) and (voice_text != ''):
                    lang = langdetect.detect(voice_text)
                    if('en' in lang):
                        lang = 'en'
                    elif('ja' in lang):
                        lang = 'ja'
                    elif('kn' in lang):
                        lang = 'kn'
                    else:
                        lang = 'zh'
                    print(lang)
                    eng.language = lang
                    feed_text(voice_text)
                    speak()

                if thread:
                    thread.join()

                reply['parts'] = [all_text]
                context['talk'].append(reply)
                
                strip_history()
                #print(talk)           

                append2log(f"You: {new_item['parts']}\n ")
                append2log(f"AI: {all_text} \n")

            except Exception as e:
                print(e)
                continue 
    
    main()