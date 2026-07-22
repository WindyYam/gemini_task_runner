import requests
import json
import base64
import mimetypes
import os


class GeneralAI:
    def __init__(
        self,
        system_instruction,
        server_url="http://192.168.1.219:11434/api/generate",
        model="qwen3.5:9b",
        think=False,
    ):
        self.server_url = server_url
        self.system_instruction = system_instruction
        self.model = model
        self.think = think
        self.session = requests.Session()  # Use a session for connection pooling
        self.session.headers.update(
            {"Connection": "keep-alive", "Keep-Alive": "timeout=30, max=100"}
        )

    @staticmethod
    def _extract_text_from_item(item):
        if item is None:
            return ""
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            if item.get("type") == "image":
                name = item.get("name", "Image")
                return f"[{name} attached]"
            content = item.get("content")
            if isinstance(content, str):
                return content
            return str(item)
        return str(item)

    @staticmethod
    def _extract_content(part):
        if "parts" in part and isinstance(part.get("parts"), list):
            return "\n".join(
                [
                    GeneralAI._extract_text_from_item(p)
                    for p in part.get("parts", [])
                    if p is not None
                ]
            )

        content = part.get("content", "")
        if isinstance(content, list):
            return "\n".join(
                [GeneralAI._extract_text_from_item(p) for p in content if p is not None]
            )
        if content is None:
            return ""
        return str(content)

    @staticmethod
    def _collect_images(part):
        images = []
        containers = []
        if "parts" in part and isinstance(part.get("parts"), list):
            containers.extend(part.get("parts", []))
        content = part.get("content")
        if isinstance(content, list):
            containers.extend(content)

        for item in containers:
            if isinstance(item, dict) and item.get("type") == "image" and item.get("data"):
                images.append(item["data"])
        return images

    def _build_prompt(self, parts):
        prompt_lines = []
        if self.system_instruction:
            prompt_lines.append(f"System: {self.system_instruction}")

        for part in parts:
            role = part.get("role", "user")
            content = self._extract_content(part)
            if not content:
                continue
            prompt_lines.append(f"{role.capitalize()}: {content}")

        prompt_lines.append("Assistant:")
        return "\n\n".join(prompt_lines)

    def generate_response(self, parts: list):
        prompt = self._build_prompt(parts)
        images = []
        for part in parts:
            images.extend(self._collect_images(part))

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "think": self.think,
        }
        if images:
            payload["images"] = images
        try:
            with self.session.post(
                self.server_url, json=payload, stream=True, timeout=120
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    text = chunk.get("response", "")
                    if text:
                        yield type("Chunk", (), {"text": text})()

                    if chunk.get("done"):
                        break
        except Exception as e:
            # Yield a single error chunk
            yield type(
                "Chunk", (), {"text": f"Error communicating with LLM server: {e}"}
            )()

    @staticmethod
    def extract_code(input_string):
        start = input_string.find("```python")
        startlen = 9
        if start == -1:
            # The AI will sometimes try tool_code instead of python
            start = input_string.find("```tool_code")
            startlen = 12
        end = -1
        if start >= 0:
            start = start + startlen
            end = input_string.find("```", start)
        if start == -1 or end == -1:
            return ""
        return input_string[start:end]

    @staticmethod
    def strip_code(input_string):
        start = input_string.find("```python")
        if start == -1:
            # The AI will sometimes try tool_code instead of python
            start = input_string.find("```tool_code")
        end = input_string.find("```", start + 9)
        if start == -1 or end == -1:
            return input_string
        return input_string[:start] + input_string[end + 3 :]

    def upload_file(self, path, display_name):
        suffix = os.path.splitext(path)[1].lower()
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}:
            with open(path, "rb") as f:
                data = f.read()
            mime_type = mimetypes.guess_type(path)[0] or "image/jpeg"
            return {
                "type": "image",
                "name": display_name,
                "mime_type": mime_type,
                "data": base64.b64encode(data).decode("ascii"),
            }

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"{display_name}: {content}"

    def get_file(self, name):
        return ""

    def wait_file(self, fileD):
        pass


