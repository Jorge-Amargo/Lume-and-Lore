import os
import json
import shutil
import time
import requests
import sqlite3
import re
import streamlit as st
from dotenv import load_dotenv
import subprocess
from architect import AutonomousArchitect
from visual_weaver import VisualWeaver
from ink_smith import InkSmith
from sound_weaver import SoundWeaver

# Helper: safe rerun that supports Streamlit versions without experimental_rerun
def safe_rerun():
    try:
        st.experimental_rerun()
    except Exception:
        try:
            # Fall back to changing query params to trigger a rerun
            st.experimental_set_query_params(_rerun=int(time.time()))
            print("⚠️ streamlit.experimental_rerun not available; used query-param fallback to trigger rerun.")
        except Exception:
            # Last resort: stop script (user will need to interact to continue)
            print("⚠️ Unable to trigger rerun programmatically. Please refresh the page.")
            st.stop()

# --- 1. SETUP & PATHS ---
st.set_page_config(page_title="Lume & Lore Director", layout="wide", page_icon="🕯️")

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '..', '.env')
load_dotenv(os.path.join(current_dir, '..', '.env'))

if "engine_ready" not in st.session_state:
    st.session_state.engine_ready = False
    st.session_state.current_step = "narrative"
    st.session_state.node_id = "intro"
    st.session_state.scene_data = None
    st.session_state.generated_images = []
    st.session_state.smith = None
    
BOOKS_DIR = os.path.join(current_dir, "..", "data", "books")
CONFIG_PATH = os.path.join(current_dir, "..", "book_config.json")
DB_NAME = "gutenberg_index.db"
DEFAULT_LLMS = ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"]

# --- 2. HELPER FUNCTIONS ---
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
                # We check for the compiled json file
                json_path = os.path.join(folder_path, "adventure.json")
                if os.path.exists(json_path):
                    title = folder.replace("_", " ").title()
                    projects.append({"id": folder, "title": title})

    with open(manifest_path, 'w') as f:
        json.dump(projects, f, indent=4)
    
    return len(projects)
try:
    count = update_game_manifest()
    st.sidebar.caption(f"🎮 {count} Playable Games Found")
except Exception as e:
    print(f"Manifest Error: {e}")

def compile_current_ink():
    """Compiles the current project's .ink file into a .json file for the player."""
    # Check if smith exists and has the attribute self.ink_path (which you already have)
    if "smith" not in st.session_state or not hasattr(st.session_state.smith, 'ink_path'):
        print("⚠️ Cannot compile: InkSmith.ink_path not found in session state.")
        return
    
    # Use your existing attribute name
    ink_path = st.session_state.smith.ink_path
    json_path = ink_path.replace(".ink", ".json")
    
    try:
        # Runs the external 'inklecate' command.
        subprocess.run(["inklecate", "-o", json_path, ink_path], check=True, capture_output=True)
        
        # After a successful compile, refresh the manifest so the Player knows it's ready
        update_game_manifest()
    except subprocess.CalledProcessError as e:
        # Decode and display the specific Inklecate error
        err_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
        st.error(f"⚠️ Ink Compilation Failed:\n{err_msg}")
        print(f"Compilation Error:\n{err_msg}")
    except Exception as e:
        st.error(f"⚠️ Ink Compilation Failed: {e}")
        print(f"Compilation Error: {e}")

def finalize_ink_node(base_id, scene):
    # 1. DEFINE NAMES
    current_real_id = scene.get('scene_id', base_id)
    next_placeholder = f"{current_real_id}_NEXT"
    
    curr_id = st.session_state.node_id
    next_node_id = f"{base_id}_next"
    selected_audio = st.session_state.get('sound_selected_map', {}).get(base_id)
    
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

    # 3. Write Outcomes (Restored from dashboard_git.py)
    # This writes the '== scene_result_1 ==' knots that the choices link to.
    smith.write_choice_outcomes(base_id, scene['choices'], next_node_id)
    
    # 4. Create the NEXT placeholder (This fixes the compilation error)
    smith.write_placeholder_knot(next_node_id)

    # 5. Compile & Reset
    st.session_state.node_id = next_node_id
    st.session_state.current_step = "narrative"
    # Auto-compilation disabled to allow manual inspection of .ink file
    # compile_current_ink() 
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
    st.rerun()

def load_config():
    # Default Configuration
    config = {
        "book_id": "unknown_book",
        "title": "Unknown Book",
        "llm_model": "gemini-2.0-flash-exp",
        "supported_llms": DEFAULT_LLMS,
        "generation": {
            "images_per_scene": 4,
            "sounds_per_scene": 1,
            "sound_length_seconds": 5,
            "sound_loop": False
        }
    }
    
    # Debug Path
    # print(f"DEBUG: Loading config from {os.path.abspath(CONFIG_PATH)}")
    
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

