# Gemini Voice Companion

Gemini Voice Companion is a Python-based voice assistant that offers a wide range of voice-controlled features and capabilities. This project leverages advanced speech recognition and synthesis technologies to create a versatile and interactive voice assistant, all without lifting a finger.

This app is best for users who crave hands-free convenience.  Seamlessly access information and control your devices with just your voice while your hands are on other activities.
Or, if you are the one who like to get eyes a bit of rest while still want to explore the internet world, then this will be the perfect choice for you.

Specially, this App mainly aimed and optimized for in car usage and entertainment, which takes the noise and unwanted voice from your car navigation system into consideration. Either access from a laptop in car, or a laptop in house <- discord -> mobile phone in car(either bluetooth to car in call mode, or you mignt want a wired cable audio output & input to your car as bluetooth call mode audio quality is bad).

Currently test on Windows only.
My Laptop is nVidia RTX A500 with 4GB VRAM. So in `voice_recognition.py` I am using the small model of whisper. If your PC is rich in VRAM don't hesitate to use the `large-v2` one.

Quick Rundown: https://youtu.be/6eXayNvU6ds
Introduction: https://youtu.be/6NTnIVsfiNM
In-car usage: https://youtu.be/Fer7pBjVmyA
Answer phone call(remote usage): https://youtu.be/kon9clc4MDQ
Discord Video Vision: https://youtu.be/La9BApz4LbY

## Core dependencies

- **Gemini**: The gemini 1.5 flash API
- **Real-time Speech-to-Text (STT)**: Converts spoken words into text in real-time.
- **Real-time Text-to-Speech (TTS)**: Generates natural-sounding speech from text.
- **Fast Whisper**: The multi-language voice to text engine.
- **Coqui xTTS**: The powerful text-to-speech AI engine.
- **Resemblyzer**: For voice similarity and recognition.
- **Selenium**: For Google Chrome autonomous.

## Features

- **Multi-Language**: For now the supported language is English and Chinese only. Support them to be in a mixed manner.
- **Multi-User Recognition**: Distinguish between different users based on voice samples, the extra benefit of this is it will filter out ambient voice or voice like noise.
- **Voice Switching**: Change the companion's voice on command (e.g., mimic user's voice, switch to Darth Vader's voice. See `api_list.txt` for more.).
- **House Managing**: Smart house like operation through voice command. It is simulated by pygame as a simple GUI. You can open door, turn on light, etc.
- **Reminder Schedule**: Schedule a voice reminder or an alarm at specific time, or any other activity. You can actually do anything with scheduling, like playing music at specific time, take screenshot at specific time and analyze as well.
- **Recurring Schedule**: Schedule recurring function call at specific interval. You can use this to make AI chat proactively in fixed interval(by using system message to initiate the talk instead of you). E.g. "Now schedule a recurring system message saying 'tell the user some jokes' every 30 seconds", or "Now schedule a recurring PC screenshot and analyze it every minute". You can ask AI companion to clear all the schedule once you're done with it.
- **Information Lookup**: Search for information on the internet, like weather, news.
- **Navigate Browser**: Use together with information lookup, you can navigate to the search result webpage, e.g. news, youtube page, Wikipeda. 
- **Summarize Webpage**: Use together with information lookup, you can ask the AI to get the content from static webpage and summarize it.
- **YouTube Music Integration**: Play and control music on YouTube Music.
- **Google Map Functions**: Some simple google map functions, like locate yourself, search for nearby stores. To use this, keep in mind that Google Map on your PC doesn't have GPS location. To access your location, you can let it access your mobile phone's, by login in Chrome and your mobile Google Map with the same account, and keep your mobile google map on, then the Google Map on PC will be able to locate you with your device. You might ask what's the point to locate yourself if you already open Google Map on your mobile, well, simply so that the AI can talk based on your location context.
- **PC Keyboard Control**: Type content onto your PC using voice commands.
- **Take Picture**: Either take a photo from the camera, or take a screenshot of your PC, which will then get uploaded to gemini. For better experience, recommend to download ```DroidCam https://droidcam.app/``` to turn your mobile phone into a camera. Update: DroidCam has some issue in getting camera frames when it is not in vision mode. Now since discord can do video call that turn your mobile phone into camera, the recommend way of using the mobile phone camera is discord mobile video call -> PC discord preview fullscreen -> ask AI on PC to take screenshot and analyze.
- **Vision Mode**: Record a video for AI inference when you are talking, either from the camrea or from screen record (if you are doing discord video chat with the AI, the screen record mode let the AI see the camera video from your mobile phone)
- **Write Diary Entry**: It can upload the conversation history today and then you can ask the AI to write diary entry based on that. You will have to explicitly ask the AI to access the history for reference(it is recommended to start a new conversation for AI after that as the history file can be huge which slows down the subsequential requests).
- **Memorize Information**: It can memorize information and save locally, like the user's preference on music, user's family informations. You can explicitly ask it to remember something or write something down. The max number of memory items can be adjusted in `config.json`
- **Analyze a general file**: It can upload and analyze a general file (in supported format, like jpg, png, pdf, txt etc.) under a file path of your PC. e.g. Summarize the content of file in "C:/example.txt". (It might be better to use other way like the keyboard to type in the path, or use some indirect way to provide the path, as voice is not very helpful in inputing path here)