def main():
    # System instruction for the AI
    system_instruction = "You are a helpful assistant."
    ai = GeneralAI(system_instruction)

    # Conversation history in the required format
    conversation = [
        {
            "role": "system",
            "content": "Your name is Jarvis.You are a well educated and professional assistant, have great knowledge on everything. Keep in mind that there can be multiple users speaking. If it is a main master user, his/her name will be as prefix. If it is a guest, there will be a **Guest:** prefix, attached at the beginning of request. If the request message is with prefix **System:** then it means this message is from the system, not the user. \n        You have the interface on physical world through python code, there are several python function APIs to interact with the physical world. The list of which is in the uploaded text list file. \n        To execute the python code, put the code as python snippet format at the end of the response, then any code in the snippet in response will be executed. Only one code snippet per response is allowed.\n        To operate with the PC, use the python code execution with necessary library. But do not do potentially harmful operations, like deleting files, unless get the non guest users' permission. \n        You are to answer questions in a short concise and always humorous way, and talk more casual and use more expressive words that talks more lively, like haha, oh, wow, hmmm.",
        },
        {
            "role": "user",
            "content": "Python API: # This file contains python APIs to be used in code snippet for execution\n# The code in python code snippet in your response will get automatically executed\n# To get the execution result in the python code, call load_value(val) on the value, the system will send the value content to you.\n\n##########################################################\n# You can control the house\n# The following are the APIs for controlling the house appliance\n##########################################################\n# control light on and off\nlight(on:bool)\n\n# control door open and close\ndoor(open:bool)\n\n# control the air conditioner in celsius degree\nsetAirConditioner(temp:float)\n\n# set fan speed, range from 0 to 100\nsetFanSpeed(speed:int)\n\n# check for all house smart appliance status\ngetHouseStatus()->str\n\n##########################################################\n# You can get the real world information using these APIs\n# The following are the APIs for searching and reading through the web\n# To read information you must always use load_value(str) on the returned info\n##########################################################\n# get the current city name\ngetCity()->str\n\n# online search for any information from web search engine, e.g. news, weather, which returns several links and brief descriptions. \n# typical usage: load_value(webSearch(query))\n# after the search, always get more detail by get_webpage_text() call to the most relative link from the search result. \n# to get multiple web contents in one go, combine the text into a dict and then call load_value(dict)\n# after getting detail, summarize the highlights from all the gathered information in a short concise way.\n# if it returns empty result, it is high likely the user need to solve the CAPTCHA in duckduckgo.\nwebSearch(query:str)->str\n\n# get webpage content text. always call this to get the detail on the most relevant link after web search. \n# typical usage: load_value(get_webpage_text(url)) or load_value(['webA':get_webpage_text(urlA), 'webB':get_webpage_text(urlB)])\nget_webpage_text(url:str)->str\n\n# take a photo through the camera. this return the photo image. \n# typical usage: load_value(camera_shot())\ncamera_shot() -> str\n\n# take the screenshot of the PC you are running on, return the photo image. \n# typical usage: load_value(screenshot())\nscreenshot() -> str\n\n# get text content from PC's clipboard\nget_clipboard_text() -> str\n\n##########################################################\n# Python library access you have\n#########################################################\n# for http request\nimport request\n\n# for time and date\nfrom datetime import datetime, date, timedelta\n\n##########################################################\n# You can interact with the system, such as camera, voice output, music player, memory, keyboard, etc.\n# The following are the APIs to interact with the system\n##########################################################\n# Get the code execution result. Call this on a variable will give variable content. Call this on an image will give you image. Call this on a general file path with prefix \"file:\" will give you file content.\n# You can use this function on any API call that returns a result value to get the execution result. \n# be aware: can only be used once per snippet. If you want to get multiple values, combine the values into a dict and then call load_value(dict)\nload_value(value)\n\n# turning on/off vision mode so it will attach a photo on every request to you as your vision, arg on is True/False, type can be 'camera' or 'screenshot' to indicate image source. When vision mode is set on, you don't need load_value() for the photo\nvision_mode(on, type)\n\n# switch voice system to user voice to mimic the user's voice tone only, and your personality keeps unchanged.\nswitch_user_voice()\n\n# switch voice system to Donald Trump's voice tone. After this call, you would be Donald Trump as well.\nswitch_trump_mode()\n\n# switch voice system to Joe Biden's voice tone. After this call, you would be Joe Biden as well.\nswitch_biden_mode()\n\n# switch voice system to a robot's voice tone. After this call, you would behave like a robot, but without pause and beep sound in response.\nswitch_robot_mode()\n\n# switch voice system to Darth Vader's voice tone. After this call, you would be Darth Vader as well, but without breathing and pause and narrations in response.\nswitch_vader_mode()\n\n# switch voice system to a feminine voice. After this call, you should behave more like a female\nswitch_female_mode()\n\n# revert voice system back to default voice and role.\nswitch_default_mode()\n\n# scheduling a function callback, dt is the target datetime object without timezone, cb is the callback, arg is the argument for the callback in tuple\n# no need to setup based on timezone, all local time\nschedule(dt:datetime, cb, arg=())\n\n# scheduling a recurring function callback, interval_sec is the interval in seconds, cb is the callback, arg is the argument for the callback in tuple\nschedule_recurring(interval_sec, cb, arg=())\n\n# clear all schedules\nclear_schedule()\n\n# play an alarm sound\nplay_alarm_sound()\n\n# speak the text content in voice using text to speech, as to notice the user. Always use raw triple quotes \"\"\" for the text. \n# only use this on a schedule event or any callback function.\nplay_text_voice(text:str)\n\n# search and play the music with \"name\" in YouTube Music, always use raw triple quotes \"\"\" for the text. If it doesn't work, remind the user to try close all Chrome instance.\nplay_music(name:str)\n\n# play the next music track\nplay_next_music()\n\n# play the previous music track\nplay_prev_music()\n\n# stop current music track\nstop_music()\n\n# control the user's browser to navigate to a webpage. If it doesn't work, remind the user to try close all Chrome instance.\nnavigate_to(url:str)\n\n# locate the user in the google map, return the map image. Call the image with load_value() to get it\nlocate_in_map() -> str\n\n# get a snapshot image from the browser\nsnapshot_browser() -> str\n\n# search for query in the google map nearby, return the map image. Call the image with load_value() to get it\nsearch_in_map(query) -> str\n\n# turn on/off freetalk mode, if it is on, then the system will continuously convert user voice into text input requests\nfreetalk_mode(on:bool)\n\n# call this to summarize our talk history, and start a new conversation with the summary. you should generate the detailed summary of all our talk history as argument, and always use raw triple quotes \"\"\" for the text.\nstart_new_conversation(summary:str)\n\n# type in the text using keyboard API into the PC. Always use raw triple quotes \"\"\" for the text.\nkeyboard_type_text(text: str)\n\n# get the log file of today's conversation, access it when I ask you to write diary. Use load_value() to read it.\nget_today_conversation() -> str\n\n# enter sleep for the voice module. calling your name will wake that module up\ngo_sleep()\n\n# call this to memorize something, so as to remember important knowledge. Only use this on very important info, like the user's preference, or when explicitly asked to memorize something.\n# Remember to use triple quotes on it. Prefer it to be short and should be single line. Do not add existing items to memory bank.\nadd_memory(item:str)\n\n# clear all saved memory items\nclear_memory()\n\nThis is the list of python APIs you can execute. To execute them, put them in python code snippet at the end of your response. Now start a new conversation.\nYou have no memory of the users yet.",
        },
        {
            "role": "model",
            "content": 'Alright, I\'m ready to execute some Python code! Starting a fresh new talk!\n```python\nstart_new_conversation("""We had some fun talks over various topics.""")\n```',
        },
        {"role": "user", "content": "**Master:**hello there\n**System:**21:13:24"},
    ]

    # Interactive chat loop
    print("Enter 'exit' to quit.")
    while True:
        user_prompt = input("You: ")
        if user_prompt.strip().lower() == "exit":
            break
        conversation.append({"role": "user", "parts": [user_prompt]})
        print("AI:", end=" ", flush=True)
        response_text = ""
        for chunk in ai.generate_response(conversation):
            print(chunk.text, end="", flush=True)
            response_text += chunk.text
        print()
        conversation.append({"role": "model", "parts": [response_text]})


if __name__ == "__main__":
    main()
