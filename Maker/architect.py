import os
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(os.path.join("..", ".env"), override=True)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class AutonomousArchitect:
    def __init__(self, book_path):
        with open("../book_config.json", "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.book_path = book_path
        self.chat = None
        self.cache = None

    def initialize_engine(self):
        """Initializes the cache and generates the Intro text."""
        with open(self.book_path, 'r', encoding='utf-8') as f:
            book_text = f.read()

        # 1. Unrestricted Safety Filters
        safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        ]

        # 2. 2026 Model Discovery
        print("--- Scanning for Caching-Ready Models ---")
        cacheable_models = [m.name for m in client.models.list() if 'create_cached_content' in m.supported_actions]
        MODEL_NAME = next((m for m in cacheable_models if "pro" in m), "models/gemini-2.5-flash")
        print(f"🚀 Using Model: {MODEL_NAME}")

        # 3. Cache Creation (Role 'user' required)
        self.cache = client.caches.create(
            model=MODEL_NAME,
            config=types.CreateCachedContentConfig(
                display_name=f"engine_{self.config['book_id']}",
                contents=[types.Content(role="user", parts=[types.Part(text=book_text)])],
                system_instruction = f"""
                Act as a game engine for: {self.config['title']}.
                Tell the story from the perspective of the main protagonist using the book's words and style.
                Present the user with the main choices the protagonist faces.
                VISUAL RULE: For 'visual_prompt', describe a dynamic scene of the character in the current environment. 
                """,
                ttl="7200s" 
            )
        )

        self.chat = client.chats.create(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(cached_content=self.cache.name, safety_settings=safety_settings)
        )
        
        if skip_intro:
            return None # Just warm up the chat, don't generate text
            
        prompt = "Act as the game engine. Introduce the book's setting. Return ONLY JSON with 'scene_text' and 'visual_prompt'."
        resp = self.chat.send_message(prompt)
        return self._validate_and_retry(resp.text, ["scene_text", "visual_prompt"])
        

    def generate_main_beat(self, progress_context):
        # We explicitly define what 'exquisite' and 'bad' mean for this specific book.
        prompt = f"""
        CURRENT PLOT: {progress_context}
        
        TASK: Write a short scene for the next main plot-point of the protagonist. Summarize the events that have happened until then, 
        describe the scene using the book's original style.
        You MUST provide exactly 3 choices for the protagonist on what do do next, all being possible from the book's perspective. 
        Use these types for the choices:
        1. 'golden': the choice the protagonist is coosing in the book and which progresses the main book plot.
        2. 'exquisite': A rewarding side-track, in the style of the book's main themes.
        3. 'bad': An action which would have bad consequences in the world of the book.
        PROMPT GUIDELINE: For 'visual_prompt', create tags for an image generator describing the scene. 
        Return ONLY JSON with 'node_id', 'scene_text', 'visual_prompt', and 'choices'.
        """
        resp = self.chat.send_message(prompt)
        return self._validate_and_retry(resp.text, ["node_id", "scene_text", "choices"])

    def explore_path(self, choice_text, is_reward=False):
        """Follows a choice and returns the outcome."""
        prompt = f"The player chooses: '{choice_text}'. "
        if is_reward:
            prompt += "Generate a Reward Scene. No choices. Return JSON with 'scene_text' and 'visual_prompt'."
        else:
            prompt += "Continue the story. Return JSON with 'node_id', 'scene_text', 'visual_prompt', and 'choices'."
        
        resp = self.chat.send_message(prompt)
        return self._validate_and_retry(resp.text, ["scene_text"])

    def reset_to_main_path(self, last_node_id):
        self.chat.send_message(f"Return focus to the main plot after node {last_node_id}.")

    def _validate_and_retry(self, text, required_keys):
        try:
            data = self._parse_json(text)
            if all(k in data for k in required_keys): return data
            raise KeyError("Missing Keys")
        except:
            print("⚠️ JSON Invalid. Retrying once...")
            retry = self.chat.send_message(f"Invalid JSON. Re-output but ensure these keys: {required_keys}")
            return self._parse_json(retry.text)

    def _parse_json(self, text):
        # Removes Markdown code blocks if the LLM adds them
        clean = text.replace('```json', '').replace('```', '').strip()
        try:
            # Look for the actual JSON boundaries
            start = clean.find('{')
            end = clean.rfind('}') + 1
            if start == -1: raise ValueError("No JSON found")
            return json.loads(clean[start:end])
        except Exception as e:
            print(f"❌ JSON Parse Error: {e}")
            return {}
    
    def generate_transition(self, parent_node_id, choice):
        """Generates the specific outcome of a choice (Golden, Exquisite, or Bad)."""
        c_type = choice.get('type', 'golden')
        c_text = choice.get('text', '')

        prompt = f"""
        CONTEXT: The player is at node '{parent_node_id}'.
        CHOICE TAKEN: '{c_text}' (Type: {c_type}).
        
        TASK:
        Describe the immediate outcome of this choice using the book's original style.
        - If 'golden': This is the next main plot beat. Include 3 new choices.
        - If 'exquisite': This is a reward scene. No new choices. Add a 'variable_change' if applicable
        - If 'bad': This is a failure or death. Describe the fate vividly.
        
        OUTPUT JSON: Include 'scene_text', 'visual_prompt', and (if golden) 'choices' and 'node_id'.
        """
        resp = self.chat.send_message(prompt)
        return self._validate_and_retry(resp.text, ["scene_text", "visual_prompt"])