- For more detail of the API it can use, see the api_list.txt.

## Installation

Make sure your nVidia graphic card is in latest driver.  
Download this repo and put all the content into a folder.  
Then first, install Python 3.12 from https://www.python.org/downloads/ (might work with other version but not tested).  
After that, simply run `setup.bat` to install all dependencies.  
Added: You might also need to install cuDNN for some libraries if you encounter ops64_9.dll issue. https://developer.nvidia.com/cudnn-downloads. And don't forget to add the environment PATH `C:\Program Files\NVIDIA\CUDNN\v9.8\bin\12.8`

## Usage

1. This is Google Gemini AI which has free tier usage enough for a single user. I'm not gonna use my API key here (unless I'm going to charge you for the excess usage beyond free tier). So you should get the (free) Gemini API key here `https://aistudio.google.com/app/apikey` and either:   
  (recommended) put it in environment variable as GEMINI_API_KEY (please search for detail on how to add environment variable if you are not familiar with). Or  
  (not recommended) do nothing, and `run.bat` will prompt you to enter GEMINI_API_KEY at the beginning every time.
2. Run `manage_user.bat` to add/delete user voice for AI to recognize. You can add multiple users.
3. Use any text editor to open and configure through `config.json` for several parameters. You should modify `user_chrome_data_path` to point to your chrome user profile. You can't use default profile for this, either copy your chrome user profile to somewhere like `C:/YourCustomProfileFolder/MyProfile`, or use command: `PATH_TO_YOUR_CHROME/chrome.exe --user-data-dir="C:/YourCustomProfileFolder/MyProfile" --profile-directory="Default"` to create a new one. Then copy the path `C:/YourCustomProfileFolder/MyProfile` to replace the existing in `user_chrome_data_path`.
4. Run `run.bat`. Make sure you've GEMINI_API_KEY variable in step 1.
5. When using Chrome related features(such as playing YouTube Music, navigate webpage), make sure you have Google Chrome installed, YouTube Music accessible in Chrome, and Chrome is closed before doing AI Chrome features.

### Web Chat Mode (LAN)

You now have a second way to use the assistant from devices in your local network through a browser UI.
This web server is a frontend process only. It forwards requests to the existing chatbot loop in `scripts/main.py`, so all existing behavior (history, code execution, memory, APIs) stays in one backend.

1. Start the main assistant with `run.bat`.
2. Ask the assistant to start web mode by calling:
  `start_web_chat_server(host="0.0.0.0", port=8765, prefix="Master")`
  (or run `run_web.bat` in another terminal after main is already running)
3. Open `http://YOUR_PC_LAN_IP:8765` from another device on the same network.
4. Use text chat directly in the page.
5. Use voice chat with the **Start Voice** button (browser speech recognition + browser speech playback).
6. Set your own chat name prefix in the top input (for example `Master`, `Guest`, `Alex`).

Bot voice in web mode now uses the backend chatbot TTS stream (WebSocket audio), not browser TTS.

- Turn on `Bot Voice` in the web UI to request backend voice output for web chat turns.
- On mobile browsers, tap a UI button first (for example `Bot Voice` or `Start Voice`) so audio playback is allowed by browser autoplay policy.
- Audio stream endpoint is served from the backend on `web_audio_ws_port` (default `8790`).

