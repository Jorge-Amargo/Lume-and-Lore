import os
import json
import datetime
import time
import re
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
        
        from utils import DashboardUtils
        self.config = DashboardUtils.load_config()

        self.book_id = self.config.get("book_id", "default")
        self.model_name = self.config.get("llm_model", "gemini-2.0-flash-exp")
        gen_cfg = self.config.get("generation", {})
        self.target_scene_count = int(gen_cfg.get("target_scene_count", 15))
        self.current_scene_num = 1
        self.cache = None
        self.chat = None

    def _filter_context(self, full_text, max_scenes=5):
        """Filters the .ink content to keep only variables and the last N scenes."""
        lines = full_text.splitlines()
        # Keep global variables (name, bio, traits) so the LLM knows who the player is
        vars_lines = [l for l in lines if l.strip().startswith("VAR ")]
        
        # Identify main scene knots (ignoring the 'result' knots)
        knot_indices = [i for i, l in enumerate(lines) if l.strip().startswith("==") and "_result_" not in l]
        
        if not knot_indices:
            return full_text
            
        # Select the starting point for the last N scenes
        target_index = knot_indices[-max_scenes] if len(knot_indices) > max_scenes else knot_indices[0]
        
        # Reconstruct: Variables at the top, then the recent story chunk
        return "\n".join(vars_lines) + "\n\n" + "\n".join(lines[target_index:])
    
    def set_scene_number(self, number):
        self.current_scene_num = number
        print(f"🎬 Architect: Progress synced to scene #{self.current_scene_num}")
    
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
            # 1. Define the master instruction here (with protagonist)
            from utils import DashboardUtils
            char = DashboardUtils.get_protagonist_from_ink(self.book_id)
            char_ctx = f"Protagonist: {char['name']} - {char['description']}" if char else "No protagonist defined yet."
            language_rule = """
            LANGUAGE RULES:
            1. You MUST write all narrative 'scene_text', 'ending', 'text' (choices), and 'outcome_text' 
               in the SAME LANGUAGE as the provided book text.
            2. You MUST write 'visual_prompt', 'reward_visual_prompt', and 'audio_prompt' 
               exclusively in ENGLISH (to ensure compatibility with image/audio generators).
            """
            instruction = f"You are a Master Director and Dungeon Master. Guide the story based on the provided book. Focus on the most memorable scenes. {char_ctx} {language_rule}"
            
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
    def generate_book_pitch(self):
        """Analyzes the book and suggests a summary and protagonists."""
        self._ensure_chat_ready()
        prompt = """
        Analyze the provided book. 
        1. Summarize the core conflict and atmosphere in 2-3 sentences.
        2. Identify the 2-4 most interesting main characters that could serve as a protagonist.
        
        RETURN JSON ONLY:
        {
            "summary": "...",
            "characters": [
                {"name": "...", "description": "Short 1-sentence hook why playing them is interesting"}
            ]
        }
        """
        resp = self.chat.send_message(prompt)
        return self._parse_json(resp.text)
    
    def initialize_engine(self, protagonist_name=None, skip_intro=False):
        if skip_intro: return None
        self._ensure_chat_ready()
        
        character_instruction = f"The player has chosen to play as: {protagonist_name}." if protagonist_name else "The player will play as the main character."

        prompt = f"""
        TASK: {character_instruction}
        Explain to the player the beginning of the journey and 
        introduce the book's setting. Describe the scene vividly, following the book's specific tone and style.
        REQUIREMENTS:
        1. If NOT the end: Provide exactly 3 choices (Golden, Exquisite, Bad).
        2. If IT IS the end: Set "ending" to a vivid final paragraph.
        3. 'scene_id' must be snake_case.
        4. UNIFIED STRUCTURE: Every choice MUST have an 'outcome_text' describing what happens next.
        5. TRAIT LOGIC: Use ONLY the trait label names (e.g. 'health', 'luck') as keys in 'trait_changes'.
        If an 'outcome_text' clearly affects a trait, you may change the trait value between -20 and +20.
        4. REWARD LOGIC: The 'exquisite' choice MUST include a 'reward_visual_prompt'.

        JSON STRUCTURE:
        {{
            "scene_id": "...",
            "scene_text": "...",
            "ending": "Optional final paragraph if the story ends here",
            "visual_prompt": "A concise prompt using simple words for SD1.5 image-generation (describe buildings, interior, landscape, colors)",
            "audio_prompt": "A concise prompt using simple words for SFX generation (mood, dominant sounds, loopable)",
            "choices": [
                {{"text": "...", "type": "golden", "outcome_text": "...", "trait_changes": "..."}},
                {{"text": "...", "type": "exquisite", "outcome_text": "...", "reward_visual_prompt": "...", "trait_changes": "..."}},
                {{"text": "...", "type": "bad", "outcome_text": "...", "trait_changes": "..."}}
            ]
        }}
        NOTE: The 'audio_prompt' should be concise (a few words) and focused on ambience, suitable to feed into a TTS/sound synthesis API.
        """
        print(prompt)
        print(self.target_scene_count)
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
            return {}

    def generate_main_beat(self, node_id, force_ending=False):
        self.current_scene_num += 1
        self._ensure_chat_ready() # 🛠️ FIX: Connects to Google only now
        active_traits = [re.sub(r'\W+', '_', v['label'].lower()) for k, v in self.config.get("traits", {}).items() if v['label']]
        traits_hint = "TRAIT RULES: You MUST use these exact variable names for changes: " + ", ".join(active_traits) if active_traits else "No traits active."
        if force_ending:
            pacing_instruction = f"""
            CRITICAL: This is the FINAL SCENE of the story (Scene {self.current_scene_num}).
            You MUST bring the narrative to a satisfying conclusion. 
            Resolve the main conflict. Do not introduce new mysteries.
            """
        else:
            pacing_instruction = f"PROGRESS: Scene {self.current_scene_num} / {self.target_scene_count}."
        
        prompt = f"""
        {pacing_instruction}
        Advance the story from {node_id}. 
        {traits_hint}
        Suggest changes for active traits in 'trait_changes' field (e.g., "health": 10).

        Describe the conclusion of the prevoious scene and the next major scene where the protagonist faces a decision. 
        Descibe the scene vividly and with the same tone and style as the book.
        
        CRITICAL MULTI-LANGUAGE REQUIREMENT:
        - Identify the language of the book context.
        - Write 'scene_text', 'choices.text', and 'choices.outcome_text' in that language.
        - Write 'visual_prompt' and 'audio_prompt' in ENGLISH.
        - If an 'exquisite' choice is present, 'reward_visual_prompt' MUST be in ENGLISH.
        
        CRITICAL: If the story has reached its natural conclusion based on the book, provide a final paragraph named 'ending' and leave 'choices' as an empty list [].

        REQUIREMENTS:
        1. If NOT the end: Provide exactly 3 choices (Golden, Exquisite, Bad).
        2. If IT IS the end: Set "ending" to a vivid final paragraph.
        3. 'scene_id' must be snake_case.
        3. UNIFIED STRUCTURE: Every choice MUST have an 'outcome_text' describing what happens next.
        4. TRAIT LOGIC: If an 'outcome_text' clearly affects a trait, you may change the trait value between -20 and +20.
        4. REWARD LOGIC: The 'exquisite' choice MUST include a 'reward_visual_prompt' that visualizes its specific 'outcome_text'.

        JSON STRUCTURE:
        {{
            "scene_id": "...",
            "scene_text": "[...]",
            "ending": "Optional final paragraph if the story ends here",
            "visual_prompt": "A concise prompt using simple words for SD1.5 image-generation (describe buildings, interior, landscape, colors)",
            "audio_prompt": "A concise prompt using simple words for SFX generation (mood, dominant sounds, loopable, IN ENGLISH)",
            "choices": [
                {{"text": "...", "type": "golden", "outcome_text": "...", "trait_changes": "..."}},
                {{"text": "...", "type": "exquisite", "outcome_text": "...", "reward_visual_prompt": "...", "trait_changes": "..."}},
                {{"text": "...", "type": "bad", "outcome_text": "...", "trait_changes": "..."}}
            ]
        }}
        NOTE: The 'audio_prompt' should be concise (a few words) and focused on ambience, suitable to feed into a TTS/sound synthesis API.
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

    def generate_story_pack(self, protagonist_name=None, scene_count=12):
        """Generates the full adventure in one call and returns all scenes as JSON."""
        self._ensure_chat_ready()
        scene_count = max(1, int(scene_count))
        active_traits = [
            re.sub(r'\W+', '_', v['label'].lower())
            for _, v in self.config.get("traits", {}).items()
            if v.get('label')
        ]
        traits_hint = ", ".join(active_traits) if active_traits else "sanity, health, luck"
        character_instruction = (
            f"The player has chosen to play as: {protagonist_name}."
            if protagonist_name
            else "The player will play as the most fitting protagonist from the book context."
        )

        prompt = f"""
        TASK: Generate a COMPLETE interactive adventure in ONE output.
        {character_instruction}

        HARD REQUIREMENTS:
        1. Return EXACTLY {scene_count} scenes in a top-level JSON object.
        2. Every scene except the last must contain exactly 3 choices (golden, exquisite, bad).
        3. The last scene must be the finale: include an 'ending' text and set 'choices' to [].
        4. Keep consistent narrative continuity from scene 1 to scene {scene_count}.
        5. Use ONLY these trait variable names in trait_changes: {traits_hint}
        6. trait_changes values must be integers between -20 and 20.
        7. scene_id values must be snake_case and unique.

        CRITICAL MULTI-LANGUAGE REQUIREMENT:
        - Write 'scene_text', 'ending', 'choices.text', and 'choices.outcome_text' in the SAME LANGUAGE as the book text.
        - Write 'visual_prompt', 'audio_prompt', and 'reward_visual_prompt' in ENGLISH.

        RETURN JSON ONLY with this exact structure:
        {{
          "meta": {{
            "protagonist": "...",
            "target_scene_count": {scene_count}
          }},
          "scenes": [
            {{
              "scene_id": "...",
              "scene_text": "...",
              "ending": "Optional final paragraph only on last scene",
              "visual_prompt": "...",
              "audio_prompt": "...",
              "choices": [
                {{"text": "...", "type": "golden", "outcome_text": "...", "trait_changes": {{}}}},
                {{"text": "...", "type": "exquisite", "outcome_text": "...", "reward_visual_prompt": "...", "trait_changes": {{}}}},
                {{"text": "...", "type": "bad", "outcome_text": "...", "trait_changes": {{}}}}
              ]
            }}
          ]
        }}
        """

        resp = self.chat.send_message(prompt)
        pack = self._parse_json(resp.text)
        if not isinstance(pack, dict):
            return None

        scenes = pack.get("scenes", [])
        if not isinstance(scenes, list):
            return None

        # Normalize scene structure so downstream editor logic is stable.
        normalized = []
        for i, scene in enumerate(scenes[:scene_count]):
            if not isinstance(scene, dict):
                continue
            scene = self._sanitize_response(scene)
            if "scene_id" not in scene or not scene.get("scene_id"):
                scene["scene_id"] = f"scene_{i+1}"
            if "scene_text" not in scene:
                scene["scene_text"] = ""
            if "visual_prompt" not in scene:
                scene["visual_prompt"] = ""
            if "audio_prompt" not in scene:
                scene["audio_prompt"] = ""
            if "choices" not in scene or not isinstance(scene.get("choices"), list):
                scene["choices"] = []
            normalized.append(scene)

        if not normalized:
            return None

        # Ensure the final scene is treated as finale in the local editor pipeline.
        normalized[-1]["choices"] = []
        if not normalized[-1].get("ending"):
            normalized[-1]["ending"] = normalized[-1].get("scene_text", "")

        pack["scenes"] = normalized
        pack["meta"] = pack.get("meta", {})
        pack["meta"]["target_scene_count"] = len(normalized)
        if protagonist_name and not pack["meta"].get("protagonist"):
            pack["meta"]["protagonist"] = protagonist_name
        return pack

    def resume_session(self, content_to_send):
        """Verbesserter Resume-Handshake."""
        self._ensure_chat_ready()
        optimized_content = self._filter_context(content_to_send, max_scenes=5)

        prompt = f"""
        RESUME ADVENTURE. 
        Story so far (Key Context & Last 5 scenes):
        ---
        {optimized_content}
        ---
        Analyze the state. Return JSON ONLY: 
        {{"status": "synchronized", "last_node": "ID_HERE", "summary": "..."}}
        """
        resp = self.chat.send_message(prompt)
        return self._parse_json(resp.text)

    def reset_to_main_path(self, parent_node_id):
        self._ensure_chat_ready()
        self.chat.send_message(f"Side-path finished. Returning to node {parent_node_id}.")

    def generate_conclusion(self, story_so_far):
            """Generates a final concluding paragraph based on the adventure's history."""
            self._ensure_chat_ready()
            prompt = f"""
            THE ADVENTURE HAS ENDED.
            Based on this story summary: {story_so_far}
            
            Write a poetic and satisfying 'The End' section (approx 100 words). 
            
            CRITICAL MULTI-LANGUAGE REQUIREMENT:
            - Write 'scene_text' in the SAME LANGUAGE as the provided book text.
            - Write 'visual_prompt' in ENGLISH.

            Return JSON ONLY:
            {{
                "scene_text": "Your concluding text...",
                "visual_prompt": "A final cinematic image description",
                "audio_prompt": "A final cinematic sound description",
                "choices": []
            }}
            """
            resp = self.chat.send_message(prompt)
            data = self._parse_json(resp.text)
            
            # Ensure choices key exists for compatibility with InkSmith
            if data and "choices" not in data:
                data["choices"] = []
            return data

    def _validate_and_retry(self, raw_text, required_keys, retries=3):
            for _ in range(retries):
                data = self._parse_json(raw_text)
                if data and all(k in data for k in required_keys):
                    return data
                resp = self.chat.send_message(f"Error: Missing keys {required_keys}. Reformatted JSON only.")
                raw_text = resp.text
            return {k: "Error" for k in required_keys}

    def _parse_json(self, text):
        """Extrahiert JSON, selbst wenn das LLM drumherum plaudert."""
        try:
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            if start_idx == -1 or end_idx == -1: return None
            
            raw_data = json.loads(text[start_idx:end_idx+1])
            return self._sanitize_response(raw_data)
        except Exception as e:
            print(f"❌ JSON Parse Error: {e}")
            return None

    def _sanitize_response(self, data):
        """Ensures that traits and choices are always in the expected format (dict/list)."""
        if not isinstance(data, dict):
            return data
            
        # Sanitize choices and their trait_changes
        if "choices" in data and isinstance(data["choices"], list):
            for choice in data["choices"]:
                if "trait_changes" in choice:
                    # If trait_changes is a string (common LLM error), try to parse it or default to {}
                    if isinstance(choice["trait_changes"], str):
                        try:
                            choice["trait_changes"] = json.loads(choice["trait_changes"].replace("'", '"'))
                        except:
                            choice["trait_changes"] = {}
                    elif not isinstance(choice["trait_changes"], dict):
                        choice["trait_changes"] = {}
        
        # Ensure scene_text is a string
        if "scene_text" in data and not isinstance(data["scene_text"], str):
            data["scene_text"] = str(data["scene_text"])           
        return data