def save_config(new_config):
    try:
        # FIX: Use utf-8 and ensure_ascii=False for readable JSON
        with open(CONFIG_PATH, "w", encoding='utf-8') as f:
            json.dump(new_config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Config Save Error: {e}")
        st.error(f"Could not save config: {e}")

def check_forge_connection(api_url):
    try:
        requests.get(f"{api_url}/sdapi/v1/options", timeout=2)
        return True
    except: return False

# GUTENBERG HELPERS (Native SQL) ---
def search_gutenberg_native(query, search_type="title"):
    # FIX: Absolute path to database
    db_path = os.path.join(current_dir, "..", DB_NAME)
    if not os.path.exists(db_path): 
        st.error(f"⚠️ Database not found at {db_path}!")
        return []
    try:
        conn = sqlite3.connect(db_path); c = conn.cursor()
        sql = f"%{query}%"
        if search_type == "title":
            c.execute("SELECT t.book_id, t.name, a.name FROM titles t LEFT JOIN authors a ON t.book_id = a.book_id WHERE t.name LIKE ? LIMIT 500", (sql,))
        else:
            c.execute("SELECT a.book_id, t.name, a.name FROM authors a LEFT JOIN titles t ON a.book_id = t.book_id WHERE a.name LIKE ? LIMIT 500", (sql,))
        rows = c.fetchall(); conn.close()
        return [f"[{r[0]}] {r[1]} - {r[2]}" for r in rows]
    except Exception as e: 
        st.error(f"Search Error: {e}")
        return []

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

def apply_visual_bible(prompt, char_map):
    if not char_map: return prompt
    for name, desc in char_map.items():
        prompt = re.sub(re.escape(name), desc, prompt, flags=re.IGNORECASE)
    return prompt

# --- CLEANUP: Delete old adventure files (assets & audio) ---
def cleanup_old_adventure_files(book_id, confirm_first=True):
    """
    Scans and deletes old image/sound files for a book to ensure fresh start.
    Returns: (files_deleted_count, cleaned_successfully)
    """
    output_dir = os.path.join(current_dir, "..", "data", "output", book_id)
    
    if not os.path.exists(output_dir):
        return 0, True
    
    # Files to delete: *.png in assets/, *.mp3 & *.wav & *.ogg in audio/
    assets_dir = os.path.join(output_dir, "assets")
    audio_dir = os.path.join(output_dir, "audio")
    
    files_to_delete = []
    
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

def cleanup_scene_files(scene_id, weaver):
    """
    Delete all image/audio files for a specific scene (scene_id).
    This ensures each scene generation starts fresh.
    """
    assets_dir = weaver.output_dir
    audio_dir = os.path.join(os.path.dirname(assets_dir), os.path.basename(assets_dir), 'audio')
    
    files_to_delete = []
    
    # Find all files for this scene (both main and reward)
    if os.path.exists(assets_dir):
        for f in os.listdir(assets_dir):
            if f.startswith(f"{scene_id}_") and f.endswith(('.png', '.jpg', '.jpeg')):
                files_to_delete.append(os.path.join(assets_dir, f))
    
    # Also check for audio files for this scene
    if os.path.exists(audio_dir):
        for f in os.listdir(audio_dir):
            if scene_id in f and f.endswith(('.mp3', '.wav', '.ogg')):
                files_to_delete.append(os.path.join(audio_dir, f))
    
    for fpath in files_to_delete:
        try:
            os.remove(fpath)
            print(f"🗑️ Deleted: {os.path.basename(fpath)}")
        except Exception as e:
            print(f"⚠️ Could not delete {os.path.basename(fpath)}: {e}")
    
    return len(files_to_delete)


# --- 3. DERIVE BOOK ID GLOBALLY (Fixes NameError) ---
st.sidebar.title("⚙️ Engine Settings")
tab_lib, tab_conf = st.sidebar.tabs(["📚 Library", "🔧 Config"])

os.makedirs(BOOKS_DIR, exist_ok=True)
available_books = [f for f in os.listdir(BOOKS_DIR) if f.endswith(".txt")]
current_config = load_config()
active_book_id = current_config.get("book_id", "unknown_book")
BOOKS_DIR = os.path.join(current_dir, "..", "data", "books") 
active_book_filename = current_config.get("book_filename", f"{active_book_id}.txt")
book_path = os.path.join(BOOKS_DIR, active_book_filename)

if not os.path.exists(book_path):
    # Fallback: Try removing trailing underscore (common sanitization issue)
    alt_name = active_book_id.rstrip('_') + ".txt"
    alt_path = os.path.join(BOOKS_DIR, alt_name)
    if os.path.exists(alt_path):
        active_book_filename = alt_name
        book_path = alt_path
        # Update config so it remembers the correct file next time
        current_config['book_filename'] = active_book_filename
        save_config(current_config)
weaver = VisualWeaver()
smith = InkSmith(active_book_id)
# Validate ElevenLabs API key for sound generation in UI
gen_cfg = current_config.get('generation', {})
if 'eleven' in gen_cfg.get('sound_model', '').lower():
    if not os.getenv('ELEVENLABS_API_KEY'):
        st.warning("⚠️ ELEVENLABS_API_KEY not set. Sound generation using ElevenLabs will be unavailable. Add ELEVENLABS_API_KEY to your `.env` file at the project root or set it in your environment variables. See https://elevenlabs.io/app/developers for details.")

with tab_lib:
    st.markdown("### 🌍 Project Gutenberg")
    search_mode = st.radio("Search by:", ["Title", "Author"], horizontal=True, key="lib_mode")
    search_query = st.text_input("Search term", key="lib_query")
    if st.button("🔍 Search Library", key="lib_search"):
        st.session_state.search_results = search_gutenberg_native(search_query, search_mode.lower())
    
    if "search_results" in st.session_state and st.session_state.search_results:
        selected_book_str = st.selectbox("Select Result", st.session_state.search_results, key="lib_res")
        if st.button("⬇️ Download & Import", key="lib_dl"):
            with st.spinner("Downloading..."):
                fname = download_book_robust(selected_book_str)
                if fname:
                    st.success(f"Imported: {fname}")
                    st.rerun()

    st.markdown("---")
    st.markdown("### 📂 Local Library")
    if available_books:
        conf = load_config()
        saved_id = conf.get("book_id", "")
        def_idx = 0
        for i, f in enumerate(available_books):
            if saved_id in f: def_idx = i; break
        current_book_filename = st.selectbox("Active Source Text", available_books, index=def_idx, key="local_sel")
        if "last_book_sel" not in st.session_state or st.session_state.last_book_sel != current_book_filename:
            # Strip .txt and replace underscores with spaces
            new_title = os.path.splitext(current_book_filename)[0].replace('_', ' ')
            st.session_state["c_title"] = new_title
            st.session_state["last_book_sel"] = current_book_filename
            current_config["title"] = new_title
            current_config["book_id"] = "".join(x for x in os.path.splitext(current_book_filename)[0] if x.isalnum() or x in "_-")
            current_config["book_filename"] = current_book_filename
            save_config(current_config)
        active_book_id = "".join(x for x in os.path.splitext(current_book_filename)[0] if x.isalnum() or x in "_-")
with tab_conf:
    # Load latest config
    current_config = load_config()
    
    st.markdown("### 🛠️ Generation Settings")
    if 'generation' not in current_config: current_config['generation'] = {}
    gen_cfg = current_config.get('generation', {})
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.subheader("🎨 Visuals")
        img_count = st.slider("Images per Scene", 1, 8, gen_cfg.get('images_per_scene', 4))
    with col_g2:
        st.subheader("🎧 Audio")
        snd_count = st.slider("Sounds per Scene", 0, 5, gen_cfg.get('sounds_per_scene', 1))
        snd_len = st.number_input("Sound Duration (sec)", 1, 30, gen_cfg.get('sound_length_seconds', 5))
        snd_loop = st.checkbox("Seamless Loop", value=gen_cfg.get('sound_loop', False))
        
    st.divider()

    st.markdown("#### 📝 Project Metadata")
    title = st.text_input(
        "Project Title", 
        value=st.session_state.get("c_title", current_config.get("title", "New Adventure")), 
        key="c_title"
    )
    
    st.markdown("#### 🧠 AI Brain")
    llms = current_config.get("supported_llms", DEFAULT_LLMS)
    def_llm = current_config.get("llm_model", "gemini-2.0-flash-exp")
    llm_model = st.selectbox("LLM Model", llms, index=llms.index(def_llm) if def_llm in llms else 0, key="c_llm")

    st.markdown("#### 🎨 Visual Style")
    vis = current_config.get("visual_settings", {})
    m_style = st.text_area("Master Style", value=vis.get("master_style", ""), key="c_style")
    p_prompt = st.text_area("Positive Prompt", value=vis.get("positive_prompt", ""), key="c_pos")
    n_prompt = st.text_area("Negative Prompt", value=vis.get("negative_prompt", ""), key="c_neg")

    with st.expander("🖼️ Stable Diffusion Advanced"):
        sd = current_config.get("sd_settings", {})
        # Try to fetch models from the API
        available_models = weaver.get_sd_models()
        current_model_val = sd.get("sd_model", "")

        if available_models:
            # If the currently saved model isn't in the list (e.g. different PC), add it safely
            # so the index lookup doesn't crash.
            if current_model_val and current_model_val not in available_models:
                available_models.insert(0, current_model_val)
            
            # Default to the saved model, or the first one in the list
            try:
                idx = available_models.index(current_model_val)
            except ValueError:
                idx = 0
            
            sd_m = st.selectbox("SD Model", available_models, index=idx, key="c_sd_model")
        else:
            # Fallback: API is down, allow manual text entry
            st.caption("⚠️ API unreachable. Enter model name manually.")
            sd_m = st.text_input("SD Model", value=current_model_val, key="c_sd_model")
        c1, c2 = st.columns(2)
        with c1:
            width = st.number_input("Width", value=sd.get("width", 512), key="c_w")
            steps = st.number_input("Steps", value=sd.get("steps", 20), key="c_steps")
            sampler = st.text_input("Sampler", value=sd.get("sampler_name", "Euler a"), key="c_samp")
        with c2:
            height = st.number_input("Height", value=sd.get("height", 512), key="c_h")
            cfg = st.number_input("CFG Scale", value=sd.get("cfg_scale", 7.0), key="c_cfg")
            scheduler = st.text_input("Scheduler", value=sd.get("scheduler", "normal"), key="c_sched")

    st.markdown("#### 👥 Character Bible")
    if "temp_char_map" not in st.session_state:
        st.session_state.temp_char_map = current_config.get("character_map", {}).copy()
    
    c_name = st.text_input("Name", key="bible_name_in")
    c_desc = st.text_input("Visual Description", key="bible_desc_in")
    if st.button("➕ Add Character"):
        if c_name and c_desc:
            st.session_state.temp_char_map[c_name] = c_desc
            st.rerun()

    st.caption("Defined Characters:")
    for c_name, c_desc in list(st.session_state.temp_char_map.items()):
        c1, c2 = st.columns([4, 1])
        c1.text(f"{c_name}: {c_desc}")
        if c2.button("🗑️", key=f"del_{c_name}"):
            del st.session_state.temp_char_map[c_name]
            st.rerun()

    st.divider()
    if st.button("💾 Save All Settings", type="primary", use_container_width=True):
        # Update current config object with all values
        if 'generation' not in current_config: current_config['generation'] = {}
        current_config['generation']['images_per_scene'] = img_count
        current_config['generation']['sounds_per_scene'] = snd_count
        current_config['generation']['sound_length_seconds'] = snd_len
        current_config['generation']['sound_loop'] = snd_loop
        
        current_config['title'] = title
        current_config['llm_model'] = llm_model
        current_config['visual_settings'] = {
            "master_style": m_style, "positive_prompt": p_prompt, "negative_prompt": n_prompt
        }
        current_config['character_map'] = st.session_state.temp_char_map
        current_config['sd_settings'] = {
            "sd_model": sd_m, "width": width, "height": height, "steps": steps, 
            "sampler_name": sampler, "scheduler": scheduler, "cfg_scale": cfg
        }
        # 'book_id' and 'book_filename' are preserved because we modify current_config in place
        
        save_config(current_config)
        st.success("✅ All Configuration Saved!")
        time.sleep(1)
        st.rerun()
    st.divider()
    st.markdown("#### 🔨 Export Story")
    st.caption("Convert your readable `.ink` script into the `.json` format required by the Player.")
    
    if st.button("⚙️ Compile .ink to .json", use_container_width=True):
        try:
            # Ensure paths are defined
            if 'output_path' not in locals():
                # Re-resolve paths if button is clicked outside main loop context
                c_id = current_config.get("book_id", "unknown_book")
                o_path = os.path.join(current_dir, "..", "data", "output", c_id)
                i_path = os.path.join(o_path, "adventure.ink")
                j_path = os.path.join(o_path, "adventure.json")
            else:
                # Use existing variables if available
                i_path = ink_file
                j_path = json_path
            
            # Run Inklecate
            subprocess.run(["inklecate", "-o", j_path, i_path], check=True, capture_output=True)
            update_game_manifest()
            st.success("✅ Compilation Successful! 'adventure.json' updated.")
            
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
            st.error(f"⚠️ Compilation Failed:\n{err_msg}")
        except Exception as e:
            st.error(f"Error: {e}")

if st.session_state.engine_ready and "architect" not in st.session_state:
    try:
        st.session_state.architect = AutonomousArchitect(os.path.join(BOOKS_DIR, current_book_filename))
        st.session_state.weaver = VisualWeaver()
        target_ink_path = os.path.join(weaver.output_dir, "adventure.ink")
        st.session_state.smith = InkSmith(current_config["book_id"])
    except: st.session_state.engine_ready = False

# --- 4. MAIN INTERFACE ---
# ==========================================
# 🎬 MAIN INTERFACE & LOGIC
# ==========================================

# 1. Output Paths
output_path = os.path.join(current_dir, "..", "data", "output", active_book_id)
os.makedirs(output_path, exist_ok=True)
ink_file = os.path.join(output_path, "adventure.ink")

# 2. Resume Helper
def get_resume_state(file_path):
    if not os.path.exists(file_path): return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.findall(r'~ last_node = "(.*?)"', content)
        return match[-1] if match else None
    except: return None

# 3. Render Title (ONLY ONCE)
st.title(f"🎬 Director Mode: {title}")

# ==========================================
# 🛑 STATE 1: SELECTION MENU (Engine OFF)
# ==========================================
if not st.session_state.engine_ready:
    st.markdown("### 🎬 Production Control")
    st.info("Select a mode to begin.")
    
    col1, col2 = st.columns(2)
    
    # [A] NEW PROJECT
    with col1:
        st.markdown("#### 🆕 New Project")
        st.caption("Erase history and start from the Intro.")
        
        # Check if old files exist for this book
        output_dir = os.path.join(current_dir, "..", "data", "output", active_book_id)
        assets_dir = os.path.join(output_dir, "assets")
        audio_dir = os.path.join(output_dir, "audio")
        old_files_exist = False
        old_file_count = 0
        
        if os.path.exists(assets_dir):
            old_file_count += len([f for f in os.listdir(assets_dir) if f.endswith(('.png', '.jpg', '.jpeg'))])
        if os.path.exists(audio_dir):
            old_file_count += len([f for f in os.listdir(audio_dir) if f.endswith(('.mp3', '.wav', '.ogg'))])
        
        old_files_exist = old_file_count > 0
        
        # Show warning if old files exist
        if old_files_exist:
            st.warning(f"⚠️ Found {old_file_count} old images/sounds from a previous session. Starting a new adventure will **delete all of them**.")
            
            # Show confirmation dialog
            if not st.session_state.get('confirm_cleanup', False):
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🚀 Continue & Clean Up", type="primary", use_container_width=True, key="btn_new_project_confirm"):
                        st.session_state.confirm_cleanup = True
                        st.rerun()
                with col_btn2:
                    st.button("❌ Cancel", disabled=True, use_container_width=True, key="btn_new_project_cancel")
            else:
                # User confirmed cleanup, proceed with new adventure
                st.session_state.confirm_cleanup = False
                
                # Delete old files
                deleted_count, success = cleanup_old_adventure_files(active_book_id, confirm_first=True)
                
                if success:
                    weaver = VisualWeaver()
                    print(f"ℹ️ VisualWeaver SD model on Start New Adventure: {getattr(weaver, 'sd_model', None)}")
                    st.session_state.weaver = weaver
                    # Setup Paths
                    target_ink_path = os.path.join(weaver.output_dir, "adventure.ink")
                    source_book_path = os.path.join(BOOKS_DIR, st.session_state.get("local_sel", current_config.get("book_filename")))
                    # Initialize Workers
                    st.session_state.smith = InkSmith(current_config["book_id"])
                    st.session_state.architect = AutonomousArchitect(source_book_path)
                    
                    # Reset all session state image/audio keys
                    for key in list(st.session_state.keys()):
                        if 'generated_images_' in key or 'generated_sfx_' in key or 'scene_images_completed_' in key or 'awaiting_sound_' in key or 'reward_selected_' in key or 'picking_reward' in key:
                            st.session_state.pop(key, None)
                    
                    st.session_state.engine_ready = True
                    st.success(f"✅ Cleaned up {deleted_count} old files. Starting fresh!")
                    st.rerun()
                else:
                    st.error("❌ Could not clean up old files. Please manually delete them and try again.")
        else:
            # No old files, proceed normally
            # Unique Key: btn_new_project
            if st.button("🚀 Start New Adventure    ", type="primary", use_container_width=True, key="btn_new_project"):
                weaver = VisualWeaver()
                print(f"ℹ️ VisualWeaver SD model on Start New Adventure: {getattr(weaver, 'sd_model', None)}")
                st.session_state.weaver = weaver
                # Setup Paths
                target_ink_path = os.path.join(weaver.output_dir, "adventure.ink")
                source_book_path = os.path.join(BOOKS_DIR, st.session_state.get("local_sel", current_config.get("book_filename")))
                # Initialize Workers
                st.session_state.smith = InkSmith(current_config["book_id"])
                st.session_state.architect = AutonomousArchitect(source_book_path)
                
                st.session_state.engine_ready = True
                st.rerun()

    # [B] RESUME SESSION
    with col2:
        st.markdown("#### ⏯️ Resume Session")
        st.caption("Continue from the last saved .ink file.")
        last_node = get_resume_state(ink_file)
        
        if last_node:
            st.success(f"Found Save: `{last_node}`")
            # Unique Key: btn_resume_active
            if st.button("📂 Resume Adventure", use_container_width=True, key="btn_resume_active"):
                weaver = VisualWeaver()
                print(f"ℹ️ VisualWeaver SD model on Resume: {getattr(weaver, 'sd_model', None)}")
                st.session_state.weaver = weaver

                target_ink_path = os.path.join(weaver.output_dir, "adventure.ink")
                source_book_path = os.path.join(BOOKS_DIR, st.session_state.get("local_sel", current_config.get("book_filename")))
                # Use the selectbox value as a fallback for the filename
                active_filename = st.session_state.get("local_sel", current_config.get("book_filename"))
                if not active_filename:
                    st.error("Could not find source text filename. Please re-select it in the Library tab.")
                    st.stop()        
                try:
                    with st.spinner("🧠 Waking up the Architect (connecting to Google)..."):
                        # 1. Initialize Components
                        st.session_state.smith = InkSmith(current_config["book_id"])
                        st.session_state.architect = AutonomousArchitect(source_book_path)
                        
                        # 2. Read the existing Ink file
                        if os.path.exists(st.session_state.smith.ink_path):
                            with open(st.session_state.smith.ink_path, 'r', encoding='utf-8') as f:
                                existing_ink = f.read()
                            
                            # 3. Attempt the Resume Handshake
                            response = st.session_state.architect.resume_session(existing_ink)
                            
                            if response is None:
                                raise ValueError("Architect returned 'None'. Check console logs for API errors.")
                                
                            st.success(f"Architect Online! Last known node: {response.get('last_node', 'Unknown')}")
                
                except Exception as e:
                    st.error(f"❌ CONNECTION FAILED: {str(e)}")
                    # Print full error to the terminal for debugging
                    print(f"CRITICAL ERROR: {e}") 
                    st.stop()
                st.session_state.smith = InkSmith(current_config["book_id"])
                st.session_state.scene_data = None
                st.session_state.architect = AutonomousArchitect(source_book_path)
                st.session_state.generated_images = []
                st.session_state.picking_reward = False
                st.session_state.engine_ready = True
                st.rerun()
        else:
            st.warning("No valid save file found.")
            st.button("📂 Resume Adventure", disabled=True, use_container_width=True, key="btn_resume_disabled")

# ==========================================
# 🚀 STATE 2: PRODUCTION LOOP (Engine ON)
# ==========================================
else:
    # 🛑 SESSION CONTROL (Sidebar)
    with st.sidebar:
        st.divider()
        st.markdown("### 🛑 Session Control")
        
        # MODE 1: A project is currently active (LLM is "Live")
        if st.session_state.engine_ready:
            if not st.session_state.get('confirm_stop', False):
                if st.button("⏹️ Stop Current Project", type="secondary", use_container_width=True, key="btn_stop_init"):
                    st.session_state.confirm_stop = True
                    st.rerun()
            else:
                st.warning("⚠️ Progress on the current scene will be lost!")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("Confirm Stop", type="primary", key="btn_stop_final", use_container_width=True):
                        st.session_state.engine_ready = False
                        st.session_state.scene_data = None
                        st.session_state.confirm_stop = False
                        st.session_state.current_step = "narrative" 
                        st.rerun()
                with col_no:
                    if st.button("Cancel", key="btn_stop_cancel", use_container_width=True):
                        st.session_state.confirm_stop = False
                        st.rerun()
        
        # MODE 2: Session is stopped (At the Library/Config screen)
        else:
            st.success("Project inactive. Director is idling.")
            if st.button("🔌 Kill Server & Close", type="primary", use_container_width=True, key="btn_exit_app"):
                st.info("Shutting down terminal... Goodbye.")
                import os
                os._exit(0) # Immediately kills the Python process
        
               
        # 3. 🛡️ THE FIREWALL
        # If the user is currently looking at the warning OR if the engine is off,
        # we STOP the script right here so it never reaches the Architect/LLM code below.
        if st.session_state.get('confirm_stop') or st.session_state.engine_ready == False:
            st.stop()
    # --- WORKER CONNECTION ---
    if "architect" not in st.session_state:
        try:
            with st.spinner("🔌 Reconnecting Engine..."):
                st.session_state.architect = AutonomousArchitect(os.path.join(BOOKS_DIR, current_book_filename))
                st.session_state.weaver = VisualWeaver()
                print(f"ℹ️ VisualWeaver SD model on Reconnect: {getattr(st.session_state.weaver, 'sd_model', None)}")
                target_ink_path = os.path.join(weaver.output_dir, "adventure.ink")
                st.session_state.smith = InkSmith(current_config["book_id"])
        except Exception as e:
            st.error(f"Connection Failed: {e}")
            st.session_state.engine_ready = False
            st.stop()
    
    # Only grab workers from state if the engine is actually running
    if st.session_state.engine_ready:
        architect = st.session_state.architect
        weaver = st.session_state.weaver
        smith = st.session_state.get("smith") 
        
        # Final safety check: if smith is missing for some reason, stop
        if not smith:
            st.error("InkSmith initialization failed. Please restart the project.")
            st.stop()
        # otherwise continue


    # --- STEP 1: NARRATIVE DRAFTING ---
    if st.session_state.current_step == "narrative":
        st.subheader(f"📖 Scripting: {st.session_state.node_id}")
        
        # 1. GENERATE (If Empty)
        if st.session_state.scene_data is None:
            with st.spinner("🕵️ Architect is drafting..."):
                try:
                    if st.session_state.node_id == "intro":
                        data = architect.initialize_engine()
                    else:
                        data = architect.generate_main_beat(st.session_state.node_id)
                except Exception as e:
                    st.error(f"Architect exception: {e}")
                    import traceback
                    traceback.print_exc()
                    st.stop()
                
                if data is None:
                    st.error("Architect failed. Please Stop and Resume.")
                    st.stop()
                
                if 'scene_id' not in data: data['scene_id'] = f"node_{int(time.time())}"
                st.session_state.scene_data = data
                st.rerun()
        
        # 2. EDITING INTERFACE
        with st.form("script_form"):
            scene = st.session_state.scene_data
            
            # Main Story Block
            col_main, col_vis = st.columns([2, 1])
            with col_main:
                txt = st.text_area("📖 Story Text", value=scene.get('scene_text', ''), height=200)
            with col_vis:
                vp = st.text_area("🎨 Scene Visual Prompt", value=scene.get('visual_prompt', ''), height=200)
                ap = st.text_input("🔊 Audio Prompt (for SFX)", value=scene.get('audio_prompt', ''), help="A short prompt describing ambience/mood and dominant textures, suitable for a sound generator (e.g., 'soft wind, distant chimes, melancholic, loopable')")
            
            st.divider()
            st.markdown("### 🔀 Choices & Outcomes")
            
            updated_choices = []
            # Unified Loop for all 3 choices
            for i, c in enumerate(scene.get('choices', [])):
                
                # We use specific colors/icons for types
                icons = {"golden": "🌟", "exquisite": "💎", "bad": "💀"}
                icon = icons.get(c['type'], "➡️")
                
                with st.expander(f"{icon} Option {i+1}: {c['type'].title()}", expanded=True):
                    # Choice Text & Outcome Text (Standard for ALL)
                    c_txt = st.text_input("Choice Text", value=c.get('text', ''), key=f"c_txt_{i}")
                    c_out = st.text_area("Outcome Text", value=c.get('outcome_text', ''), height=68, key=f"c_out_{i}", 
                                         help="The immediate narrative result of picking this choice.")
                    # Conditional Extra Field: Reward Prompt
                    if c['type'] == 'exquisite':
                        st.markdown("---")
                        c_rew = st.text_area(
                            "💎 Reward Visual Prompt", 
                            value=c.get('reward_visual_prompt', vp), # Fallback to scene prompt if missing
                            height=68, 
                            key=f"c_rew_{i}",
                            help="Describe the reward image based on the outcome text above."
                        )
                        c['reward_visual_prompt'] = c_rew
                    
                    # Save updates
                    c['text'] = c_txt
                    c['outcome_text'] = c_out
                    updated_choices.append(c)

            if st.form_submit_button("🎨 Confirm & Generate Art", type="primary"):
                st.session_state.scene_data['scene_text'] = txt
                st.session_state.scene_data['visual_prompt'] = vp
                # Save audio prompt (editable by the author)
                st.session_state.scene_data['audio_prompt'] = ap
                st.session_state.scene_data['choices'] = updated_choices
                st.session_state.current_step = "art"
                st.rerun()
    # --- STEP 2: ART SELECTION (REPLACED) ---
    elif st.session_state.current_step == "art":
        scene = st.session_state.scene_data
        base_id = scene.get('scene_id', 'unknown')
        weaver = st.session_state.weaver
        
        # Paths
        final_main_img = os.path.join(weaver.output_dir, f"{base_id}_final.png")
        final_reward_img = os.path.join(weaver.output_dir, f"{base_id}_REW_final.png")

        # --- PHASE 1: SCENE IMAGES ---
        # check if final exists or if we have candidates in memory
        if not os.path.exists(final_main_img):
            st.subheader(f"1. Scene Art: {base_id}")
            
            # KEY FIX: Check Session State before generating to prevent Loop
            gen_key = f"gen_main_{base_id}"
            if gen_key not in st.session_state:
                is_online, err_msg = weaver.check_connection()
                if not is_online:
                    st.warning(f"⚠️ Connection Failed: {err_msg}")
                    st.info("If WebUI is open in browser, you likely need to add '--api' to your launch script.")
                    
                    c1, c2 = st.columns(2)
                    if c1.button("🔄 Retry Connection"):
                        st.rerun()
                    if c2.button("❌ Terminate & Exit"):
                        st.error("Maker halted. Please launch WebForge UI and restart.")
                        st.stop()
                    
                    st.stop() # Wait for user input

                with st.spinner("💎 Painting Scene..."):
                    # 1. Create the empty progress bar in the UI
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # 2. Define the callback function
                    def update_ui(percent, current, total):
                        progress_bar.progress(percent)
                        status_text.text(f"🎨 Painting... Image {current} of {total} ({percent}%)")
                        
                    # 3. Pass this function to the weaver
                    # Note: We add 'callback=update_ui' to the arguments
                    paths = weaver.generate_batch(
                        prompt=prompt, 
                        count=3, 
                        base_filename=node_id,
                        callback=update_ui 
                    )
                    
                    # 4. Cleanup after done
                    status_text.text("✅ Generation Complete!")
                    progress_bar.empty()
                    cnt = current_config.get('generation', {}).get('images_per_scene', 4)
                    imgs = weaver.generate_batch(scene['visual_prompt'], base_id, count=cnt)
                    st.session_state[gen_key] = imgs
                    st.rerun()
            
            # Display Candidates
            candidates = st.session_state[gen_key]
            if candidates:
                cols = st.columns(len(candidates))
                for idx, img_path in enumerate(candidates):
                    with cols[idx]:
                        st.image(img_path)
                        if st.button("Select", key=f"sel_main_{idx}"):
                            shutil.move(img_path, final_main_img)
                            # Cleanup others
                            for c in candidates: 
                                if os.path.exists(c) and c != final_main_img: os.remove(c)
                            st.session_state.pop(gen_key, None) # Clear memory
                            st.rerun()
            st.stop() # Stop here until selection is made

        # --- PHASE 2: REWARD IMAGES (If applicable) ---
        exquisite_choice = next((c for c in scene['choices'] if c['type'] == 'exquisite'), None)
        if exquisite_choice:
            if not os.path.exists(final_reward_img):
                st.subheader(f"2. Reward Art: {base_id}_REW")
                
                gen_key_rew = f"gen_rew_{base_id}"
                if gen_key_rew not in st.session_state:
                    is_online, err_msg = weaver.check_connection()
                    if not is_online:
                        st.warning(f"⚠️ Connection Failed: {err_msg}")
                        c1, c2 = st.columns(2)
                        if c1.button("🔄 Retry", key="rew_retry"): st.rerun()
                        if c2.button("❌ Terminate & Exit", key="rew_exit"):
                            st.error("Maker halted. Please launch WebForge UI and restart.")
                            st.stop()
                        st.stop()

                    with st.spinner("💎 Painting Reward..."):
                        cnt = current_config.get('generation', {}).get('images_per_scene', 4)
                        imgs = weaver.generate_batch(exquisite_choice.get('reward_visual_prompt'), f"{base_id}_REW", count=cnt)
                        st.session_state[gen_key_rew] = imgs
                        st.rerun()

                candidates = st.session_state[gen_key_rew]
                if candidates:
                    cols = st.columns(len(candidates))
                    for idx, img_path in enumerate(candidates):
                        with cols[idx]:
                            st.image(img_path)
                            if st.button("Select", key=f"sel_rew_{idx}"):
                                shutil.move(img_path, final_reward_img)
                                for c in candidates:
                                    if os.path.exists(c) and c != final_reward_img: os.remove(c)
                                st.session_state.pop(gen_key_rew, None)
                                st.rerun()
                st.stop()

        # --- PHASE 3: SOUND GENERATION ---
        # We only reach here if images are done.
        audio_dir = os.path.join(current_dir, "..", "data", "output", current_config['book_id'], "audio")
        final_sound = os.path.join(audio_dir, f"{base_id}_final.mp3")
        
        # Check config
        snd_count = current_config.get('generation', {}).get('sounds_per_scene', 1)

        if snd_count > 0 and not os.path.exists(final_sound):
            st.subheader("3. Audio Atmosphere")
            
            snd_key = f"gen_snd_{base_id}"
            if snd_key not in st.session_state:
                # Generate Sounds
                sw = SoundWeaver()
                is_loop = current_config.get('generation', {}).get('sound_loop', False)
                snd_dur = current_config.get('generation', {}).get('sound_length_seconds', 5)
                
                with st.spinner(f"🎧 Composing {snd_count} Audio Candidates..."):
                    snds = sw.generate_candidates(
                        current_config['book_id'], base_id, 
                        scene.get('audio_prompt', scene['visual_prompt']), 
                        count=snd_count,
                        length_seconds=snd_dur,
                        model="eleven_text_to_sound_v2",
                        loop=is_loop
                    )
                    st.session_state[snd_key] = snds
                    st.rerun()

            # Display Sound Candidates
            sounds = st.session_state.get(snd_key, [])
            if sounds:
                st.write("Select your preferred audio:")
                for idx, s in enumerate(sounds):
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        if st.button(f"Select #{idx+1}", key=f"sel_snd_{base_id}_{idx}"):
                            os.makedirs(audio_dir, exist_ok=True)
                            src = os.path.join(current_dir, "..", s['file'])
                            shutil.copy(src, final_sound)
                            st.session_state['sound_selected_map'] = {base_id: f"{base_id}_final.mp3"}
                            # 3. Cleanup: Delete ALL candidates (MP3 + JSON)
                            # Since we copied the winner to '_final.mp3', we can safely wipe the temp files.
                            for cand in sounds:
                                try:
                                    # Resolve paths
                                    cand_path = os.path.join(current_dir, "..", cand['file'])
                                    json_path = cand_path.replace(".mp3", ".json")
                                    
                                    # Delete MP3
                                    if os.path.exists(cand_path): 
                                        os.remove(cand_path)
                                    
                                    # Delete JSON Metadata
                                    if os.path.exists(json_path): 
                                        os.remove(json_path)
                                        
                                except Exception as e:
                                    print(f"⚠️ Could not delete temp file: {e}")

                            # Clear the candidates list so they disappear from UI
                            st.session_state[snd_key] = []
                            st.rerun()
                    with c2:
                        # Display metadata tooltips from the JSON data if available
                        meta_info = s.get('meta', {})
                        prompt_text = meta_info.get('prompt', 'No prompt data')
                        st.audio(s['file'])
                        st.caption(f"📝 *{prompt_text[:60]}...*")
            st.stop()

        # --- PHASE 4: FINALIZE ---
        st.success("✅ Scene Assets Complete!")
        if st.button("🎬 Write to Script & Continue"):
            finalize_ink_node(base_id, scene)