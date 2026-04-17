import os
import google.genai as genai
from google.genai import types
import time

class GeminiAI:
    def __init__(self, model_name, system_instruction):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not found")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

        self.generation_config = types.GenerateContentConfig(
            temperature=0.7,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            system_instruction=system_instruction,
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            ],
        )

        try:
            print("Available models:")
            for m in self.client.models.list():
                print(getattr(m, "name", m))
            print("Previous uploaded files:")
            for item in self.client.files.list():
                print(getattr(item, "name", "?"), getattr(item, "mime_type", "?"), getattr(item, "display_name", "?"))
        except Exception as e:
            print(e)
            pass
        print('Loading model', model_name)

    def _to_part(self, part):
        if isinstance(part, str):
            return types.Part(text=part)

        # Uploaded files expose URI + MIME info and need to be wrapped as file_data.
        file_uri = getattr(part, "uri", None)
        mime_type = getattr(part, "mime_type", None)
        if file_uri and mime_type:
            return types.Part(file_data=types.FileData(file_uri=file_uri, mime_type=mime_type))

        # Allow already-constructed SDK parts to pass through.
        if isinstance(part, types.Part):
            return part

        return types.Part(text=str(part))

    def _to_contents(self, messages: list):
        contents = []
        for msg in messages:
            if isinstance(msg, dict) and "role" in msg and "parts" in msg:
                parts = msg.get("parts", [])
                if not isinstance(parts, list):
                    parts = [parts]
                contents.append(
                    types.Content(
                        role=msg.get("role", "user"),
                        parts=[self._to_part(p) for p in parts],
                    )
                )
            else:
                # Fallback for direct string/part inputs.
                contents.append(types.Content(role="user", parts=[self._to_part(msg)]))
        return contents

    def generate_response(self, parts: list):
        response = self.client.models.generate_content_stream(
            model=self.model_name,
            contents=self._to_contents(parts),
            config=self.generation_config,
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
        uploaded_file = self.client.files.upload(
            file=path,
            config=types.UploadFileConfig(display_name=display_name),
        )
        # Wait for file to be processed
        self.wait_file(uploaded_file)
        return uploaded_file
    
    def get_file(self, name):
        """Get a file object by name"""
        return self.client.files.get(name=name)
    
    def wait_file(self, file_obj):
        """Wait for file to be processed"""
        while getattr(getattr(file_obj, "state", None), "name", "") == "PROCESSING":
            print('.', end='')
            time.sleep(0.5)
            file_obj = self.client.files.get(name=file_obj.name)
        
        if getattr(getattr(file_obj, "state", None), "name", "") == "FAILED":
            raise ValueError(f"File processing failed: {file_obj.error}")
        
        return file_obj

    def clear_files(self):
        """Delete all uploaded files"""
        for item in self.client.files.list():
            print(f"Deleting: {item.name} {item.mime_type} {item.display_name}")
            self.client.files.delete(name=item.name)

    def delete_file(self, file_obj):
        """Delete a specific file"""
        self.client.files.delete(name=file_obj.name)

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
