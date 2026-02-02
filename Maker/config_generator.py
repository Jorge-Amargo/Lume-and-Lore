import json
import os
from dotenv import load_dotenv
from google import genai

# 1. Load the .env from one folder up
# Use override=True to ensure it forces the key into the environment
load_dotenv(os.path.join("..", ".env"), override=True)

# 2. Grab the key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 3. Safety Check: If the key is missing, stop here with a clear message
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found! Check your .env file in the root folder.")

# 4. NOW initialize the client
client = genai.Client(api_key=GEMINI_API_KEY)

class ConfigGenerator:
    def __init__(self, book_path, book_id):
        self.book_path = book_path
        self.book_id = book_id

    def initialize_book_config(self):
        """Asks Gemini to set the stage for the entire project."""
        with open(self.book_path, 'r', encoding='utf-8') as f:
            # We only need the first few thousand words to get the 'vibe'
            sample_text = f.read(8000)

        prompt = f"""
        Analyze this book excerpt: \"\"\"{sample_text}\"\"\"
        Add your knowledge of the book to do these TASKS:
        1. Write a 5-sentence summary of the book's overall plot and themes.
        2. Propose a 'Master Visual Style' (art medium, lighting, era) that fits the prose.
        
        OUTPUT ONLY VALID JSON:
        {{
            "book_id": "{self.book_id}",
            "context_summary": "...",
            "master_style": "...",
            "negative_prompt": "bad, low quality"
        }}
        """
        
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        config_data = json.loads(response.text.replace('```json', '').replace('```', '').strip())
        
        with open("../book_config.json", "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        
        print("✅ book_config.json created! You can now edit it before running the game.")