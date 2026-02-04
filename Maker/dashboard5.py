import os
import json
import shutil
import time
import requests
import sqlite3
import re
import streamlit as st
from dotenv import load_dotenv

# --- 1. SETUP & PATHS ---
st.set_page_config(page_title="Lume & Lore Director", layout="wide", page_icon="🕯️")

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '..', '.env')
load_dotenv(os.path.join(current_dir, '..', '.env'))

from architect import AutonomousArchitect
from visual_weaver import VisualWeaver
from ink_smith import InkSmith

if "engine_ready" not in st.session_state:
    st.session_state.engine_ready = False
    st.session_state.current_step = "narrative"
    st.session_state.node_id = "intro"
    st.session_state.scene_data = None
    st.session_state.generated_images = []
    
BOOKS_DIR = os.path.join(current_dir, "..", "data", "books")
CONFIG_PATH = os.path.join(current_dir, "..", "book_config.json")
DB_NAME = "gutenberg_index.db"
DEFAULT_LLMS = ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"]

# --- 2. HELPER FUNCTIONS ---

def finalize_ink_node(base_id, scene):
    curr_id = st.session_state.node_id
    next_node_id = f"{base_id}_next"
    
    if curr_id == "intro":
        st.session_state.smith.write_intro(scene, next_node_id)
    else:
        st.session_state.smith.write_main_node_start(base_id, scene['scene_text'], f"{base_id}_main", scene['choices'], next_node_id)
    
    st.session_state.smith.write_choice_outcomes(base_id, scene['choices'], next_node_id)
    
    # Reset state for next scene
    st.session_state.node_id = next_node_id
    st.session_state.current_step = "narrative"
    st.session_state.scene_data = None
    st.session_state.generated_images = []
    st.session_state.picking_reward = False
    st.rerun()

