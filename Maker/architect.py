import os
import json
import datetime
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))  

class AutonomousArchitect:
    def __init__(self, book_path):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("❌ GEMINI_API_KEY is missing.")
        
        # 🛠️ FIX: Removed 'transport' and used HttpOptions for a safe timeout
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=120000) # 2 minute timeout for slow handshakes
        )
        self.book_path = book_path   
        
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "book_config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.book_id = self.config.get("book_id", "default")
        self.model_name = self.config.get("llm_model", "gemini-2.0-flash-exp")
        
        self.cache = None
        self.chat = None

    def _setup_context_cache(self):
        """Creates the cache. This will now run only when the game actually starts."""
        # Use a timestamp to ensure uniqueness and skip the 'listing' hang
        unique_name = f"ctx-{self.book_id}-{int(time.time())}" 
        
        with open(self.book_path, 'r', encoding='utf-8') as f:
            book_content = f.read()

        return self.client.caches.create(
            model=f"models/{self.model_name}",
            config=types.CreateCachedContentConfig(
                display_name=unique_name,
                contents=[types.Content(role="user", parts=[types.Part(text=book_content)])],
                ttl="3600s", 
            )
        )
    def _ensure_chat_ready(self):
        """🛠️ FIX: Moves system_instruction into the cache to resolve 400 error."""
        if self.chat is None:
            # 1. Define the master instruction here
            instruction = "You are a Master Director and Dungeon Master. Guide the story based on the provided book. Focus on the most memorable scenes."
            
            if self.cache is None:
                unique_name = f"ctx-{self.book_id}-{int(time.time())}"
                with open(self.book_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                print(f"📤 Uploading context to Gemini: {unique_name}...")
                
                # 🛠️ FIX: Baked the instruction directly into the cache
                self.cache = self.client.caches.create(
                    model=f"models/{self.model_name}",
                    config=types.CreateCachedContentConfig(
                        display_name=unique_name,
                        system_instruction=instruction, # Instruction goes HERE
                        contents=[types.Content(role="user", parts=[types.Part(text=content)])],
                        ttl="3600s", 
                    )
                )
            
            # 🛠️ FIX: Chat config must NOT contain system_instruction when using a cache
            self.chat = self.client.chats.create(
                model=f"models/{self.model_name}",
                config=types.GenerateContentConfig(
                    cached_content=self.cache.name,
                    temperature=0.7 
                    # system_instruction must NOT be here
                )
            )
    
    def initialize_engine(self, skip_intro=False):
        if skip_intro: return None
        self._ensure_chat_ready()
        
        prompt = """
        TASK: Explain to the player that he will play the main character of the book in this game and 
        introduce the book's setting. Describe the scene vividly, following the book's specific tone and style.
        
        REQUIREMENTS:
        1. Describe the scene vividly.
        2. Provide exactly 3 choices (Golden, Exquisite, Bad).
        3. UNIFIED STRUCTURE: For EVERY choice, you must write the 'outcome_text' (the immediate narrative result of that action).
        4. REWARD LOGIC: Only for the 'exquisite' choice, add a 'reward_visual_prompt' describing the positive aspects of that outcome.

        JSON STRUCTURE:
        {
            "scene_id": "intro",
            "scene_text": "...",
            "visual_prompt": "A concise prompt for SD1.5 image-generation (buildings, interior, landscape, colors)",
            "audio_prompt": "A concise prompt for SFX sound-generation (mood, dominant sounds, loopable)",
            "choices": [
                {"text": "...", "type": "golden", "outcome_text": "..."},
                {"text": "...", "type": "exquisite", "outcome_text": "...", "reward_visual_prompt": "..."},
                {"text": "...", "type": "bad", "outcome_text": "..."}
            ]
        }
        NOTE: The 'audio_prompt' should be concise (a few words) and focused on ambience or textures, suitable to feed into a TTS/sound synthesis API.
        """
        try:
            resp = self.chat.send_message(prompt)
            data = self._parse_json(resp.text)
            if data is None:
                return None
            if 'audio_prompt' not in data or not data.get('audio_prompt'):
                vp = data.get('visual_prompt', '')
                data['audio_prompt'] = f"{vp} — ambience, background texture, loopable"
                print(f"ℹ️ Architect: derived audio_prompt: {data['audio_prompt']}")
            else:
                print(f"ℹ️ Architect: audio_prompt from LLM: {data.get('audio_prompt')}")
            return data
        except Exception as e:
            print(f"❌ Handshake or API Error: {e}")
            return {
                "scene_text": "The story begins in a mist...",
                "visual_prompt": "mysterious fog, cinematic",
                "audio_prompt": "mysterious fog, soft wind, distant chimes, loopable",
                "choices": [
                    {"text": "Step forward", "type": "golden", "outcome_text": "You advance."},
                    {"text": "Look closer", "type": "exquisite", "outcome_text": "You find a clue."},
                    {"text": "Turn back", "type": "bad", "outcome_text": "You trip."}
                ]
            }

    def generate_main_beat(self, node_id):
        self._ensure_chat_ready() # 🛠️ FIX: Connects to Google only now
        prompt = f"""
        Advance the story from {node_id}. 
        Describe the conclusion of the prevoious scene and the next major scene where the protagonist faces a decision. 
        Descibe the scene vividly and with the same tone and style as the book.
        
        REQUIREMENTS:
        1. Provide exactly 3 choices (Golden, Exquisite, Bad).
        2. 'scene_id' must be snake_case.
        3. UNIFIED STRUCTURE: Every choice MUST have an 'outcome_text' describing what happens next.
        4. REWARD LOGIC: The 'exquisite' choice MUST include a 'reward_visual_prompt' that visualizes its specific 'outcome_text'.

        JSON STRUCTURE:
        {{
            "scene_id": "...",
            "scene_text": "...",
            "visual_prompt": "A concise prompt for SD1.5 image-generation (buildings, interior, landscape, colors)",
            "audio_prompt": "A concise prompt for SFX generation (mood, dominant sounds, loopable)",
            "choices": [
                {{"text": "...", "type": "golden", "outcome_text": "..."}},
                {{"text": "...", "type": "exquisite", "outcome_text": "...", "reward_visual_prompt": "..."}},
                {{"text": "...", "type": "bad", "outcome_text": "..."}}
            ]
        }}
        NOTE: The 'audio_prompt' should be concise (a few words) and focused on ambience or textures, suitable to feed into a TTS/sound synthesis API.
        """
        resp = self.chat.send_message(prompt)
        data = self._parse_json(resp.text)
        # Fallback: if LLM didn't provide an explicit audio_prompt, derive a short one from the visual prompt
        if data is None:
            return None
        if 'audio_prompt' not in data or not data.get('audio_prompt'):
            vp = data.get('visual_prompt', '')
            data['audio_prompt'] = f"{vp} — ambience, background texture, loopable"
            print(f"ℹ️ Architect: derived audio_prompt: {data['audio_prompt']}")
        else:
            print(f"ℹ️ Architect: audio_prompt from LLM: {data.get('audio_prompt')}")
        return data

    def generate_transition(self, parent_id, choice_obj):
        self._ensure_chat_ready()
        prompt = f"Player chose: {choice_obj['text']}. Write a creative outcome and a visual prompt. Return JSON."
        resp = self.chat.send_message(prompt)
        return self._parse_json(resp.text)

    def resume_session(self, ink_summary):
        """Injects previous game state back into the AI context."""
        self._ensure_chat_ready()
        prompt = f"""
        Resume the game based on this state summary:
        {ink_summary}
        The player is at the last node mentioned. Acknowledge and wait for next instruction.
        Return JSON: {{"status": "synchronized", "last_node": "ID_HERE"}}
        """
        resp = self.chat.send_message(prompt)
        return self._parse_json(resp.text)

    def reset_to_main_path(self, parent_node_id):
        self._ensure_chat_ready()
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