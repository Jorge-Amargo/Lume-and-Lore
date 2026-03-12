import os
import json
import datetime
import requests
import shutil
import sqlite3
import re
import streamlit as st
from google import genai
from session_manager import initialize_session_state, current_dir, BOOKS_DIR, CONFIG_PATH, DEFAULT_LLMS, DB_NAME

initialize_session_state()

class DashboardUtils:

    @staticmethod
    def _title_to_folder_name(title):
        """Creates a filesystem-safe folder name from an adventure title."""
        raw = (title or "").strip()
        if not raw:
            raw = "Untitled_Adventure"
        # Preserve case, replace whitespace with underscores, and strip invalid path chars.
        raw = re.sub(r'\s+', '_', raw)
        raw = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', raw)
        raw = re.sub(r'_+', '_', raw).strip('_')
        return raw or "Untitled_Adventure"

    @staticmethod
    def get_project_output_dir(book_id=None, title=None):
        """
        Resolve the active project directory.
        Primary target is always the title-based folder so different adventures can
        coexist for the same source book.
        """
        output_root = os.path.join(current_dir, "..", "data", "output")
        os.makedirs(output_root, exist_ok=True)

        cfg = DashboardUtils.load_config()
        effective_title = title or cfg.get("title", "New Adventure")
        title_folder = DashboardUtils._title_to_folder_name(effective_title)
        title_path = os.path.join(output_root, title_folder)
        return title_path
   
    @staticmethod
    def update_game_manifest():
        """Scans output folder and updates the manifest.json for the Player."""
        # current_dir is defined on line 14, so we make sure this runs after that
        output_dir = os.path.join(current_dir, "..", "data", "output")
        manifest_path = os.path.join(output_dir, "manifest.json")      
        projects = []
        
        if os.path.exists(output_dir):
            for folder in os.listdir(output_dir):
                folder_path = os.path.join(output_dir, folder)
                if os.path.isdir(folder_path):
                    ink_path = os.path.join(folder_path, "adventure.ink")
                    
                    # Default values if not found in .ink
                    lang = "English"
                    p_name = "Unknown"
                    
                    if os.path.exists(ink_path):
                        with open(ink_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Extract Language
                            l_m = re.search(r'VAR\s+language\s*=\s*"([^"]+)"', content)
                            if l_m: lang = l_m.group(1)
                            # Extract Protagonist
                            n_m = re.search(r'VAR\s+protagonist_name\s*=\s*"([^"]+)"', content)
                            if n_m: p_name = n_m.group(1)

                    if os.path.exists(os.path.join(folder_path, "adventure.json")):
                        projects.append({
                            "id": folder, 
                            "title": folder.replace("_", " ").title(),
                            "protagonist": p_name,
                            "language": lang
                        })
                        

        with open(manifest_path, 'w') as f:
            json.dump(projects, f, indent=4)
        
        return len(projects)
        
    @staticmethod
    def get_protagonist_from_ink(book_id):
        """Liest Name und Bio des Helden exklusiv aus der .ink Datei aus."""
        output_dir = DashboardUtils.get_project_output_dir(book_id=book_id)
        ink_path = os.path.join(output_dir, "adventure.ink")
        if not os.path.exists(ink_path): return None
        char = {}
        with open(ink_path, 'r', encoding='utf-8') as f:
            content = f.read()
            name_m = re.search(r'VAR protagonist_name\s*=\s*"([^"]+)"', content)
            bio_m = re.search(r'VAR protagonist_bio\s*=\s*"([^"]+)"', content)
            if name_m: char['name'] = name_m.group(1)
            if bio_m: char['description'] = bio_m.group(1)
        return char if char else None

    @staticmethod
    def initialize_ink_file(book_id, character):
        """Erstellt das .ink-File mit globalen Variablen für den Protagonisten."""
        output_dir = st.session_state.get("active_project_path", DashboardUtils.get_project_output_dir(book_id=book_id))
        # OVERWRITE LOGIC: Wipe existing folder if it exists for this combination
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        os.makedirs(output_dir, exist_ok=True)
        ink_path = os.path.join(output_dir, "adventure.ink")
        current_lang = st.session_state.get("lib_lang", "English")
        header = (f'VAR protagonist_name = "{character.get("name", "Unknown")}"\n'
              f'VAR protagonist_bio = "{character.get("description", "")}"\n'
              f'VAR last_node = "intro"\n')
        # 3. Add Traits from Config
        config = DashboardUtils.load_config()
        traits = config.get("traits", {})
        for t_key, t_data in traits.items():
            label = t_data.get("label", "").strip()
            if label:
                # Use label (lowercase, no spaces) as variable name
                var_name = re.sub(r'\W+', '_', label.lower())
                initial_val = t_data.get("initial", 50)
                header += f'VAR {var_name} = {initial_val} // {label}\n'
        header += '\n-> start_node\n\n=== start_node ===\nThe adventure begins...\n'
        with open(ink_path, 'w', encoding='utf-8') as f: 
            f.write(header)
        print(f"✅ Created .ink header for {book_id} in {current_lang}")
        return True
    
    @staticmethod
    def compile_ink_to_json(book_id):
        """
        Compiles the adventure.ink into adventure.json and updates manifest.
        Returns (success: bool, message: str)
        """
        import subprocess
        output_dir = st.session_state.get("active_project_path", DashboardUtils.get_project_output_dir(book_id=book_id))
        ink_path = os.path.join(output_dir, "adventure.ink")
        json_path = os.path.join(output_dir, "adventure.json")

        if not os.path.exists(ink_path):
            return False, f"File not found: {ink_path}"

        inklecate_cmd = DashboardUtils.locate_inklecate()
        if not inklecate_cmd:
            return False, "Ink compiler 'inklecate' not found. Please check your installation."

        try:
            result = subprocess.run([inklecate_cmd, "-o", json_path, ink_path], check=True, capture_output=True)
            DashboardUtils.update_game_manifest()
            return True, "Compilation Successful! 'adventure.json' updated."
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
            return False, f"Compilation Failed: {err_msg}"
        except Exception as e:
            return False, f"Unexpected Error: {e}"
        
    @staticmethod
    def update_game_manifest():
        """Scans output folder and updates the manifest.json for the Player."""
        # current_dir is defined on line 14, so we make sure this runs after that
        output_dir = os.path.join(current_dir, "..", "data", "output")
        manifest_path = os.path.join(output_dir, "manifest.json")
        
        projects = []
        
        if os.path.exists(output_dir):
            for folder in os.listdir(output_dir):
                folder_path = os.path.join(output_dir, folder)
                if os.path.isdir(folder_path):
                    ink_path = os.path.join(folder_path, "adventure.ink")
                    lang = "English" # Default
                    # We check for the compiled json file
                    json_path = os.path.join(folder_path, "adventure.json")
                    if os.path.exists(json_path):
                        # Read content only if ink_path exists
                        if os.path.exists(ink_path):
                            with open(ink_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            lang_match = re.search(r'VAR\s+language\s*=\s*"([^"]+)"', content)
                            if lang_match:
                                lang = lang_match.group(1)
                    title = folder.replace("_", " ").title()
                    projects.append({"id": folder, "title": title, "language": lang})
                        

        with open(manifest_path, 'w') as f:
            json.dump(projects, f, indent=4)
        
        return len(projects)
    
    @staticmethod
    def locate_inklecate():
        ink_env = os.getenv("INKLECATE_PATH") or os.getenv("INKLECATE")
        if ink_env:
            # if env points to a directory or exact file, prefer that
            if os.path.isfile(ink_env) and os.access(ink_env, os.X_OK):
                return ink_env
            # fall back to resolving via PATH
            found = shutil.which(ink_env)
            if found:
                return found

        # look on PATH (handles both linux/mac and Windows .exe)
        which_cmd = shutil.which("inklecate") or shutil.which("inklecate.exe")
        if which_cmd:
            return which_cmd

        return None
    
    @staticmethod
    def fetch_gemini_models():
        """Holt die Liste der verfügbaren Modelle direkt von der Google API."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print(f"⚠️ API key not set for fetching models.")
            return DEFAULT_LLMS
        
        try:
            client = genai.Client(api_key=api_key)
            # Wir filtern nach Modellen, die Textgenerierung unterstützen
            available_models = []
            for m in client.models.list():
                if "generateContent" in m.supported_actions:
                    # Wir extrahieren nur den Namen (z.B. gemini-2.0-flash)
                    name = m.name.split("/")[-1]
                    available_models.append(name)
            
            # Sortieren und sicherstellen, dass die Liste nicht leer ist
            return sorted(available_models) if available_models else DEFAULT_LLMS
        except Exception as e:
            print(f"⚠️ API Error fetching models: {e}")
            return DEFAULT_LLMS

    @staticmethod
    def finalize_ink_node(base_id, scene):
        # 1. DEFINE NAMES
        current_real_id = scene.get('scene_id', base_id)
        next_placeholder = f"{current_real_id}_NEXT"
        use_story_pack = bool(st.session_state.get("story_pack_mode", False))
        
        curr_id = st.session_state.node_id
        next_node_id = f"{base_id}_next"
        selected_audio = st.session_state.get('sound_selected_map', {}).get(base_id)

        # In Story Pack mode we know all scene IDs up front, so we can link directly
        # to the next scene and avoid synthetic "_next" placeholder knots.
        if use_story_pack:
            cfg = DashboardUtils.load_config()
            pack = DashboardUtils.load_story_pack(cfg.get("book_id", ""))
            if pack:
                idx = int(pack.get("progress", {}).get("next_index", 0))
                scenes = pack.get("scenes", [])
                if idx + 1 < len(scenes):
                    next_scene = scenes[idx + 1] if isinstance(scenes[idx + 1], dict) else {}
                    next_node_id = next_scene.get("scene_id", f"scene_{idx+2}")
                else:
                    next_node_id = "END"
        
        smith = st.session_state.smith
        
        # 1. Linking & Cleanup
        if curr_id != "intro":
            # If we are creating a NEW scene from a placeholder (e.g. intro_next -> oak_closet),
            # we must update 'intro_next' to point to 'oak_closet'.
            if curr_id != base_id:
                smith.connect_scenes(curr_id, base_id)
            
            # Always remove the definition of the new node if it existed previously
            # to ensure we write a clean version.
            smith.remove_knot(base_id)

        # 2. Write the Main Node
        if curr_id == "intro":
            # Handle potential ID renaming for intro
            if base_id != "intro":
                smith.patch_placeholder_links("intro", base_id)
            smith.write_intro(scene, next_node_id, audio_file=selected_audio, audio_prompt=scene.get('audio_prompt'))
        else:
            smith.write_main_node_start(
                base_id, 
                scene['scene_text'], 
                f"{base_id}_main",
                scene['choices'], 
                next_node_id,
                audio_file=selected_audio,
                audio_prompt=scene.get('audio_prompt')
            )

        # --- NEW: keep resume marker up to date ---
        # append a runtime assignment so `get_resume_state` doesn’t
        # fall back to the stale VAR at the top of the file.
        try:
            with open(smith.ink_path, "a", encoding="utf-8") as f:
                f.write(f'\n~ last_node = "{current_real_id}"\n')
        except Exception:
            pass

        # 3. Write Outcomes
        smith.write_choice_outcomes(base_id, scene['choices'], next_node_id)
        
        # 4. Check if this is the end (no choices)
        is_end = not scene.get('choices')
        if not is_end:
            # Create placeholder knots only for legacy per-scene generation mode.
            if not use_story_pack and next_node_id != "END":
                smith.write_placeholder_knot(next_node_id)
            st.session_state.node_id = next_node_id
            st.session_state.current_step = "narrative"
        else:
            st.session_state.current_step = "finished"

        # 5. Reset
        st.toast(f"✅ Scene '{base_id}' saved to .ink file.")
        st.session_state.scene_data = None
        st.session_state.picking_reward = False
        
        # Clear all state variables for this scene (including the cleanup flag)
        st.session_state.pop(f'scene_cleaned_{base_id}', None)
        st.session_state.pop(f'generated_main_{base_id}', None)
        st.session_state.pop(f'generated_reward_{base_id}', None)
        st.session_state.pop(f'generated_images_{base_id}', None)
        st.session_state.pop(f'generated_images_{base_id}_reward', None)
        st.session_state.pop(f'generated_images_{base_id}_in_progress', None)
        st.session_state.pop(f'generated_images_{base_id}_reward_in_progress', None)
        st.session_state.pop(f'scene_images_completed_{base_id}', None)
        st.session_state.pop(f'awaiting_sound_{base_id}', None)
        st.session_state.pop(f'reward_selected_{base_id}', None)
        st.session_state.pop(f'generated_sfx_{base_id}', None)
        # st.rerun() removed to allow further processing after finalize_ink_node

    @staticmethod
    def load_config():
        """Lädt die Config und fängt Fehler ab, falls die Datei leer oder kaputt ist."""
        if not os.path.exists(CONFIG_PATH):
            return {"book_id": "unknown_book", "llm_model": "gemini-2.0-flash-exp"}
        
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content: # Datei ist leer
                    return {"book_id": "unknown_book", "llm_model": "gemini-2.0-flash-exp"}
                return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"book_id": "unknown_book", "llm_model": "gemini-2.0-flash-exp"}

    @staticmethod
    def save_config(config):
        """Speichert die Config sicher."""
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        
        if os.path.exists(CONFIG_PATH):
            try:
                # FIX: Use utf-8 to handle emojis/special chars on Windows
                with open(CONFIG_PATH, "r", encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    config.update(loaded_data)
            except Exception as e:
                print(f"⚠️ Config Load Error: {e}")
                # Do not silence errors; let the user know via console
        return config

    @staticmethod
    def search_gutenberg_native(query, search_type="title", language=""):
        # FIX: Absolute path to database
        db_path = os.path.join(current_dir, "..", "data", DB_NAME)
        if not os.path.exists(db_path): 
            st.error(f"⚠️ Database not found at {db_path}!")
            return []
        try:
            conn = sqlite3.connect(db_path); c = conn.cursor()
            search_param = f"%{query}%"
            lang_param = f"%[Language: {language}]%" if language else ""
            if search_type == "title":
                if language:
                    # Search title AND filter by language tag in the record
                    c.execute("""SELECT t.book_id, t.name, a.name FROM titles t 
                                 LEFT JOIN authors a ON t.book_id = a.book_id 
                                 WHERE t.name LIKE ? AND (t.name LIKE ? OR a.name LIKE ?) 
                                 LIMIT 500""", (search_param, lang_param, lang_param))
                else:
                    c.execute("SELECT t.book_id, t.name, a.name FROM titles t LEFT JOIN authors a ON t.book_id = a.book_id WHERE t.name LIKE ? LIMIT 500", (search_param,))
            else:
                if language:
                    c.execute("""SELECT a.book_id, t.name, a.name FROM authors a 
                                 LEFT JOIN titles t ON a.book_id = t.book_id 
                                 WHERE a.name LIKE ? AND (a.name LIKE ? OR t.name LIKE ?) 
                                 LIMIT 500""", (search_param, lang_param, lang_param))
                else:
                    c.execute("SELECT a.book_id, t.name, a.name FROM authors a LEFT JOIN titles t ON a.book_id = t.book_id WHERE a.name LIKE ? LIMIT 500", (search_param,))
            
            rows = c.fetchall()
            conn.close()
            return [f"[{r[0]}] {r[1]} - {r[2]}" for r in rows]
        except Exception as e: 
            st.error(f"Search Error: {e}")
            return []
        
    @staticmethod
    def download_book_robust(selection):
        try:
            book_id = selection.split(']')[0].strip('[')
            url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
            r = requests.get(url, timeout=10)
            if r.status_code != 200: return None
            clean_title = re.sub(r'[^a-zA-Z0-9]', '_', selection.split(']')[1].strip())[:50]
            filename = f"{clean_title}.txt"
            os.makedirs(BOOKS_DIR, exist_ok=True)
            with open(os.path.join(BOOKS_DIR, filename), "w", encoding="utf-8") as f:
                f.write(r.text)
            return filename
        except: return None

    # --- CLEANUP: Delete old adventure files (assets & audio) ---
    @staticmethod
    def cleanup_old_adventure_files(book_id, confirm_first=True):
        """
        Scans and deletes old image/sound files for a book to ensure fresh start.
        Returns: (files_deleted_count, cleaned_successfully)
        """
        output_dir = st.session_state.get("active_project_path", DashboardUtils.get_project_output_dir(book_id=book_id))
        
        if not os.path.exists(output_dir):
            return 0, True
        
        # Files to delete: *.png in assets/, *.mp3 & *.wav & *.ogg in audio/
        assets_dir = os.path.join(output_dir, "assets")
        audio_dir = os.path.join(output_dir, "audio")
        
        files_to_delete = []
        
        ink_path = os.path.join(output_dir, "adventure.ink")
        if os.path.exists(ink_path):
            files_to_delete.append(ink_path)
        story_pack_path = os.path.join(output_dir, "story_pack.json")
        if os.path.exists(story_pack_path):
            files_to_delete.append(story_pack_path)

        if os.path.exists(assets_dir):
            for f in os.listdir(assets_dir):
                if f.endswith(('.png', '.jpg', '.jpeg')):
                    files_to_delete.append(os.path.join(assets_dir, f))
        
        if os.path.exists(audio_dir):
            for f in os.listdir(audio_dir):
                if f.endswith(('.mp3', '.wav', '.ogg')):
                    files_to_delete.append(os.path.join(audio_dir, f))
        
        if not files_to_delete:
            return 0, True
        
        if confirm_first:
            print(f"⚠️ CLEANUP: Found {len(files_to_delete)} old adventure files for '{book_id}':")
            for f in files_to_delete[:5]:
                print(f"   - {os.path.basename(f)}")
            if len(files_to_delete) > 5:
                print(f"   ... and {len(files_to_delete) - 5} more")
        
        try:
            deleted = 0
            for fpath in files_to_delete:
                try:
                    os.remove(fpath)
                    deleted += 1
                except Exception as e:
                    print(f"   ⚠️ Could not delete {os.path.basename(fpath)}: {e}")
            print(f"✅ Deleted {deleted}/{len(files_to_delete)} old files")
            return deleted, True
        except Exception as e:
            print(f"❌ Cleanup failed: {e}")
            return 0, False

    @staticmethod
    def get_story_pack_path(book_id):
        output_dir = st.session_state.get("active_project_path", DashboardUtils.get_project_output_dir(book_id=book_id))
        return os.path.join(output_dir, "story_pack.json")

    @staticmethod
    def load_story_pack(book_id):
        path = DashboardUtils.get_story_pack_path(book_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            if "scenes" not in data or not isinstance(data.get("scenes"), list):
                return None
            data.setdefault("meta", {})
            data.setdefault("progress", {})
            data["progress"].setdefault("next_index", 0)
            data["progress"].setdefault("saved_scene_ids", [])
            return data
        except Exception as e:
            print(f"⚠️ Could not load story pack: {e}")
            return None

    @staticmethod
    def save_story_pack(book_id, pack_data):
        path = DashboardUtils.get_story_pack_path(book_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pack_data, f, indent=2, ensure_ascii=False)
        return path

    @staticmethod
    def create_story_pack(book_id, raw_pack):
        """Persists a freshly generated story pack and initializes resume metadata."""
        if not isinstance(raw_pack, dict):
            return None
        scenes = raw_pack.get("scenes", [])
        if not isinstance(scenes, list) or not scenes:
            return None

        pack = {
            "meta": raw_pack.get("meta", {}),
            "scenes": scenes,
            "progress": {
                "next_index": 0,
                "saved_scene_ids": []
            }
        }
        pack["meta"]["created_at"] = pack["meta"].get("created_at") or datetime.datetime.utcnow().isoformat() + "Z"
        return DashboardUtils.save_story_pack(book_id, pack)

    @staticmethod
    def get_next_story_pack_scene(book_id):
        """Returns (index, total, scene) or (None, total, None) if completed."""
        pack = DashboardUtils.load_story_pack(book_id)
        if not pack:
            return None, 0, None
        scenes = pack.get("scenes", [])
        total = len(scenes)
        idx = int(pack.get("progress", {}).get("next_index", 0))
        if idx >= total:
            return None, total, None
        scene = scenes[idx]
        if isinstance(scene, dict):
            scene.setdefault("scene_id", f"scene_{idx+1}")
            scene.setdefault("scene_text", "")
            scene.setdefault("visual_prompt", "")
            scene.setdefault("audio_prompt", "")
            scene.setdefault("choices", [])
        return idx, total, scene

    @staticmethod
    def advance_story_pack(book_id, edited_scene):
        """Saves edited scene back into the pack and advances resume cursor."""
        pack = DashboardUtils.load_story_pack(book_id)
        if not pack:
            return False
        scenes = pack.get("scenes", [])
        idx = int(pack.get("progress", {}).get("next_index", 0))
        if idx >= len(scenes):
            return False

        if isinstance(edited_scene, dict):
            scenes[idx] = edited_scene
            scene_id = edited_scene.get("scene_id", f"scene_{idx+1}")
        else:
            scene_id = f"scene_{idx+1}"

        saved_ids = pack.get("progress", {}).get("saved_scene_ids", [])
        if scene_id not in saved_ids:
            saved_ids.append(scene_id)
        pack["progress"]["saved_scene_ids"] = saved_ids
        pack["progress"]["next_index"] = idx + 1
        DashboardUtils.save_story_pack(book_id, pack)
        return True