def load_config():
    config = {
        "book_id": "default", "title": "New Project", "llm_model": "gemini-2.0-flash-exp",
        "supported_llms": DEFAULT_LLMS,
        "sd_settings": {"steps": 30, "cfg_scale": 7, "sampler_name": "Euler a", "scheduler": "Automatic"},
        "visual_settings": {"master_style": "Oil painting", "positive_prompt": "", "negative_prompt": ""}
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config.update(json.load(f))
        except: pass
    return config

def save_config(new_config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(new_config, f, indent=4)

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

# --- 3. DERIVE BOOK ID GLOBALLY (Fixes NameError) ---
st.sidebar.title("⚙️ Engine Settings")
tab_lib, tab_conf = st.sidebar.tabs(["📚 Library", "🔧 Config"])

os.makedirs(BOOKS_DIR, exist_ok=True)
available_books = [f for f in os.listdir(BOOKS_DIR) if f.endswith(".txt")]
current_config = load_config()

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
        active_book_id = "".join(x for x in os.path.splitext(current_book_filename)[0] if x.isalnum() or x in "_-")

with tab_conf:
    current_config = load_config()
    st.markdown("#### 📝 Project Metadata")
    title = st.text_input("Project Title", value=current_config.get("title", "New Adventure"), key="c_title")
    
    st.markdown("#### 🧠 AI Brain")
    llms = current_config.get("supported_llms", DEFAULT_LLMS)
    def_llm = current_config.get("llm_model", "gemini-2.0-flash-exp")
    llm_model = st.selectbox("LLM Model", llms, index=llms.index(def_llm) if def_llm in llms else 0, key="c_llm")

    st.markdown("#### 🎨 Visual Style")
    vis = current_config.get("visual_settings", {})
    m_style = st.text_area("Master Style", value=vis.get("master_style", ""), key="c_style")
    p_prompt = st.text_area("Positive", value=vis.get("positive_prompt", ""), key="c_pos")
    n_prompt = st.text_area("Negative", value=vis.get("negative_prompt", ""), key="c_neg")

    with st.expander("⚙️ SD Advanced"):
        sd = current_config.get("sd_settings", {})
        try:
            models_resp = requests.get("http://127.0.0.1:7860/sdapi/v1/sd-models", timeout=2)
            model_list = [m['title'] for m in models_resp.json()] if models_resp.status_code == 200 else []
        except: model_list = []
        sd_m = st.selectbox("SD Model", model_list if model_list else [sd.get("sd_model", "")], key="c_sd_m")
        col_w, col_h = st.columns(2)
        with col_w: 
            width = st.slider("Width", 256, 1024, sd.get("width", 512), 64, key="c_sd_w")
        with col_h: 
            height = st.slider("Height", 256, 1024, sd.get("height", 768), 64, key="c_sd_h")
        steps = st.slider("Steps", 10, 100, sd.get("steps", 30), key="c_sd_s")
        cfg = st.slider("CFG", 1.0, 20.0, float(sd.get("cfg_scale", 7.0)), key="c_sd_c")
        sampler = st.text_input("Sampler", value=sd.get("sampler_name", "Euler a"), key="c_sd_samp")
        scheduler = st.text_input("Scheduler", value=sd.get("scheduler", "Automatic"), key="c_sd_sched")

    if st.button("💾 Save Config Settings", type="primary", key="c_save"):
        new_conf = {
            "title": title, "llm_model": llm_model, "supported_llms": llms,
            "visual_settings": {"master_style": m_style, "positive_prompt": p_prompt, "negative_prompt": n_prompt},
            "sd_settings": {
                "sd_model": sd_m, "width": width, "height": height, "steps": steps, "sampler_name": sampler, 
                "scheduler": scheduler, "cfg_scale": cfg
            },
            "book_id": active_book_id
        }
        save_config(new_conf); st.toast("Saved!")

if st.session_state.engine_ready and "architect" not in st.session_state:
    try:
        st.session_state.architect = AutonomousArchitect(os.path.join(BOOKS_DIR, current_book_filename))
        st.session_state.weaver = VisualWeaver()
        st.session_state.smith = InkSmith(active_book_id)
    except: st.session_state.engine_ready = False

# --- 4. MAIN INTERFACE ---
st.title(f"🎬 Director Mode: {current_config.get('title')}")

# Define the path to the current project's script
output_path = os.path.join(current_dir, "..", "data", "output", active_book_id)
ink_file = os.path.join(output_path, "adventure.ink")

# --- SELF-HEALING LOGIC ---
# This checks if the AI 'Architect' disappeared (common after a browser refresh)
if st.session_state.get("engine_ready") and "architect" not in st.session_state:
    with st.spinner("🔄 Reconnecting to Director..."):
        try:
            # We rebuild the tools from the saved config
            st.session_state.architect = AutonomousArchitect(os.path.join(BOOKS_DIR, current_book_filename))
            st.session_state.weaver = VisualWeaver()
            st.session_state.smith = InkSmith(active_book_id)
        except Exception as e:
            st.error(f"Reconnection failed: {e}")
            st.session_state.engine_ready = False

# --- THE START BUTTON (Only shows if engine isn't ready) ---
if not st.session_state.engine_ready:
    st.info("Configuration loaded. Press below to begin the adaptation.")
    if st.button("🚀 Start Scripting", type="primary", use_container_width=True):
        if not current_book_filename:
            st.error("Please select a book in the Library tab first!")
        else:
            with st.status("🎬 Initializing Engine...") as s:
                # Step 1: Architect (Talks to Google Gemini)
                s.write("🧠 Connecting to AI Architect (Uploading Book)...")
                st.session_state.architect = AutonomousArchitect(os.path.join(BOOKS_DIR, current_book_filename))
                
                # Step 2: Weaver (Talks to SD Forge)
                s.write("🎨 Connecting to Visual Weaver (Checking SD Forge)...")
                st.session_state.weaver = VisualWeaver()
                
                # Step 3: Smith (Sets up Ink file)
                s.write("✍️ Connecting to Ink Smith (Creating File)...")
                st.session_state.smith = InkSmith(active_book_id)
                
                s.update(label="✅ Engine Online! Starting story...", state="complete")
                st.session_state.engine_ready = True
                time.sleep(1) # Give it a second to breathe
                st.rerun()
else:
    # 🛠️ FIX: Use these handles so you don't have to type 'st.session_state' everywhere
    arc = st.session_state.architect
    smth = st.session_state.smith
    wvr = st.session_state.weaver

# --- 6. MAIN INTERFACE GATEKEEPER ---
st.title(f"🎬 Director Mode: {title}")

output_path = os.path.join(current_dir, "..", "data", "output", active_book_id)
os.makedirs(output_path, exist_ok=True)
ink_file = os.path.join(output_path, "adventure.ink")

def get_resume_state(file_path):
    """Scans the .ink file for the last visited node."""
    if not os.path.exists(file_path): return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.findall(r'~ last_node = "(.*?)"', content)
        return match[-1] if match else None
    except: return None

# === STATE 1: SELECTION MENU (Engine OFF) ===
if not st.session_state.engine_ready:
    st.markdown("### 🎬 Production Control")
    st.info("Select a mode to begin.")
    
    col1, col2 = st.columns(2)
    
    # [A] START NEW PRODUCTION
    with col1:
        st.markdown("#### 🆕 New Project")
        st.caption("Erase history and start from the Intro.")
        # 🛠️ FIX: Added key="btn_new_project" to prevent ID collisions
        if st.button("🚀 Start Scripting", type="primary", use_container_width=True, key="btn_new_project"):
            if not current_book_filename:
                st.error("⚠️ Please select a book in the Library tab first!")
            else:
                # 🛠️ HARD RESET
                st.session_state.node_id = "intro"
                st.session_state.scene_data = None
                st.session_state.generated_images = []
                st.session_state.picking_reward = False
                st.session_state.engine_ready = True
                st.rerun()

    # [B] RESUME EXISTING
    with col2:
        st.markdown("#### ⏯️ Resume Session")
        st.caption("Continue from the last saved .ink file.")
        last_node = get_resume_state(ink_file)
        
        if last_node:
            st.success(f"Found Save: `{last_node}`")
            # 🛠️ FIX: Added key="btn_resume_active"
            if st.button("📂 Resume Adventure", use_container_width=True, key="btn_resume_active"):
                st.session_state.node_id = f"{last_node}_next"
                st.session_state.scene_data = None
                st.session_state.generated_images = []
                st.session_state.picking_reward = False
                st.session_state.engine_ready = True
                st.rerun()
        else:
            st.warning("No valid save file found.")
            # 🛠️ FIX: Added key="btn_resume_disabled"
            st.button("📂 Resume Adventure", disabled=True, use_container_width=True, key="btn_resume_disabled")

# === STATE 2: PRODUCTION LOOP (Engine ON) ===
else:
    # 🛑 STOP BUTTON (In Sidebar)
    with st.sidebar:
        st.divider()
        st.markdown("### 🛑 Session Control")
        if st.button("⏹️ Stop & Save", type="secondary", use_container_width=True):
            st.session_state.engine_ready = False
            st.session_state.scene_data = None
            st.rerun()

    # --- WORKER INITIALIZATION ---
    # Self-healing logic to reconnect tools if browser refreshed
    if "architect" not in st.session_state:
        try:
            with st.spinner("🔌 Reconnecting Engine..."):
                st.session_state.architect = AutonomousArchitect(os.path.join(BOOKS_DIR, current_book_filename))
                st.session_state.weaver = VisualWeaver()
                st.session_state.smith = InkSmith(active_book_id)
        except Exception as e:
            st.error(f"Connection Failed: {e}")
            st.session_state.engine_ready = False
            st.stop()

    # Define workers for easy access
    architect = st.session_state.architect
    weaver = st.session_state.weaver
    smith = st.session_state.smith

    # --- STEP 1: NARRATIVE DRAFTING ---
    if st.session_state.current_step == "narrative":
        st.subheader(f"📖 Scripting: {st.session_state.node_id}")
        
        if st.session_state.scene_data is None:
            with st.spinner("🕵️ Architect is drafting..."):
                if st.session_state.node_id == "intro":
                    data = architect.initialize_engine()
                else:
                    data = architect.generate_main_beat(st.session_state.node_id)
                
                # Validation
                if data is None:
                    st.error("Architect returned empty data. Please Stop and Resume.")
                    st.stop()
                    
                if 'scene_id' not in data: 
                    data['scene_id'] = f"node_{int(time.time())}"
                
                st.session_state.scene_data = data
                st.rerun()
        
        with st.form("script_form"):
            scene = st.session_state.scene_data
            txt = st.text_area("Narrative", value=scene.get('scene_text', ''), height=250)
            vp = st.text_area("Visual Prompt", value=scene.get('visual_prompt', ''), height=80)
            
            # Show choices for review
            st.caption("Planned Choices:")
            for c in scene.get('choices', []):
                st.text(f"- [{c['type'].upper()}] {c['text']}")

            if st.form_submit_button("🎨 Confirm & Generate Art"):
                st.session_state.scene_data['scene_text'] = txt
                st.session_state.scene_data['visual_prompt'] = vp
                st.session_state.current_step = "art"
                st.rerun()

    # STEP 2: ART (Visualizing & Writing to Ink)
    elif st.session_state.current_step == "art":
        scene = st.session_state.scene_data
        is_reward_phase = st.session_state.get('picking_reward', False)
        
        header = "💎 Selecting Reward Art" if is_reward_phase else "🎨 Selecting Scene Art"
        st.subheader(f"{header}: {st.session_state.node_id}")
        
        # 🛠️ FIX: Show the prompt so you can compare it to results
        st.info(f"**Visual Prompt:** {scene.get('visual_prompt')}")

        if not st.session_state.generated_images:
            with st.spinner("🎨 Painting batch..."):
                # Use reward-specific prompt if in reward phase, otherwise scene prompt
                prompt = scene.get('visual_prompt')
                slug = f"{scene.get('scene_id')}_reward" if is_reward_phase else scene.get('scene_id')
                st.session_state.generated_images = weaver.generate_batch(prompt, slug)
                st.rerun()

        cols = st.columns(4)
        for i, img_path in enumerate(st.session_state.generated_images):
            with cols[i]:
                st.image(img_path)
                if st.button(f"Select #{i+1}", key=f"sel_{i}"):
                    base_id = scene.get('scene_id')
                    
                    if not is_reward_phase:
                        # --- PHASE 1: Scene Image ---
                        target = os.path.join(weaver.output_dir, f"{base_id}_main.png")
                        shutil.move(img_path, target)
                        
                        # Cleanup others
                        for temp in st.session_state.generated_images:
                            if temp != img_path and os.path.exists(temp): os.remove(temp)
                        
                        # Check if we need to pick a reward
                        ex_idx = next((idx for idx, c in enumerate(scene['choices']) if c['type'] == 'exquisite'), None)
                        if ex_idx is not None:
                            st.session_state.picking_reward = True
                            st.session_state.ex_choice_idx = ex_idx
                            st.session_state.generated_images = [] # Clear for new batch
                            st.rerun()
                        else:
                            # No reward? Finish immediately
                            finalize_ink_node(base_id, scene)
                    else:
                        # --- PHASE 2: Reward Image ---
                        idx = st.session_state.ex_choice_idx
                        target = os.path.join(weaver.output_dir, f"{base_id}_result_{idx+1}_reward.png")
                        shutil.move(img_path, target)
                        # Finalize
                        finalize_ink_node(base_id, scene)   

                        # Finish and write to Ink
                        curr_id = st.session_state.node_id
                        next_node_id = f"{base_id}_next"
                        
                        if curr_id == "intro":
                            smith.write_intro(scene, next_node_id)
                        else:
                            smith.write_main_node_start(base_id, scene['scene_text'], f"{base_id}_main", scene['choices'], next_node_id)
                        
                        smith.write_choice_outcomes(base_id, scene['choices'], next_node_id)

                        # Reset State
                        st.session_state.node_id = next_node_id
                        st.session_state.current_step = "narrative"
                        st.session_state.scene_data = None
                        st.session_state.generated_images = []
                        st.session_state.picking_reward = False
                        st.rerun()
                        