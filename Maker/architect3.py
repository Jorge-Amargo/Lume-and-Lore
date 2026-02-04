import os
import json
import datetime
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))  

class AutonomousArchitect:
    def __init__(self, book_path):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("❌ GEMINI_API_KEY is missing.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.book_path = book_path   
        
        # Load Config
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "..", "book_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.book_id = self.config.get("book_id", "default")
        self.model_name = self.config.get("llm_model", "gemini-2.0-flash-exp")
        
        # 1. Setup Context Cache
        self.cache = self._setup_context_cache()
        
        # 2. Start Chat Session
        self.chat = self.client.chats.create(
            model=f"models/{self.model_name}",
            config=types.GenerateContentConfig(
                cached_content=self.cache.name,
                system_instruction="You are a Master Director and Dungeon Master. Guide the story based on the provided book."
            )
        )

    def _setup_context_cache(self):
        """Purges old caches and creates/reloads the current one."""
        active_display_name = f"Context_{self.book_id}"
        model_path = f"models/{self.model_name}"
        target_cache = None

        try:
            # New SDK syntax for listing/purging
            for c in self.client.caches.list():
                if c.display_name.startswith("Context_"):
                    if c.display_name == active_display_name and c.model == model_path:
                        target_cache = c
                    else:
                        self.client.caches.delete(name=c.name)
        except Exception as e:
            print(f"Cache check: {e}")

        if not target_cache:
            with open(self.book_path, 'r', encoding='utf-8') as f:
                book_content = f.read()

            target_cache = self.client.caches.create(
                model=model_path,
                config=types.CreateCachedContentConfig(
                    display_name=active_display_name,
                    contents=[types.Content(parts=[types.Part(text=book_content)])],
                    ttl="3600s", # 1 Hour
                )
            )
        return target_cache

        if not target_cache:
            print(f"📤 Uploading fresh context for {self.book_id}...")
            with open(self.book_path, 'r', encoding='utf-8') as f:
                book_content = f.read()

            target_cache = self.client.caches.create(
                model=model_path,
                config=types.CreateCachedContentConfig(
                    display_name=active_display_name,
                    contents=[types.Content(parts=[types.Part(text=book_content)])],
                    ttl="3600s", # 1 Hour
                )
            )
        return target_cache
    
    def initialize_engine(self):
        with open(self.book_path, "r", encoding="utf-8") as f:
            book_text = f.read()

        system_instruction = f"""
        You are the Game Engine for '{self.config['title']}'.
        You are telling the story of the book from the eyes of the protagonist.
        The scenes should use as much of the original text as possible, adapting it into an interactive format.
        Make the adventure engaging and immersive. 
        You will generate scenes, visual prompts for images, and choices for the player.
        Provide a dramatic 2-paragraph introduction to the story and a visual prompt. Return JSON.
        """

        # Cleanup old caches
        try:
            for c in self.client.caches.list():
                if c.display_name == f"engine_{self.config.get('book_id', 'default')}":
                    self.client.caches.delete(name=c.name)
        except: pass

        # Create Cache
        self.cache = self.client.caches.create(
            model=self.model_name,
            config=types.CreateCachedContentConfig(
                display_name=f"engine_{self.config.get('book_id', 'default')}",
                contents=[types.Content(role="user", parts=[types.Part(text=book_text)])],
                system_instruction=system_instruction,
                ttl="7200s"
            )
        )

        # Create the Chat Session
        safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        ]

        # Create Chat
        self.chat = self.client.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                cached_content=self.cache.name, 
                temperature=0.7
            )
        )
        if skip_intro: return None

        prompt = """
        TASK: Act as the game engine. Introduce the book's setting and the main character.
        Describe the scene vividly and with the same tone and style as the book.
        
        OUTPUT FORMAT: Return ONLY JSON with 'scene_text' and 'visual_prompt'.
        """
        resp = self.chat.send_message(prompt)
        return self._validate_and_retry(resp.text, ["scene_text", "visual_prompt"])

    def generate_main_beat(self, node_id):
        prompt = f"""
        Advance the plot from {node_id}. 
        
        TASK: Architect the next major narrative beat where the protagonist faces a decision. 
        Descibe the scene vividly and with the same tone and style as the book.
        You MUST then provide exactly 3 choices with these types:
        1. 'golden': original choice of the protagonist in the book. Progresses the main book plot.
        2. 'exquisite': A alternative to the book leading to a better solution. A rewarding side-track or investigation.
        3. 'bad': A dangerous or failed action.
        For every choice, provide an outcome_text (1-2 sentences) describing what happens when 
        the player selects it, before they move to the next scene
        Return JSON ONLY:
        {{
            "scene_id": "short_snake_case_slug",
            "scene_text": "2-3 paragraphs",
            "choices": [
                {{"text": "...", "type": "golden/exquisite/bad", "outcome_text": "1 sentence reaction"}},
                ...
            ],
            "visual_prompt": "SDXL style prompt"
        }}
        """
        resp = self.chat.send_message(prompt)
        return self._parse_json(resp.text)

    def generate_transition(self, parent_id, choice_obj):
        prompt = f"Player chose: {choice_obj['text']}. Write a creative outcome and a visual prompt. Return JSON."
        resp = self.chat.send_message(prompt)
        return self._parse_json(resp.text)

    def resume_session(self, ink_summary):
        """Injects previous game state back into the AI context."""
        prompt = f"""
        Resume the game based on this state summary:
        {ink_summary}
        The player is at the last node mentioned. Acknowledge and wait for next instruction.
        Return JSON: {{"status": "synchronized", "last_node": "ID_HERE"}}
        """
        resp = self.chat.send_message(prompt)
        return self._parse_json(resp.text)

    def reset_to_main_path(self, parent_node_id):
        self.chat.send_message(f"Side-path finished. Returning to node {parent_node_id}.")

    def _validate_and_retry(self, raw_text, required_keys, retries=3):
        for _ in range(retries):
            data = self._parse_json(raw_text)
            if data and all(k in data for k in required_keys):
                return data
            resp = self.chat.send_message(f"Error: Missing keys {required_keys}. Reformatted JSON only.")
            raw_text = resp.text
        return {k: "Error" for k in required_keys}

    def _parse_json(self, text):
        try:
            cleaned = text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except: return None