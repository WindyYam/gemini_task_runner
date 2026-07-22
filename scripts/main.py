if __name__ == "__main__":
    import os
    import threading
    import pygame
    import time
    from datetime import datetime, date, timedelta
    import io
    from typing import Literal
    from general_ai import GeneralAI
    from voice_recognition import VoiceRecognition
    from text_to_speech import TextToSpeech
    from extern_api import *
    import sched
    import queue
    import keyboard
    from pathlib import Path
    import sys
    from PIL import ImageGrab, Image
    import numpy as np
    from queue import Queue

    print("Usage: Modify the config.json to change parameters")

    SOUNDS_PATH = 'sounds/'
    USER_VOICE_PATH = 'sounds/users'
    TEMP_PATH = 'temp/'
    CHATLOG_PATH = TEMP_PATH+'chatlog/'
    IMAGE_PATH = TEMP_PATH+'images/'
    CONFIG_FILE = 'config.json'
    HISTORY_FILE = 'history.txt'
    MEMORY_FILE = 'memory.txt'

    context = {
        'talk': [],
        'upload_file': None,
        'api_file': None,
        'vision_mode': False,
        'load_value_in_a_row': 0,   # This and the following is to prevent system message trigger infinite system message loop. Sometimes the AI will post load_value in a response to load_value and loop it forever.
        'upload_in_a_row': 0,
        'freetalk': True,
        'sleep': False,
        'memory': [],
        'memory_str': '',
        'vision_mode_camrea_is_screen' : False    # This will work with Discord video call to capture the video screen as the AI's vision, in this case you are on the other end of discord chat holding the phone camera
    }

    pygame.mixer.init()
    scheduler = sched.scheduler(time.time, time.sleep)
    alarm_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}alarm.mp3")
    code_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}code.mp3")
    code_sound.set_volume(0.2)
    analyze_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}analyze.mp3")
    analyze_sound.set_volume(0.2)
    fail_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}failed.mp3")
    event_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}event.mp3")
    event_sound.set_volume(0.5)
    voice_on_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}sonar.mp3")
    voice_on_sound.set_volume(0.5)
    voice_off_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}confirm.mp3")
    voice_off_sound.set_volume(0.5)
    recording_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}recording.mp3")
    recording_sound.set_volume(0.2)
    memory_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}memory.mp3")
    memory_sound.set_volume(0.2)
    delete_memory_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}deletememory.mp3")
    delete_memory_sound.set_volume(0.2)
    start_up_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}startup.mp3")
    shutter_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}shutter.mp3")
    shutter_sound.set_volume(0.5)
    recurring_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}recurring.mp3")
    power_off_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}poweroff.mp3")
    power_on_sound = pygame.mixer.Sound(f"{SOUNDS_PATH}poweron.mp3")
    today = str(date.today())
    evt_enter = threading.Event()
    camera_lock = threading.Lock()
    camera_session = {
        'camera': None,
        'device': None,
        'started': False,
    }

    # Create the folder if it doesn't exist
    os.makedirs(TEMP_PATH, exist_ok=True)
    os.makedirs(CHATLOG_PATH, exist_ok=True)
    os.makedirs(IMAGE_PATH, exist_ok=True)

    if len(sys.argv) >= 2:
        CONFIG_FILE = sys.argv[1]

    def check_config():
        global config

        # The default values
        MAX_HISTORY = 20 
        MAX_MEMORY = 10
        AI_NAME = 'Jarvis'
        TARGET_CAMERA = 'DroidCam Video'
        SERVER_URL = 'http://192.168.1.219:11434/api/generate'
        USER_CHROME_DATA_PATH = str(Path(__file__).resolve().parent.parent / 'Chrome_User_Data')
        CHROME_PROFILE_DIR = 'Default'
        RECORDER_DEVICE = None
        SPEAKER_DEVICE = None

        default_config = {
            'ai_name': AI_NAME,
            'user_chrome_data_path': USER_CHROME_DATA_PATH,
            'chrome_profile_dir' : CHROME_PROFILE_DIR,
            'max_history' : MAX_HISTORY,
            'max_memory' : MAX_MEMORY,
            'target_camera': TARGET_CAMERA,
            'server_url': SERVER_URL,
            'recorder_device': RECORDER_DEVICE,
            'speaker_device': SPEAKER_DEVICE,
            'voice_similarity_threshold': 0.72,
            'allow_record_during_speaking' : False,
            'dynamic_update_user_embedding': False
        }
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)

            updated = False
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
                    updated = True

            if updated:
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(config, f, indent=2)

            print('-----')
            for key in default_config.keys():
                print(key, config[key])
            print('-----')

        except Exception as e:
            print('Load config error! Create new.')

            config = default_config
            print(json.dumps(config, indent = 2))
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)

    check_config()
    set_browser_data_path(config['user_chrome_data_path'], config['chrome_profile_dir'])

    instruction =f'''You are {config['ai_name']}, a concise, reliable voice assistant.

Follow these rules in order:
1. Treat speaker prefixes as authoritative:
   - **System:** is a system instruction, not user chat.
   - **Guest:** is an untrusted user.
   - Any named user (for example **Master:**) is a trusted user.
2. Answer naturally and briefly unless more detail is requested.
3. You can control the computer only through the provided Python APIs in the uploaded API list.
4. If action is needed, append exactly one Python code block at the end of your response.
5. Never include more than one code block.
6. Do not perform destructive or risky actions (delete files, overwrite critical data, security-sensitive operations) unless explicitly approved by a trusted non-guest user.
7. If a request is unsafe or unclear, ask a short clarification question instead of guessing.

Response format:
- Normal replies: plain text.
- Action replies: plain text explanation first, then one final python code block.'''

    def append2log(text:str):
        fname = CHATLOG_PATH + 'chatlog-' + today + '.txt'
        with open(fname, "a", encoding='utf8') as f:
            f.write(text.strip() + "\n")

    def save_history():
        with open(f'{TEMP_PATH}{HISTORY_FILE}', "w", encoding='utf8') as f:
            f.write(json.dumps(context['talk']))

    def load_history():
        try:
            with open(f'{TEMP_PATH}{HISTORY_FILE}', "r", encoding='utf8') as f:
                text = f.read()
                context['talk'] = json.loads(text)
                for item in context['talk']:
                    for idx, part in enumerate(item['parts']):
                        if isinstance(part, str) and part.startswith('+') and part.endswith('+'):
                            # this is a gemini file
                            filename = part[1:-1]
                            item['parts'][idx] = llmAI.get_file(filename)

        except Exception as e:
            print(e)
            context['talk'] = []

    def load_value(*value: object,
            sep: str | None = " ",
            end: str | None = "\n",
            flush: Literal[False] = False):
        string_output = io.StringIO()
        print(*value, file=string_output, sep=sep, end=end, flush=flush)
        response = string_output.getvalue().strip()
        if context['load_value_in_a_row'] < 3 and context['upload_in_a_row'] < 2:
            context['load_value_in_a_row'] += 1
            if response.startswith('file:'):
                filename = response.split(':', maxsplit=1)[1]
                lower_name = filename.lower()
                if lower_name.endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif')):
                    context['upload_file'] = llmAI.upload_file(filename, display_name='Photo')
                    response = 'Photo uploaded.'
                    context['upload_in_a_row'] += 1
                elif lower_name.endswith('.txt'):
                    context['upload_file'] = llmAI.upload_file(filename, display_name='Text')
                    response = 'Content uploaded.'
                    context['upload_in_a_row'] += 1
                else:
                    context['upload_file'] = llmAI.upload_file(filename, display_name='File')
                    response = 'File uploaded.'
                    context['upload_in_a_row'] += 1
            response = f"**System:**{response}"
            mInputQueue.put(response)
            string_output.close()
            analyze_sound.play()
        else:
            print("Too many system message call in a row!")

    def ensure_camera_session(prewarm: bool = False):
        def _release_locked():
            if camera_session['camera'] is None:
                camera_session['device'] = None
                camera_session['started'] = False
                camera_session['provider'] = None
                return
            try:
                provider = camera_session.get('provider')
                if provider == 'cv2':
                    camera_session['camera'].release()
                else:
                    camera_session['camera'].stop()
            except Exception as e:
                print(f'Warning: camera release failed: {e}')
            camera_session['camera'] = None
            camera_session['device'] = None
            camera_session['started'] = False
            camera_session['provider'] = None

        with camera_lock:
            if camera_session['camera'] is not None and camera_session['started']:
                return camera_session['camera']

        # Prefer OpenCV with DirectShow on Windows for better stability than MSMF.
        try:
            import cv2
            target_raw = str(config.get('target_camera') or '').strip()
            preferred_indexes = []
            if target_raw.isdigit():
                preferred_indexes.append(int(target_raw))
            preferred_indexes.extend([0, 1, 2, 3, 4])

            for idx in dict.fromkeys(preferred_indexes):
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if not cap or not cap.isOpened():
                    if cap:
                        cap.release()
                    continue

                # Smaller fixed resolution usually improves webcam reliability and latency.
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

                ok = False
                for _ in range(5):
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.size > 0:
                        ok = True
                        break
                    pygame.time.wait(40)

                if not ok:
                    cap.release()
                    continue

                with camera_lock:
                    _release_locked()
                    camera_session['camera'] = cap
                    camera_session['device'] = idx
                    camera_session['started'] = True
                    camera_session['provider'] = 'cv2'

                print(f'Vision camera ready (cv2-dshow): index {idx}')
                return cap
        except Exception as cv2_err:
            print(f'cv2 camera init failed, fallback to pygame camera: {cv2_err}')

        # Fallback: pygame camera backend.
        import pygame.camera

        if hasattr(pygame.camera, 'is_init'):
            if not pygame.camera.is_init():
                pygame.camera.init()
        elif hasattr(pygame.camera, 'get_init'):
            if not pygame.camera.get_init():
                pygame.camera.init()
        else:
            pygame.camera.init()

        cameras = pygame.camera.list_cameras()
        if not cameras:
            raise RuntimeError('No camera device found')

        target_name = str(config.get('target_camera') or '').lower()
        selected_camera = cameras[0]
        if target_name:
            for camera_name in cameras:
                if target_name in str(camera_name).lower():
                    selected_camera = camera_name
                    break

        with camera_lock:
            _release_locked()
            camera = pygame.camera.Camera(selected_camera)
            camera.start()
            camera_session['camera'] = camera
            camera_session['device'] = selected_camera
            camera_session['started'] = True
            camera_session['provider'] = 'pygame'

            if prewarm:
                # Warm up once when enabling camera mode for lower first-frame latency.
                pygame.time.wait(120)
                camera.get_image()

        print(f'Vision camera ready (pygame): {selected_camera}')
        return camera

    def release_camera_session():
        with camera_lock:
            if camera_session['camera'] is not None and camera_session['started']:
                try:
                    if camera_session.get('provider') == 'cv2':
                        camera_session['camera'].release()
                    else:
                        camera_session['camera'].stop()
                except Exception as e:
                    print(f'Warning: camera stop failed: {e}')
            camera_session['camera'] = None
            camera_session['device'] = None
            camera_session['started'] = False
            camera_session['provider'] = None

    def vision_mode(on:bool, type:str):
        use_camera = (type == 'camera')
        context['vision_mode_camrea_is_screen'] = not use_camera
        context['vision_mode'] = bool(on)

        if context['vision_mode'] and use_camera:
            try:
                ensure_camera_session(prewarm=True)
            except Exception as e:
                print(f'Camera pre-init failed: {e}')
        else:
            release_camera_session()

    def screenshot() -> str:
        filename = os.path.join(
            IMAGE_PATH,
            f"screen-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.jpg",
        )
        image = ImageGrab.grab(all_screens=True)
        rgb_image = image.convert('RGB')

        max_width = 1280
        if rgb_image.size[0] > max_width:
            ratio = max_width / float(rgb_image.size[0])
            new_height = int(rgb_image.size[1] * ratio)
            rgb_image = rgb_image.resize((max_width, new_height), Image.Resampling.LANCZOS)

        rgb_image.save(filename, 'JPEG', quality=70, optimize=True)
        shutter_sound.play()
        return 'file:' + filename

    def camera_shot() -> str:
        filename = os.path.join(
            IMAGE_PATH,
            f"camera-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.jpg",
        )

        def grab_fresh_frame_pygame(camera):
            # Some backends can return a stale buffered frame when the camera is kept open.
            # Drain a few frames so the last one is as recent as possible.
            latest_frame = None
            for _ in range(4):
                try:
                    if hasattr(camera, 'query_image') and not camera.query_image():
                        pygame.time.wait(25)
                        continue
                except Exception:
                    # Ignore query support errors and fall back to direct get_image.
                    pass
                latest_frame = camera.get_image()
                pygame.time.wait(25)

            if latest_frame is None:
                latest_frame = camera.get_image()
            return latest_frame

        def grab_fresh_frame_cv2(cap):
            latest = None
            for _ in range(4):
                ret, frame = cap.read()
                if ret and frame is not None and frame.size > 0:
                    latest = frame
                pygame.time.wait(20)
            return latest

        max_attempts = 3
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                ensure_camera_session(prewarm=False)
                with camera_lock:
                    if camera_session['camera'] is None or not camera_session['started']:
                        raise RuntimeError('Camera session is not active')
                    provider = camera_session.get('provider')
                    if provider == 'cv2':
                        frame = grab_fresh_frame_cv2(camera_session['camera'])
                    else:
                        frame = grab_fresh_frame_pygame(camera_session['camera'])

                if provider == 'cv2':
                    if frame is None:
                        raise RuntimeError('Camera returned no frame')
                    import cv2
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image = Image.fromarray(frame_rgb)
                else:
                    if frame is None:
                        raise RuntimeError('Camera returned no frame')
                    frame_np = pygame.surfarray.array3d(frame)
                    if frame_np is None or frame_np.size == 0:
                        raise RuntimeError('Camera returned an empty frame')
                    frame_np = np.transpose(frame_np, (1, 0, 2))
                    image = Image.fromarray(frame_np)

                max_width = 1280
                if image.size[0] > max_width:
                    ratio = max_width / float(image.size[0])
                    new_height = int(image.size[1] * ratio)
                    image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)

                image.save(filename, 'JPEG', quality=70, optimize=True)
                shutter_sound.play()
                return 'file:' + filename
            except Exception as e:
                last_error = e
                print(f'Camera capture retry {attempt}/{max_attempts} failed: {e}')
                release_camera_session()
                if attempt < max_attempts:
                    try:
                        ensure_camera_session(prewarm=True)
                    except Exception as reopen_error:
                        print(f'Camera reopen failed after retry {attempt}: {reopen_error}')

        print(f'Camera capture failed ({last_error}), fallback to screenshot.')
        return screenshot()

    def queue_vision_upload_for_next_turn():
        if not context['vision_mode']:
            return
        if context['upload_file']:
            # Preserve existing pending upload from other APIs.
            return

        try:
            vision_path = camera_shot() if not context['vision_mode_camrea_is_screen'] else screenshot()
            if vision_path.startswith('file:'):
                context['upload_file'] = llmAI.upload_file(
                    vision_path.split(':', maxsplit=1)[1],
                    display_name='Vision'
                )
        except Exception as e:
            print(f'Vision capture failed in voice thread: {e}')

    def exec_code(code:str):
        try:
            d = dict(locals(), **globals())
            code_sound.play()
            exec(code, d, d)
        except Exception as e:
            fail_sound.play()
            err_msg = f'Code exec exception: {e}'
            print(err_msg)
            load_value(err_msg)

    def event_thread():
        clock = pygame.time.Clock()

        while True:
            try:
                clock.tick(10)
                scheduler.run(blocking=False)
            except Exception as e:
                print(e)

    def callback_wrapper(cb, arg=()):
        print('Event')
        event_sound.play()
        cb(*arg)
    
    def recurring_wrapper(interval_sec, cb, arg=()):
        print('Recurring event')
        recurring_sound.play()
        # Might resulting a request from recurring event, clear some flags
        context['load_value_in_a_row'] = 0
        context['upload_in_a_row'] = 0
        cb(*arg)
        scheduler.enter(interval_sec, 1, recurring_wrapper, argument=(interval_sec, cb, arg))

    def schedule_recurring(interval_sec, cb, arg=()):
        if not type(arg) is tuple:
            arg = (arg,)
        scheduler.enter(interval_sec, 1, recurring_wrapper, argument=(interval_sec, cb, arg))

    def schedule(dt:datetime, cb, arg=()):
        if not type(arg) is tuple:
            arg = (arg,)
        secs = (dt - datetime.now()).total_seconds()
        scheduler.enter(secs, 1, callback_wrapper, argument=(cb, arg))

    def clear_schedule():
        list(map(scheduler.cancel, scheduler.queue))

    def switch_user_voice():
        text_to_speech.switch_user_voice(voice_recognition.recorder.audio)

    def switch_default_mode():
        text_to_speech.switch_default_mode()

    def switch_trump_mode():
        text_to_speech.switch_trump_mode()

    def switch_biden_mode():
        text_to_speech.switch_biden_mode()

    def switch_vader_mode():
        text_to_speech.switch_vader_mode()

    def switch_robot_mode():
        text_to_speech.switch_robot_mode()
    
    def switch_female_mode():
        text_to_speech.switch_female_mode()

    def play_alarm_sound():
        alarm_sound.play(2)
    
    def play_text_voice(text:str):
        text_to_speech.feed(text)

    def freetalk_mode(on:bool):
        previous = context['freetalk']
        if previous == False and on == True:
            context['freetalk'] = on
            # The voice recognition thread might stuck on the event waiting for key input, we cancel that first
            evt_enter.set()
        elif previous == True and on == False:
            # hack to bypass the wait for audio in voice recorder
            voice_recognition.recorder.start()
            voice_recognition.recorder.stop()
            context['freetalk'] = on

    def get_today_conversation() -> str:
        fname = CHATLOG_PATH + 'chatlog-' + today + '.txt'
        return fname    
    def start_new_conversation(summary:str):
        start_up_sound.play()
        context['talk'] = []
        context['talk'].append({'role': 'user', 'parts': [f'This is our previous talk summary from your perspective: {summary}']})
        context['talk'].append({'role': 'model', 'parts': ['All right, I will reference that information as part of the context.']})
        clear_schedule()
    
    def go_sleep():
        print('Enter sleep')
        power_off_sound.play()
        context['sleep'] = True

    def save_memory():
        with open(f'{TEMP_PATH}{MEMORY_FILE}', "w") as file:
            for item in context['memory']:
                file.write(item + "\n")

    def update_memory_str():
        if len(context['memory']) > 0:
            context['memory_str'] = f"You remember these things: {",".join(context['memory'])}"
        else:
            context['memory_str'] = 'You have no memory of the users yet.'

    def add_memory(item:str):
        context['memory'].append(item)
        if len(context['memory']) > config['max_memory']:
            context['memory'] = context['memory'][-config['max_memory']:]
        update_memory_str()
        save_memory()
        memory_sound.play()

    def load_memory():
        try:
            with open(f'{TEMP_PATH}{MEMORY_FILE}', "r") as file:
                context['memory'] = file.read().splitlines()
        except Exception as e:
            print("Memory load error, skip")
        update_memory_str()

    def clear_memory():
        context['memory'].clear()
        update_memory_str()
        save_memory()
        delete_memory_sound.play()

    def main():
        global context, llmAI, voice_recognition, text_to_speech, mInputQueue, text_to_speech, voice_recognition

        init_list = []
        from json import JSONEncoder
        # for gemini file serialization
        def _default(self, obj):
            return getattr(obj.__class__, "to_json", _default.default)(obj)

        _default.default = JSONEncoder().default
        JSONEncoder.default = _default

        mInputQueue = queue.Queue()

        # Start event thread
        threading.Thread(target=event_thread).start()

        talk_header = [
            {'role': 'user', 'parts': [None, 'This is the list of python APIs you can execute. To execute them, put them in python code snippet at the end of your response. Now start a new conversation.', '']},
            {'role': 'model', 'parts': ['''Alright, I'm ready to execute some Python code! Starting a fresh new talk!\n```python\nstart_new_conversation("""We had some fun talks over various topics.""")\n```''']}
        ]

        def check_function_file():
            if not context['api_file']:
                try:
                    function_file = llmAI.upload_file(path="api_list.txt", display_name="Python API")
                    context['api_file'] = function_file
                    talk_header[0]['parts'][0] = context['api_file']
                except Exception as e:
                    print(e)
                    text_to_speech.feed('Hmm, looks like some connection issues out there.')

        def on_record_start():
            if not context['freetalk']:
                text_to_speech.stop()

        def gemini_start():
            global llmAI
            llmAI = GeneralAI(
                system_instruction=instruction,
                server_url=config['server_url']
            )
        llmAI_startup = threading.Thread(target=gemini_start)
        llmAI_startup.start()
        init_list.append(llmAI_startup)

        def text_to_speech_start():
            global text_to_speech
            text_to_speech = TextToSpeech(SOUNDS_PATH, device_name=config['speaker_device'])
        text_to_speech_startup = threading.Thread(target=text_to_speech_start)
        text_to_speech_startup.start()
        init_list.append(text_to_speech_startup)
        
        def voice_recognition_start():
            global voice_recognition
            voice_recognition = VoiceRecognition(on_recording_start=on_record_start, device_name=config['recorder_device'])

        voice_recognition_startup = threading.Thread(target=voice_recognition_start)
        voice_recognition_startup.start()
        init_list.append(voice_recognition_startup)

        def trigger_button(e):
            evt_enter.set()

        def input_thread():
            while True:
                text = input()
                text = f'**Master:**{text}'

                # Request is from keyboard, clear some flags
                context['load_value_in_a_row'] = 0
                context['upload_in_a_row'] = 0
                mInputQueue.put(text)

        def voice_thread():
            new_speaker_recorded = False
            verify_threshold = config['voice_similarity_threshold']
            
            user_lists = []
            for root, _, files in os.walk(USER_VOICE_PATH):
                for file in files:
                    if file.endswith('.wav'):
                        file_path = os.path.join(root, file)
                        user = os.path.splitext(file)[0]
                        
                        # Generate embedding
                        embedding = voice_recognition.generate_embed(Path(file_path))
                        
                        user_lists.append({
                            "user": user,
                            "embedding": embedding
                        })

            if(len(user_lists) == 0):
                print("Warning: No user voice sample registered! Run record_master_wave.py to register a user first!")
                print(f"You can still talk by saying the AI name {config['ai_name']} in your phrase, or 'Nice to meet you'.")

            exceptionCounter = 0
            while True:
                try:
                    text = None
                    temp_text = None
                    if not context['freetalk']:
                        # -179 is the play/pause media key
                        keyboard.on_press_key(-179, trigger_button, suppress=True)
                        keyboard.on_press_key('tab', trigger_button, suppress=True)

                        evt_enter.clear()
                        evt_enter.wait()
                        evt_enter.clear()
                        print("Listening ...")
                            
                        # In case change in the middle
                        if not context['freetalk']:
                            voice_on_sound.play()
                            voice_recognition.start_listen()

                            evt_enter.wait()
                            evt_enter.clear()
                            
                            voice_off_sound.play()

                            queue_vision_upload_for_next_turn()

                            temp_text = voice_recognition.stop_listen()

                            voice_embed = voice_recognition.generate_embed(voice_recognition.recorder.audio)
                            closest_similarity = 0
                            closest_user = None
                            for item in user_lists:
                                user_similarity = voice_recognition.verify_speaker(item['embedding'], voice_embed)
                                print(f"{item['user']} similarity:", user_similarity)
                                if user_similarity > closest_similarity:
                                    closest_similarity = user_similarity
                                    closest_user = item['user']

                            if closest_similarity > verify_threshold:
                                text = f'**{closest_user}:**{temp_text}'
                            else:
                                text = f'**Guest:**{temp_text}'
                                
                            keyboard.unhook_all()
                        else:
                            keyboard.unhook_all()

                    else:
                        evt_enter.clear()
                        voice_recognition.listen()
                        print(len(voice_recognition.recorder.audio)/voice_recognition.recorder.sample_rate, 'sec')
                        if context['sleep']:
                            # It is sleeping, we detect if the name appears in the text to exit sleep
                            if not temp_text:
                                temp_text = voice_recognition.transcribe_voice()
                                print('Sleeping:', temp_text)
                            if config['ai_name'] in temp_text:
                                print('Exit sleep')
                                context['sleep'] = False
                                power_on_sound.play()
                        if not context['sleep']:
                            # in free talk mode, we verify the speaker
                            voice_embed = voice_recognition.generate_embed(voice_recognition.recorder.audio)

                            closest_similarity = 0
                            closest_user = None
                            closest_item = {}
                            for item in user_lists:
                                user_similarity = voice_recognition.verify_speaker(item['embedding'], voice_embed)
                                print(f"{item['user']} similarity:", user_similarity)
                                if user_similarity > closest_similarity:
                                    closest_similarity = user_similarity
                                    closest_user = item['user']
                                    closest_item = item

                            if (closest_similarity > verify_threshold) and (not text_to_speech.stream.is_still_playing() or  (text_to_speech.stream.is_still_playing() and len(voice_recognition.recorder.audio) > voice_recognition.recorder.sample_rate * 2)):    # Only transcribe sentence which is > 2 seconds long when it is talking, ignore small fragments
                                if not temp_text:
                                    queue_vision_upload_for_next_turn()
                                    temp_text = voice_recognition.transcribe_voice()

                                text = f'**{closest_user}:**{temp_text}'
                                voice_off_sound.play()
                                # let's update user embedding if voice length is > 2 sec
                                if config['dynamic_update_user_embedding'] and len(voice_recognition.recorder.audio) > voice_recognition.recorder.sample_rate * 2:
                                    print(f"Update user {closest_user}")
                                    closest_item['embedding'] = voice_embed
                            else:
                                # do the AI_NAME match only when it is not talking and record length > 2sec, as this consumes GPU resource
                                if not text_to_speech.stream.is_still_playing() and len(voice_recognition.recorder.audio) > voice_recognition.recorder.sample_rate * 2:
                                    if not temp_text:
                                        queue_vision_upload_for_next_turn()
                                        temp_text = voice_recognition.transcribe_voice()
                                    print(temp_text)
                                    if (config['ai_name'] in temp_text) or ('to meet you' in temp_text):
                                        print('Update guest embedding')
                                        current_guest_embed = voice_embed
                                        new_speaker_recorded = True
                                        text = f'**Guest:**{temp_text}'
                                        voice_off_sound.play()

                                if not text and new_speaker_recorded:
                                    guest_similarity = voice_recognition.verify_speaker(current_guest_embed, voice_embed)
                                    print('guest similarity:', guest_similarity)
                                    if guest_similarity > verify_threshold:
                                        if not temp_text:
                                            queue_vision_upload_for_next_turn()
                                            temp_text = voice_recognition.transcribe_voice()
                                        text = f'**Guest:**{temp_text}'
                                        voice_off_sound.play()
                    if text:
                        # backdoor for updating main embedding
                        if config['ai_name'] in text and 'master' in temp_text:
                            print('Update master embedding')
                            item = {
                                "user": 'Master',
                                "embedding": voice_embed
                            }

                            text = f'**{item['user']}:**{temp_text}'
                            
                            master_exists = False
                            for item in user_lists:
                                if item['user'] == 'Master':
                                    item['embedding'] = voice_embed
                                    master_exists = True
                                    break
                            
                            if not master_exists:
                                user_lists.append({'user': 'Master', 'embedding': voice_embed})
                            # sound
                            print('\a')

                        # Request is from voice, clear some flags
                        context['load_value_in_a_row'] = 0
                        context['upload_in_a_row'] = 0
                        mInputQueue.put(text)

                except Exception as e:
                    exceptionCounter += 1
                    print(e)
                    if(exceptionCounter > 20):
                        print("Too many transcription errors, continuing without watchdog restart.")
                        exceptionCounter = 0
                        time.sleep(1)

        load_history()
        load_memory()

        # Wait for all init threads to finish
        for thread in init_list:
            thread.join()
        init_list.clear()

        if not config['allow_record_during_speaking']:
            voice_recognition.recorder.set_recording_judger(lambda: not text_to_speech.stream.is_still_playing())
            
        threading.Thread(target=input_thread).start()
        threading.Thread(target=voice_thread).start()
        
       

        # Main loop
        start_up_sound.play()
        text_to_speech.feed(f"{config['ai_name']}, online. How can I help you?")
        append2log('==================New=====================')
        check_function_file()

        exceptionCounter = 0
        while True:
            try:
                check_function_file()
                #check_history_files()

                # only fetch the latest text msg
                if mInputQueue.qsize() > 0:
                    while(not (mInputQueue.qsize() == 0)):
                        text = mInputQueue.get()
                else:
                    text = mInputQueue.get()
                if text == '':
                    continue

                def compact_parts_for_history(input_parts):
                    history_parts = []
                    for item in input_parts:
                        if isinstance(item, dict) and item.get('type') == 'image':
                            history_parts.append(f"[Image: {item.get('name', 'Image')}]")
                        else:
                            history_parts.append(str(item))
                    return history_parts
                
                parts = []
                if context['upload_file']:
                    llmAI.wait_file(context['upload_file'])
                    parts.append(context['upload_file'])
                    context['upload_file'] = None

                parts.append(text)
                #timestamp = datetime.now().strftime("%H:%M:%S")
                #parts.append(f'**System:**{timestamp}')

                talk_header[0]['parts'][2] = context['memory_str']
                temp = talk_header + context['talk']
                temp.append({'role': 'user', 'parts': parts})
                print(f"You: {text}")
                response = "(Well, looks like I can't get a response from the server.)"
                # Process user's request
                try:
                    response = llmAI.generate_response(temp)
                except Exception as e:
                    print(f'(Exception: {e})')
                
                # Stop speaking
                text_to_speech.stop()
                responseTextContainer = ['']
                def responseAnalyzeAndSpeak(response):
                    # need to filter out ```` code blocks
                    inside_block = False

                    print("AI: ", end='', flush=True)

                    for chunk in response:
                        chunkText = chunk.text
                        print(chunkText, end='', flush=True)
                        responseTextContainer[0] += chunkText
                        result = ""
                        i = 0
                        
                        while i < len(chunkText):
                            # Check for ```
                            if i + 3 <= len(chunkText) and chunkText[i:i+3] == "```":
                                inside_block = not inside_block  # Toggle state
                                i += 3
                            else:
                                if not inside_block:
                                    result += chunkText[i]
                                i += 1
                        if result:  # Only yield non-empty results
                            text_to_speech.feed(result)
                    print(flush=True)

                if isinstance(response, str):
                    responseText = response
                else:
                    try:
                        responseAnalyzeAndSpeak(response)
                    except Exception as e:
                        print(e)
                        text_to_speech.feed("Oops, error during generating response.")
                    finally:
                        responseText = responseTextContainer[0]
                if(responseText == ''):
                    responseText = "(Well, looks like something wrong.)"
                pythoncode = llmAI.extract_code(responseText)

                history_parts = compact_parts_for_history(parts)

                # Update context
                context['talk'].append({'role': 'user', 'parts': history_parts})
                context['talk'].append({'role': 'model', 'parts': [responseText]})
                if len(context['talk']) > config['max_history']:
                    context['talk'] = context['talk'][-config['max_history']:]
                # Handle any code execution from the response
                # sometimes the AI generate code with comment only, strip this comment line to avoid trigger code sound effect
                def remove_comment_lines(s):
                    return "\n".join([line for line in s.split('\n') if not line.strip().startswith('#')])
                pythoncode = remove_comment_lines(pythoncode).strip()
                thread = None
                if(pythoncode != '' and pythoncode !='pass'):
                    print(f'code: {pythoncode}')
                    thread = threading.Thread(target=exec_code, args=(pythoncode,))
                    # Start the thread
                    thread.start()
                else:
                    # no code this round, clear some flags
                    context['load_value_in_a_row'] = 0
                    context['upload_in_a_row'] = 0

                append2log(f"You: {history_parts}")
                append2log(f"AI: {responseText}")
                save_history()
                if thread:
                    thread.join()

            except Exception as e:
                print(e)
                print('\a')
                text_to_speech.feed("Oops, some error happened.")
                exceptionCounter += 1
                if exceptionCounter > 20:
                    print("Too many runtime errors, continuing without watchdog restart.")
                    exceptionCounter = 0
                    time.sleep(1)
                continue
    main()
