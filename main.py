if __name__ == "__main__":
    import os
    import threading
    import pygame
    import pygame.camera
    import time
    from datetime import datetime, date
    import io
    from typing import Literal
    from gemini_ai import GeminiAI
    from voice_recognition import VoiceRecognition
    from text_to_speech import TextToSpeech
    from extern_api import *

    MAX_HISTORY = 40
    keyboard_test_mode = False
    keycode = 'Jarvis'

    context = {
        'talk': [],
        'query_response': '',
        'image': None,
        'photo_file': None,
        'continuous_photo_mode': False,
        'attach_to_context_in_a_row': 0,
        'today':''
    }

    instruction = [
        f'Remember, today is {datetime.now().strftime("%d/%B/%Y")}, your name is {keycode}, '
        'a well educated assistant with character, have great knowledge on everything. '
        'Keep in mind that you are my AI assistant, with voice synthesis output from response text as part of the system. '
        'My input system will always attach a timestamp for your clock reference, but without noticing me. '
        'The python function API and information API and the usage description you can interact with is in the uploaded python file. '
        'To execute the python code, put the code as python snippet at the end of the response, then any code in the snippet in response will be executed. '
        'If you want to get the return value of an API, call attach_to_context(value) on that value in the code snippet, which forces me to relay the value to you. '
        'Be sure to always check the matching snippet APIs before generating response. You are to answer questions as short as possible, and always in a humorous way.'
    ]

    def append2log(text):
        fname = 'chatlog-' + context['today'] + '.txt'
        with open(fname, "a", encoding='utf8') as f:
            f.write(text + "\n")

    def attach_to_context(*values: object,
            sep: str | None = " ",
            end: str | None = "\n",
            flush: Literal[False] = False):
        string_output = io.StringIO()
        context['attach_to_context_in_a_row'] = context['attach_to_context_in_a_row'] + 1
        if(context['attach_to_context_in_a_row'] >= 4):
            return
        print(*values, file=string_output, sep=sep, end=end, flush=flush)
        context['query_response'] = string_output.getvalue().strip()
        if context['query_response'].endswith('.jpg'):
            image_file = string_output.getvalue().strip()
            if not context['continuous_photo_mode']:
                img = pygame.image.load(image_file).convert()
                pygame.display.get_surface().blit(img, (0, 0))
                pygame.display.flip()
            context['photo_file'] = gemini_ai.upload_file(image_file, display_name='Photo')
        string_output.close()

    def photo_stream_mode(on:bool):
        if(on):
            cam.start()
            context['continuous_photo_mode'] = True
        else:
            context['continuous_photo_mode'] = False
            cam.stop()

    def capture_photo()->str:
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

    def exec_code(code:str):
        try:
            d = dict(locals(), **globals())
            exec(code, d, d)
        except Exception as e:
            print("Code exec exception: ", e)

    def event_thread(cam, img_size):
        clock = pygame.time.Clock()
        # Set up display
        display = pygame.display.set_mode(img_size, 0)
        while True:
            clock.tick(24)
            if context['continuous_photo_mode']:
                while not cam.query_image():
                    pass
                lock.acquire()
                context['image'] = cam.get_image()
                lock.release()
                display.blit(context['image'], (0, 0))
                pygame.display.flip()
            else:
                pygame.event.wait()
            pygame.event.pump()

    def switch_user_voice():
        text_to_speech.switch_user_voice(voice_recognition.recorder)

    def revert_default_role():
        text_to_speech.revert_default_role()

    def switch_trump_role():
        text_to_speech.switch_trump_role()

    def switch_biden_role():
        text_to_speech.switch_biden_role()

    def switch_vader_role():
        text_to_speech.switch_vader_role()

    def switch_robot_role():
        text_to_speech.switch_robot_role()

    def main():
        global context, gemini_ai, voice_recognition, text_to_speech, lock, cam

        context['today'] = str(date.today())

        pygame.init()
        pygame.camera.init()

        gemini_ai = GeminiAI(name=keycode, system_instruction=instruction)
        voice_recognition = VoiceRecognition()
        text_to_speech = TextToSpeech()
        lock = threading.Lock()

        # Initialize camera
        camlist = pygame.camera.list_cameras()
        img_size = (420, 240)
        cam = None
        if camlist:
            cam = pygame.camera.Camera(camlist[0], img_size)

        # Start event thread
        threading.Thread(target=event_thread, args=(cam, img_size)).start()

        function_file = gemini_ai.upload_file(path="extern_api.py",
                                    display_name="Python API")
        talk_header = [
            {'role': 'user', 'parts': [function_file, 'This is the python APIs you can execute. To execute them, put them in python code snippet at the end of your response']},
            {'role': 'model', 'parts': ["Understood, I'll remember to always check this file for available API calls to execute."]}
        ]

        # Main loop
        sleeping = False

        print('\a')
        text_to_speech.speak(f"I'm {keycode}, how can I help you?")
        append2log('==================New=====================')
        try:
            while True:
                try:
                    if context['query_response'] == '':
                        context['attach_to_context_in_a_row'] = 0
                        text = voice_recognition.listen() if not keyboard_test_mode else input('Input: ')

                        if sleeping and keycode.lower() in text.lower():
                            sleeping = False
                        elif sleeping:
                            text_to_speech.speak('I am deactivated.')
                            continue

                        if text.lower() in ["that's all", "see you", "bye"]:
                            text_to_speech.speak("OK, see you soon.")
                            append2log('==========================================')
                            sleeping = True
                            continue

                    else:
                        text = context['query_response']
                        context['query_response'] = ''

                    # Handle continuous photo mode
                    if context['continuous_photo_mode']:
                        filename = 'camera.jpg'
                        lock.acquire()
                        pygame.image.save(context['image'], filename)
                        lock.release()
                        context['photo_file'] = gemini_ai.upload_file(path=filename,
                                            display_name="Photo")

                    parts = []
                    if context['photo_file']:
                        parts.append(context['photo_file'])
                    parts.append(text)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    parts.append(timestamp)

                    temp = talk_header + context['talk']
                    temp.append({'role': 'user', 'parts': parts})

                    print(f"You: {text}, {timestamp}")

                    # Process user's request
                    response = gemini_ai.generate_response(temp)
                    
                    print(f"AI: {response}")
                    
                    pythoncode = gemini_ai.extract_code(response)
                    voice_text = gemini_ai.strip_code(response)

                    if voice_text != '':
                        text_to_speech.stop()

                    # Handle any code execution from the response
                    thread = None
                    if(pythoncode != ''):
                        print(f'code: {pythoncode}')
                        thread = threading.Thread(target=exec_code, args=(pythoncode,))
                        # Start the thread
                        thread.start()

                    # Speak the response
                    text_to_speech.speak(voice_text)

                    # Update context
                    context['talk'].append({'role': 'user', 'parts': parts})
                    context['talk'].append({'role': 'model', 'parts': [response]})
                    if len(context['talk']) > MAX_HISTORY:
                        context['talk'] = context['talk'][-MAX_HISTORY:]

                    append2log(f"You: {parts}\n ")
                    append2log(f"AI: {response} \n")

                    if thread:
                        thread.join()
                except Exception as e:
                    print(e)
                    continue

        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            voice_recognition.cleanup()
            pygame.quit()

    main()