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
load_dotenv(env_path)

from architect import AutonomousArchitect
from visual_weaver import VisualWeaver
from ink_smith import InkSmith

# --- INITIALIZE SESSION STATE ---
# This must run before any other logic!
if "engine_ready" not in st.session_state:
    st.session_state.engine_ready = False

if "current_step" not in st.session_state:
    st.session_state.current_step = "narrative"

if "node_id" not in st.session_state:
    st.session_state.node_id = "intro"

if "scene_data" not in st.session_state:
    st.session_state.scene_data = None

if "generated_images" not in st.session_state:
    st.session_state.generated_images = []
    
BOOKS_DIR = os.path.join(current_dir, "..", "data", "books")
CONFIG_PATH = os.path.join(current_dir, "..", "book_config.json")
DB_NAME = "gutenberg_index.db"
DEFAULT_LLMS = ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"]

# --- 2. HELPER FUNCTIONS ---
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
os.makedirs(BOOKS_DIR, exist_ok=True)
available_books = [f for f in os.listdir(BOOKS_DIR) if f.endswith(".txt")]
selected_book_file = st.sidebar.selectbox("Active Source Text", available_books) if available_books else None
active_book_id = "".join(x for x in os.path.splitext(selected_book_file)[0] if x.isalnum() or x in "_-") if selected_book_file else "default"

# --- 3. CONSOLIDATED SIDEBAR ---
st.sidebar.title("⚙️ Engine Settings")

os.makedirs(BOOKS_DIR, exist_ok=True)
available_books = [f for f in os.listdir(BOOKS_DIR) if f.endswith(".txt")]
tab_lib, tab_conf = st.sidebar.tabs(["📚 Library", "🔧 Config"])

# GLOBAL STATE FOR BOOK SELECTION
active_book_id = "default"
current_book_filename = None

# --- 3. SIDEBAR (RENDERED FIRST) ---
st.sidebar.title("⚙️ Engine Settings")
tab_lib, tab_conf = st.sidebar.tabs(["📚 Library", "🔧 Config"])

os.makedirs(BOOKS_DIR, exist_ok=True)
available_books = [f for f in os.listdir(BOOKS_DIR) if f.endswith(".txt")]

# Variables to be set in Library Tab but used globally
active_book_id = "default"
current_book_filename = None

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
        sd_model = st.text_input("Model Checkpoint", value=sd.get("sd_model", ""), key="c_sd_m")
        steps = st.slider("Steps", 10, 100, sd.get("steps", 30), key="c_sd_s")
        cfg = st.slider("CFG", 1.0, 20.0, float(sd.get("cfg_scale", 7.0)), key="c_sd_c")
        sampler = st.text_input("Sampler", value=sd.get("sampler_name", "Euler a"), key="c_sd_samp")
        scheduler = st.text_input("Scheduler", value=sd.get("scheduler", "Automatic"), key="c_sd_sched")

    if st.button("💾 Save Config Settings", type="primary", key="c_save"):
        new_conf = {
            "title": title, "llm_model": llm_model, "supported_llms": llms,
            "visual_settings": {"master_style": m_style, "positive_prompt": p_prompt, "negative_prompt": n_prompt},
            "sd_settings": {
                "sd_model": sd_model, "steps": steps, "sampler_name": sampler, 
                "scheduler": scheduler, "cfg_scale": cfg
            },
            "book_id": active_book_id
        }
        save_config(new_conf); st.toast("Saved!")

# --- 4. MAIN INTERFACE ---
st.title(f"🎬 Director Mode: {title}")

# Define the path to the current project's script
output_path = os.path.join(current_dir, "..", "data", "output", active_book_id)
ink_file = os.path.join(output_path, "adventure.ink")

# --- 4. MAIN INTERFACE GATE ---
st.title(f"🎬 Director Mode: {load_config().get('title')}")

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
        with st.status("Initializing Engine...") as status:
            # 1. Save the final config
            c = load_config(); c["book_id"] = active_book_id; save_config(c)
            
            # 2. Boot up the tools
            st.session_state.architect = AutonomousArchitect(os.path.join(BOOKS_DIR, current_book_filename))
            st.session_state.weaver = VisualWeaver()
            st.session_state.smith = InkSmith(active_book_id)
            
            # 3. Mark as ready
            st.session_state.engine_ready = True
            st.rerun()

