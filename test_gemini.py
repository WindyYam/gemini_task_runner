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

    MAX_HISTORY = 40
    keyboard_test_mode = False

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
        voice='RA.wav',
        #voice='coqui_Damien Black.wav',
        #voice='record.wav',
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
    # model of Google Gemini API
    model = genai.GenerativeModel(model_name='gemini-1.5-flash')

    #lists = genai.list_files()
    #for item in lists:
    #    print(item.name)
    #    genai.delete_file(item)

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

    display = None
    
    lock = threading.Lock()
    def event_thread():
        global display
        clock = pygame.time.Clock()
        display = pygame.display.set_mode(img_size, 0)
        while(True):
            clock.tick(24)
            pygame.event.pump()
            if context['continuous_photo_mode']:
                while(not cam.query_image()):
                    pass
                # capturing the single image 
                lock.acquire()
                context['image'] = cam.get_image() 
                lock.release()
                display.blit(context['image'], (0,0))
                pygame.display.flip()

    threading.Thread(target=event_thread).start()

    def strip_history():
        if(len(context['talk']) > MAX_HISTORY):
            context['talk'] = context['talk'][len(context['talk']) - MAX_HISTORY :]

    def photo_stream_mode(on:bool):
        cam.start()
        context['continuous_photo_mode'] = on

    def capture()->str:
        # opening the camera 
        if not context['continuous_photo_mode']:
            cam.start() 
        while(not cam.query_image()):
            pass
        # capturing the single image 
        image = cam.get_image() 
        if not context['continuous_photo_mode']:
            cam.stop()
        photo_name = "camera.jpg"
        # saving the image 
        pygame.image.save(image, photo_name)
        return photo_name

    def feed_text(text:str):
        #pass
        if stream.is_playing():
            stream.stop()
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
        context['query_response'] += string_output.getvalue()
        if(string_output.getvalue().strip().endswith('.jpg')):
            image_file = string_output.getvalue().strip()
            if(not context['continuous_photo_mode']):
                img = pygame.image.load(image_file).convert()
                display.blit(img, (0, 0))
                pygame.display.flip()

            context['photo_file'] = genai.upload_file(path=image_file,
                                    display_name="photo")
        string_output.close()
        
    function_file = genai.upload_file(path="extern_api.py",
                                    display_name="Python API")
    talk_header = [{'role': 'user', 'parts': [function_file, f'Remember, your name is {keycode}, a well educated assistant with character, have great knowledge on everything. Keep in mind that you are my AI assistant, the python function API and information API and the usage description you can interact with is in the uploaded file. When you confirm to execute a python API, put the code you want to execute as python snippet at the end of the response. If you want to get the execution of return value of an API, call attach_to_context(value) on that value in the code snippet, which indicate me to relay the value to you. You are to answer my questions as short as possible, and always in a humorous way.']},
                {'role': 'model', 'parts': [f"Understood., I'm {keycode}, your loyal assistant. I'll be concise. I can see the world by taking photo and attach to the context.\n"]}]
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
        feed_text(f"My name is {keycode}, how can I help you?")
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
                        pygame.mixer.Sound.play(on_sound)
                        recorder.start()
                        #text = input()
                        evtEnter.wait()
                        evtEnter.clear()
                        pygame.mixer.Sound.play(off_sound)
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
                            continue
                        
                    # AI is awake         
                    request = text.lower().strip()
                    if(len(request) <= 1):
                        continue
                    if ("that's all" in request) or ("see you" in request) or ("bye" in request):
                                                
                        append2log(f"You: {request}\n")
                        
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

                print(f"You: {request}" )

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
                if context['photo_file']:
                    new_item = {'role':'user', 'parts':[context['photo_file'], request]} 
                    context['photo_file'] = None
                else:
                    new_item = {'role':'user', 'parts':[request]}
                
                context['talk'].append(new_item)

                temp.append(new_item)
                
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

                append2log(f"You: {request}\n ")
                append2log(f"AI: {all_text} \n")

            except Exception as e:
                print(e)
                continue 
    
    main()