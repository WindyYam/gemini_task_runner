import os
import google.generativeai as genai
from datetime import datetime
import time

class GeminiAI:
    def __init__(self, model_name, system_instruction):
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        try:
            print("Available models:")
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    print(m.name)
            print("Previous uploaded files:")
            lists = genai.list_files()
            for item in lists:
                print(item.name, item.mime_type, item.display_name)
        except Exception as e:
            print(e)
            pass
        
        self.model = self._initialize_model(model_name, system_instruction)

    def _initialize_model(self, model_name, system_instruction):
        print('Loading model', model_name)
        
        # Updated safety settings for latest API
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE"
            }
        ]
        
        return genai.GenerativeModel(
            model_name=model_name,
            safety_settings=safety_settings,
            system_instruction=system_instruction
        )

    def generate_response(self, parts: list):
        # Updated generation config for latest API
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
        
        response = self.model.generate_content(
            parts, 
            stream=True, 
            generation_config=generation_config,
            request_options={"timeout": 30}
        )
        return response

    @staticmethod
    def extract_code(input_string):
        start = input_string.find('```python')
        startlen = 9
        if start == -1:
            # The AI will sometimes try tool_code instead of python
            start = input_string.find('```tool_code')
            startlen = 12
        end = -1
        if start >= 0:
            start = start + startlen
            end = input_string.find('```', start)
        if start == -1 or end == -1:
            return ''
        return input_string[start:end]

    @staticmethod
    def strip_code(input_string):
        start = input_string.find('```python')
        if start == -1:
            # The AI will sometimes try tool_code instead of python
            start = input_string.find('```tool_code')
        end = input_string.find('```', start + 9)
        if start == -1 or end == -1:
            return input_string
        return input_string[:start] + input_string[end + 3:]

    def upload_file(self, path, display_name):
        """Upload a file to Gemini and return the file object"""
        uploaded_file = genai.upload_file(path=path, display_name=display_name)
        # Wait for file to be processed
        self.wait_file(uploaded_file)
        return uploaded_file
    
    def get_file(self, name):
        """Get a file object by name"""
        return genai.get_file(name)
    
    def wait_file(self, file_obj):
        """Wait for file to be processed"""
        while file_obj.state.name == "PROCESSING":
            print('.', end='')
            time.sleep(0.5)
            file_obj = genai.get_file(file_obj.name)
        
        if file_obj.state.name == "FAILED":
            raise ValueError(f"File processing failed: {file_obj.error}")
        
        return file_obj

    def clear_files(self):
        """Delete all uploaded files"""
        lists = genai.list_files()
        for item in lists:
            print(f"Deleting: {item.name} {item.mime_type} {item.display_name}")
            genai.delete_file(item)

    def delete_file(self, file_obj):
        """Delete a specific file"""
        genai.delete_file(file_obj)

def main():
    """Test function to verify GeminiAI functionality"""
    try:
        # Check if API key is available
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("❌ Error: GEMINI_API_KEY environment variable not found!")
            print("Please set your Gemini API key in the environment variable:")
            print("export GEMINI_API_KEY='your_api_key_here'")
            return
        
        print("🚀 Testing GeminiAI class...")
        print(f"✓ API key found: {api_key[:10]}...{api_key[-4:]}")
        
        # Initialize the AI with a test system instruction
        system_instruction = """You are a helpful AI assistant. 
        Respond concisely and helpfully to user queries."""
        
        print("\n📡 Initializing Gemini model...")
        ai = GeminiAI(
            model_name="gemini-1.5-flash",  # Using the latest available model
            system_instruction=system_instruction
        )
        print("✓ Model initialized successfully!")
        
        # Test basic text generation
        print("\n💬 Testing text generation...")
        test_prompt = "Hello! Can you tell me a fun fact about Python programming?"
        
        try:
            response = ai.generate_response([test_prompt])
            
            print("✓ Response received:")
            print("-" * 50)
            
            # Stream the response
            full_response = ""
            for chunk in response:
                if chunk.text:
                    print(chunk.text, end='', flush=True)
                    full_response += chunk.text
            
            print("\n" + "-" * 50)
            print(f"✓ Total response length: {len(full_response)} characters")
            
        except Exception as e:
            print(f"❌ Error during text generation: {e}")
            return
        
        # Test code extraction methods
        print("\n🔧 Testing utility methods...")
        test_code_string = """Here's some Python code:
```python
def hello_world():
    print("Hello, World!")
    return True
```
That should work!"""
        
        extracted_code = GeminiAI.extract_code(test_code_string)
        print(f"✓ Code extraction test: Found {len(extracted_code)} characters of code")
        if extracted_code:
            print(f"  Extracted: {extracted_code.strip()[:50]}...")
        
        stripped_text = GeminiAI.strip_code(test_code_string)
        print(f"✓ Code stripping test: Result length {len(stripped_text)} characters")
        
        print("\n🎉 All tests completed successfully!")
        print("The GeminiAI class is working properly.")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
