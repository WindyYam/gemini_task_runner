import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from datetime import datetime

class GeminiAI:
    def __init__(self, name, system_instruction):
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        lists = genai.list_files()
        for item in lists:
            print(item.name)
            genai.delete_file(item)
        self.name = name
        self.model = self._initialize_model(system_instruction)  

    def _initialize_model(self, system_instruction):
        return genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            safety_settings={
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            },
            system_instruction=system_instruction
        )

    def generate_response(self, parts:list):
        response = self.model.generate_content(parts, stream=False)
        return response.text

    @staticmethod
    def extract_code(input_string):
        start = input_string.find('```python')
        end = -1
        if start >= 0:
            start = start + 9
            end = input_string.find('```', start)
        if start == -1 or end == -1:
            return ''
        return input_string[start:end]

    @staticmethod
    def strip_code(input_string):
        start = input_string.find('```python')
        end = input_string.find('```', start + 9)
        if start == -1 or end == -1:
            return input_string
        return input_string[:start] + input_string[end + 3:]

    @staticmethod
    def upload_file(path, display_name):
        return genai.upload_file(path=path, display_name=display_name)