# --- 5. MAIN INTERFACE GATE ---
    st.title(f"🎬 Director Mode: {load_config().get('title')}")
    st.markdown("### 📋 Pre-Production Check")
    
    # 📊 Sidebar Progress Stats
    if os.path.exists(ink_file):
        with open(ink_file, "r") as f:
            content = f.read()
            node_count = content.count("== node_") + content.count("== intro ==")
        st.sidebar.markdown("---")
        st.sidebar.subheader("📈 Chapter Summary")
        st.sidebar.metric("Nodes Completed", node_count)
        st.sidebar.info("System has detected an existing script for this project.")
    
    c1, c2 = st.columns(2)
    with c1: st.metric("Source Book", active_book_id)
    with c2: st.metric("AI Brain", llm_model)

    st.write("---")
    
    col_a, col_b = st.columns(2)
    
    # OPTION A: START FRESH
    with col_a:
        if st.button("🆕 Start New Production", type="secondary", use_container_width=True):
            if os.path.exists(output_path):
                st.warning("This will overwrite your existing script!")
            
            if "architect" in st.session_state: del st.session_state.architect
            st.session_state.node_id = "intro"
            st.session_state.engine_ready = True
            st.rerun()

    # OPTION B: RESUME
    with col_b:
        if os.path.exists(ink_file):
            if st.button("⏯️ Resume Existing Session", type="primary", use_container_width=True):
                with st.status("Loading Session State...") as s:
                    # 1. Boot Engine
                    st.session_state.architect = AutonomousArchitect(os.path.join(BOOKS_DIR, current_book_filename))
                    st.session_state.weaver = VisualWeaver()
                    st.session_state.smith = InkSmith(active_book_id)
                    
                    # 2. Extract context from Ink file for the AI
                    with open(ink_file, "r") as f:
                        full_script = f.read()
                    
                    # Find the last node ID
                    nodes = re.findall(r"== (node_\d+) ==", full_script)
                    last_node = nodes[-1] if nodes else "intro"
                    
                    # Catch the AI up
                    s.write("🧠 Synchronizing AI with script history...")
                    st.session_state.architect.resume_session(full_script[-2000:]) # Last 2000 chars
                    
                    st.session_state.node_id = last_node
                    st.session_state.engine_ready = True
                    st.rerun()
        else:
            st.button("Resume Production", disabled=True, use_container_width=True)