Related config fields in `config.json`:
- `web_host`
- `web_default_prefix`
- `web_ipc_host`
- `web_ipc_port`
- `web_ipc_auth`
- `web_audio_ws_host`
- `web_audio_ws_port`

### Modes

- **Free Talk Mode** (Default): The companion listens continuously for commands.
- **Trigger Mode**: Disable free talk mode by saying "Turn off free talk mode". Then use:
  - Tab key or media play/pause key to start speaking
  - Press the same key again to stop and get a response
- **Vision Mode**: In this mode, During your talk period, a video will be recorded as well to provide a vision like context for the AI inference. You can ask the AI to switch to screenshot vision mode instead of default camrea vision mode, which works very well with Discord fullscreen video chat (you are the one to video chat with the AI). The downside is that video has some overhead for processing, thus introduces several seconds' delay. (Gemini samples video in 1 FPS, so our output video is 1 FPS as well, but to stuff more movement we made the video in 4x slow motion)
- **Sleep Mode**: Tell the companion to go to sleep, it will not react to any voice activity. Only work in Free Talk mode. To wake it up again, use a phrase which contains its name. As usual, longer phrase have better recognition.

### Activating your voice

- For the main users, the voice is already recognized by the setup voice samples in ## Usage 2.
- For a guest that is not in the list, the default keyword is "Jarvis"(Or AI_NAME if you modified it), or "Nice/Pleased/Good/Ok/xxx to meet you". Use it in a phrase long enough to generate a voice embedding(at least > 2 sec), so the AI can recognize the voice subsequentially without the keyword.
- For guest, once activated, the companion will recognize the current user until another guest replace it.
- All guests that are not main users, Gemini will not react to the house commands from them. But will still help with other commands.
- Keep in mind, if you change the recorder device (like from a microphone to a VoIP output), the system might have problem recognize your voice, so you might need to record in ## Usage 2 again with new recorder device(as a new user with different voice sample).
- Or, a backdoor to temporarily setup a master user embedding is to say: "Jarvis(Or AI_NAME if you modified it), ... I'm your master ..." (As long as the phrase have AI_NAME and master together), this will force to update the main embedding no matter who is speaking(A notification sound will play). 

## Customization

- Just remove default.json, and put a default.wav of whatever voice you want the API to be like. Thanks to Coqui xTTS powerful ability to mimic voice.

## Tip

- The Free talk mode does continuous voice sample analysis thus is (slightly more) energy hunger if you are taking your laptop with only battery and in noisy environment. The trigger mode works better in this scenario.
- You can setup your PC to make Gemini answer Discord voice call/video call, in this case you are accessing the AI service remotely with your mobile phone, which is a huge benefit. See the Answer Phone Call youtube introduction ahead.
- Sometimes Gemini can be carried away by the context thus forgot to call function for a specific task, you should remind it about the function access like "Have you forgot you had function API access?". I have no good solution to this yet. You can simply ask AI to start new conversation if it goes too deep. If it fails to understand even this, tell it explicitly "call the start new conversation function".
- Normally, longer phrase can be easier for the voice recognition.
- The voice break to consider as a speech is short, so try to avoid long break in one speech. If you do want to extend it, try connect with voice like "eh.." instead of blank.
- If you find the voice recognition fails too many times, consider re-record your voice sample or lower the 'voice_similarity_threshold' field in `config.json`
- If you use it in a external speaker & mic, and your audio adapter doesn't have good echo cancellation (You notice it constantly recognize itself's voice through its own voice, due to your voice sample similar to AI's), turn off the flag `allow_record_during_speaking` in the config.json file so it only record when it finishes talking.
- To remove a user voice sample, simply delete file in sounds/users
- The AI companion has some memory bank for you to craft with. You can access it in temp/memory.txt. You can add items like "Zhenya's favourite artist is xxx", "The guest user's real name is Tony Stark", "Zhenya wants to hear laughs at the beginning of every reply.". The other way is to use voice command to ask the AI to add memory item.

## Contributing

## License

## Acknowledgements

---

Note: This project is under active development. Features and usage instructions may change. Please check for updates regularly.