import os
import time
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables (fallback if not loaded by parent script)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Configuration Constants
MODEL_NAME = "gemini-2.5-flash" 

class AutonomousArchitect:
    def __init__(self, book_path):
        """
        Initializes the Architect.
        Now connects to Google ONLY when the class is instantiated, not at import.
        """
        # 1. Validation
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("❌ CRITICAL ERROR: GEMINI_API_KEY is missing from .env file.")
        
        # 2. Lazy Connection
        self.client = genai.Client(api_key=self.api_key)
        
        # 3. CRITICAL FIX: Save the book_path to the object
        self.book_path = book_path   # <--- THIS LINE WAS LIKELY MISSING
        
        # 4. Load Config using Absolute Path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "..", "book_config.json")
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config not found at: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.chat = None
        self.cache = None

    def initialize_engine(self, skip_intro=False):
        """Reads the book and creates a cached context for the AI."""
        print(f"📚 Architect reading source text: {self.book_path}...")
        
        with open(self.book_path, "r", encoding="utf-8") as f:
            book_text = f.read()

        # System Prompt
        system_instruction = f"""
        You are the Game Engine for '{self.config['title']}'.
        You are telling the story of the book from the eyes of the protagonist. The scenes should use as much
        of the original text as possible, adapting it into an interactive format. Make the adventure engaging and immersive.
        You will generate scenes, visual prompts for images, and choices for the player. 
        OUTPUT FORMAT: strictly JSON only with keys: 'node_id', 'scene_text', 'visual_prompt', 
        'choices' (list of dicts with 'text' and 'type').
        For 'visual_prompt', describe the current scene using tags for an SDXL-based image generator.
        Do not show the face of the protagonist, focus on background, environment and other characters.
        Example: 'schemen of Alice from Alice in Wonderland, faceless, falling down a rabbit hole, 
        dark clocks doors and multiple things flowing in the dark.
        """

        # Create the Cache using self.client
        try:
            self.cache = self.client.caches.create(
                model=MODEL_NAME,
                config=types.CreateCachedContentConfig(
                    display_name=f"engine_{self.config['book_id']}",
                    contents=[types.Content(role="user", parts=[types.Part(text=book_text)])],
                    system_instruction=system_instruction,
                    ttl="7200s"
                )
            )
        except Exception as e:
            print(f"⚠️ Cache creation warning (might already exist): {e}")

        # Create the Chat Session
        safety_settings = [
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        ]

       # Read model from config, default to flash if missing
        model_name = self.config.get("llm_model", "gemini-2.0-flash-exp")
        
        self.chat = self.client.chats.create(
            model=model_name, 
            config=types.GenerateContentConfig(
                cached_content=self.cache.name, 
                safety_settings=safety_settings,
                temperature=0.7
            )
        )

        if skip_intro:
            print("⏩ Skipping intro generation (Resume Mode).")
            return None

        # Generate Intro
        prompt = "Act as the game engine. Introduce the book's setting and the main character. Explain the mission of \
        the main character. Return ONLY JSON with 'scene_text' and 'visual_prompt'."
        resp = self.chat.send_message(prompt)
        return self._validate_and_retry(resp.text, ["scene_text", "visual_prompt"])

    def generate_main_beat(self, progress_context):
        """Generates the next major plot point for the main characterwith 3 distinct choice types."""
        prompt = f"""
        CURRENT PLOT: {progress_context}
        
        TASK: Architect the next major narrative beat where the protagonist faces a decision. 
        Descibe the scene vividly and with the same tone and style as the book.
        You MUST then provide exactly 3 choices with these types:
        1. 'golden': original choice of the protagonist in the book. Progresses the main book plot.
        2. 'exquisite': A alternative to the book leading to a better solution. A rewarding side-track or investigation.
        3. 'bad': A dangerous or failed action.
        
        OUTPUT FORMAT: JSON with keys: 'node_id', 'scene_text', 'visual_prompt', 'choices' (list of dicts with 'text' and 'type').
        """
        resp = self.chat.send_message(prompt)
        return self._validate_and_retry(resp.text, ["node_id", "scene_text", "visual_prompt", "choices"])

    def generate_transition(self, parent_node_id, choice):
        """Generates the outcome of a specific choice."""
        c_type = choice.get('type', 'golden')
        prompt = f"The player chose: '{choice['text']}' which is a {c_type} path. "
        
        if c_type == 'bad':
            prompt += "Describe a negative or death scene. Provide 'outcome_text' with negative variable change (dict) or 'death_text'."
        elif c_type == 'exquisite':
            prompt += "Describe a short, beautiful reward scene. optional: Provide positive'variable_change' (dict)."
        else:
            prompt += "Advance the plot to the next logical sequence."
            
        prompt += " Return JSON."
        
        resp = self.chat.send_message(prompt)
        return self._validate_and_retry(resp.text, ["scene_text", "visual_prompt"])

    def resume_session(self, full_ink_text):
        """Injects the existing adventure script back into the LLM context."""
        print("🧠 Synchronizing LLM memory with existing Ink script...")
        
        prompt = f"""
        RESUMING STORY. Below is the adventure script generated so far:
        --- START OF SCRIPT ---
        {full_ink_text}
        --- END OF SCRIPT ---
        
        Task: 
        1. Internalize the current plot position.
        2. Identify the last 'golden' path choice that was made.
        3. Do NOT repeat any scenes. 
        4. Prepare to continue the narrative from the very next book beat.
        
        Acknowledge by returning a JSON: {{"status": "synchronized", "last_node": "ID_HERE"}}
        """
        resp = self.chat.send_message(prompt)
        return self._parse_json(resp.text)

    def reset_to_main_path(self, parent_node_id):
        """Tells the AI to forget the side-track and look back at the main fork."""
        self.chat.send_message(f"The player has returned from the side-path. We are back at node {parent_node_id}. Ready for next main beat.")

    def _validate_and_retry(self, raw_text, required_keys, retries=3):
        """Parses JSON and ensures required keys exist."""
        for _ in range(retries):
            data = self._parse_json(raw_text)
            if data and all(k in data for k in required_keys):
                return data
            print(f"⚠️ JSON Validation Failed. Retrying...")
            # Self-correction prompt
            resp = self.chat.send_message(f"Error: Missing keys {required_keys}. specific keys needed. Reformatted JSON only.")
            raw_text = resp.text
        
        # Emergency Fallback
        return {k: "Error generating content" for k in required_keys}

    def _parse_json(self, text):
        """Cleans Markdown code blocks from JSON string."""
        try:
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text)
        except json.JSONDecodeError:
            return None