# --- 5. PRODUCTION LOOP ---
if st.session_state.engine_ready:
    # 1. Safety check for core objects
    if "smith" not in st.session_state:
        # Re-derive active_book_id if it's lost
        current_conf = load_config()
        bid = current_conf.get("book_id", "default")
        st.session_state.smith = InkSmith(bid)
    
    if "architect" not in st.session_state:
        with st.spinner("⏳ Reconnecting with the AI Director..."):
            try:
                # We use the current book and model settings to reboot
                st.session_state.architect = AutonomousArchitect(os.path.join(BOOKS_DIR, current_book_filename))
                st.session_state.weaver = VisualWeaver()
                st.session_state.smith = InkSmith(active_book_id)
                st.toast("✅ Connection Restored Automatically!")
            except Exception as e:
                st.error(f"Could not reconnect: {e}")
                st.session_state.engine_ready = False
                st.stop()

    architect = st.session_state.architect
    smith = st.session_state.smith
    weaver = st.session_state.weaver
    
    if "current_step" not in st.session_state:
        st.session_state.current_step = "narrative"
        if "node_id" not in st.session_state: st.session_state.node_id = "intro"
        st.session_state.chapter_start = "intro"
        st.session_state.scene_data = None
        st.session_state.generated_images = []

    # [SCENE HISTORY LOG]
    with st.expander("🎞️ Production Log", expanded=False):
        if os.path.exists(ink_file):
            st.text(full_script[-1000:] if 'full_script' in locals() else "Script loading...")

    # STEP 1: NARRATIVE (The Director's Script)
    if st.session_state.current_step == "narrative":
        st.subheader(f"📖 Scripting: {st.session_state.node_id}")
        
        # 1. AUTO-DRAFT: Get AI content if we don't have it
        if st.session_state.scene_data is None:
            with st.spinner("🕵️ Architect is drafting..."):
                if st.session_state.node_id == "intro":
                    data = architect.initialize_engine()
                    if 'next_node_id' not in data: data['next_node_id'] = "chapter1_start"
                else:
                    data = architect.generate_main_beat(st.session_state.node_id)
                st.session_state.scene_data = data
                st.rerun()
        
        # 2. EDITING FORM: Active fields for Prose, Prompts, and Choices
        else:
            scene = st.session_state.scene_data
            
            with st.form(key=f"script_form_{st.session_state.node_id}"):
                c_edit, c_choice = st.columns([2, 1])
                
                with c_edit:
                    st.write("📝 **Prose & Visuals**")
                    edited_prose = st.text_area("Narrative Text", value=scene.get('scene_text', ''), height=300)
                    edited_prompt = st.text_area("Art Prompt", value=scene.get('visual_prompt', ''), height=100)
                
                with c_choice:
                    st.write("🔗 **Branching Choices**")
                    edited_choices = []
                    raw_choices = scene.get('choices', [])
                    
                    for i, ch in enumerate(raw_choices):
                        ctype = ch.get('type', 'golden')
                        tag = "💎 [EXQ]" if ctype == 'exquisite' else "🔸 [GLD]"
                        # Editable choice text
                        ch_text = st.text_input(f"{tag} Choice {i+1}", value=ch.get('text', ''), key=f"ch_{i}")
                        edited_choices.append({'text': ch_text, 'type': ctype})
                
                st.markdown("---")
                # Confirming overwrites the data in memory
                if st.form_submit_button("🎨 Confirm & Weave Art", type="primary", use_container_width=True):
                    st.session_state.scene_data['scene_text'] = edited_prose
                    st.session_state.scene_data['visual_prompt'] = edited_prompt
                    st.session_state.scene_data['choices'] = edited_choices
                    
                    st.session_state.current_step = "art"
                    st.session_state.generated_images = [] # Clear images to trigger auto-weave
                    st.rerun()

    # STEP 2: ART (Visualizing & Writing to Ink)
    elif st.session_state.current_step == "art":
        st.subheader(f"🎨 Visualizing: {st.session_state.node_id}")
        
        # We use the potentially EDITED prompt here
        active_prompt = st.session_state.scene_data.get('visual_prompt')
        
        if not st.session_state.generated_images:
            with st.spinner("🖌️ Weaver is painting..."):
                base_name = f"{st.session_state.node_id}_{int(time.time())}"
                st.session_state.generated_images = weaver.generate_batch(active_prompt, base_name)
                st.session_state.base_name_art = base_name
                st.rerun()
        
        else:
            cols = st.columns(4)
            for i, img_path in enumerate(st.session_state.generated_images):
                with cols[i]:
                    st.image(img_path)
                    if st.button(f"Select #{i+1}", key=f"img_{i}"):
                        scene = st.session_state.scene_data
                        base_id = scene.get('scene_id', f"node_{int(time.time())}")
                        
                        # 1. Save Main Image
                        main_img_name = f"{base_id}_main"
                        shutil.move(img_path, os.path.join(weaver.output_dir, f"{main_img_name}.png"))
                        
                        # 2. Determine Navigation
                        curr_id = st.session_state.node_id
                        next_node_id = f"{base_id}_start" 

                        # 3. Process Rewards (Auto-Weave)
                        with st.status("Building outcomes...") as s:
                            for j, c in enumerate(scene.get('choices', [])):
                                if c.get('type') == 'exquisite':
                                    reward_slug = f"{base_id}_c{j}"
                                    r_paths = weaver.generate_batch(scene.get('visual_prompt'), reward_slug, count=1)
                                    if r_paths:
                                        shutil.move(r_paths[0], os.path.join(weaver.output_dir, f"{reward_slug}_reward.png"))

                        # 4. Write to Ink
                        if curr_id == "intro":
                            smith.write_intro(scene, next_node_id)
                        else:
                            smith.write_main_node_start(base_id, scene['scene_text'], main_img_name)
                        
                        # This creates the outcome/result nodes
                        smith.write_choice_outcomes(base_id, scene['choices'], next_node_id)

                        # 5. Advance State
                        st.session_state.node_id = next_node_id
                        st.session_state.current_step = "narrative"
                        st.session_state.scene_data = None
                        st.rerun()