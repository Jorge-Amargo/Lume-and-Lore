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
        if "last_book_sel" not in st.session_state or st.session_state.last_book_sel != current_book_filename:
            # Strip .txt and replace underscores with spaces
            new_title = os.path.splitext(current_book_filename)[0].replace('_', ' ')
            st.session_state["c_title"] = new_title
            st.session_state["last_book_sel"] = current_book_filename

        active_book_id = "".join(x for x in os.path.splitext(current_book_filename)[0] if x.isalnum() or x in "_-")

with tab_conf:
    current_config = load_config()
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
# ==========================================
# 🎬 MAIN INTERFACE & LOGIC
# ==========================================

# 1. Output Paths
output_path = os.path.join(current_dir, "..", "data", "output", active_book_id)
os.makedirs(output_path, exist_ok=True)
ink_file = os.path.join(output_path, "adventure.ink")

# 2. Resume Helper
def get_resume_state(file_path):
    """Return the last known node.
    Prefer the runtime assignment (~ last_node = "...") when present; otherwise fall back
    to the file-level VAR declaration (VAR last_node = "...").
    """
    if not os.path.exists(file_path): return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Prefer runtime assignment if it exists
        runtime = re.findall(r'~\s*last_node\s*=\s*"(.*?)"', content)
        if runtime:
            return runtime[-1]
        # Fallback to VAR declaration in header
        var_match = re.findall(r'VAR\s+last_node\s*=\s*"(.*?)"', content)
        return var_match[-1] if var_match else None
    except:
        return None

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
        # Unique Key: btn_new_project
        if st.button("🚀 Start Scripting", type="primary", use_container_width=True, key="btn_new_project"):
            if not current_book_filename:
                st.error("⚠️ Please select a book in the Library tab first!")
            else:
                st.session_state.node_id = "intro"
                st.session_state.scene_data = None
                st.session_state.generated_images = []
                st.session_state.picking_reward = False
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
                st.session_state.node_id = f"{last_node}_next"
                st.session_state.scene_data = None
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
    # 🛑 STOP BUTTON (Sidebar)
    with st.sidebar:
        st.divider()
        st.markdown("### 🛑 Session Control")
        if not st.session_state.get('confirm_stop', False):
            if st.button("⏹️ Stop & Save Session", type="secondary", use_container_width=True, key="btn_stop_init"):
                st.session_state.confirm_stop = True
                st.rerun()
        else:
            st.warning("⚠️ Progress on the current scene will be lost!")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Confirm Stop", type="danger", key="btn_stop_final"):
                    st.session_state.engine_ready = False
                    st.session_state.scene_data = None
                    st.session_state.confirm_stop = False
                    st.rerun()
            with col_no:
                if st.button("Cancel", key="btn_stop_cancel"):
                    st.session_state.confirm_stop = False
                    st.rerun()

    # --- WORKER CONNECTION ---
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
    if st.session_state.get('confirm_stop') or not st.session_state.engine_ready:
            st.stop()
    architect = st.session_state.architect
    weaver = st.session_state.weaver
    smith = st.session_state.smith

    # --- STEP 1: NARRATIVE DRAFTING ---
    if st.session_state.current_step == "narrative":
        st.subheader(f"📖 Scripting: {st.session_state.node_id}")
        
        # 1. GENERATE (If Empty)
        if st.session_state.scene_data is None:
            with st.spinner("🕵️ Architect is drafting..."):
                if st.session_state.node_id == "intro":
                    data = architect.initialize_engine()
                else:
                    data = architect.generate_main_beat(st.session_state.node_id)
                
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
                            height=80, 
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
                st.session_state.scene_data['choices'] = updated_choices
                st.session_state.current_step = "art"
                st.rerun()
    # --- STEP 2: ART SELECTION ---
    elif st.session_state.current_step == "art":
        scene = st.session_state.scene_data
        is_reward_phase = st.session_state.get('picking_reward', False)
        
        # 1. Determine Header & Prompt
        if is_reward_phase:
            st.subheader(f"💎 Reward Art: {st.session_state.node_id}")
            # Get the exquisite choice specifically
            ex_choice = next((c for c in scene['choices'] if c['type'] == 'exquisite'), None)
            
            # 🛠️ FIX: Use the specific reward prompt we edited in Step 1
            raw_prompt = ex_choice.get('reward_visual_prompt', scene.get('visual_prompt'))
            
            # Add stylistic modifiers for rewards
            final_prompt = f"{raw_prompt}, masterpiece, highly detailed, magical lighting, centered composition"
            slug = f"{scene.get('scene_id')}_reward"
        else:
            st.subheader(f"🎨 Scene Art: {st.session_state.node_id}")
            final_prompt = scene.get('visual_prompt')
            slug = scene.get('scene_id')

        # 2. Display Prompt for Comparison
        st.info(f"**Visual Prompt:** {final_prompt}")

        # 3. Generate Images (if empty)
        if not st.session_state.generated_images:
            with st.spinner("🎨 Painting batch..."):
                st.session_state.generated_images = weaver.generate_batch(final_prompt, slug)
                st.rerun()

        # 4. Display Grid & Select
        cols = st.columns(4)
        for i, img_path in enumerate(st.session_state.generated_images):
            with cols[i]:
                st.image(img_path)
                if st.button(f"Select #{i+1}", key=f"sel_{i}"):
                    base_id = scene.get('scene_id')
                    
                    if not is_reward_phase:
                        # === PHASE 1: SAVE MAIN SCENE ===
                        shutil.move(img_path, os.path.join(weaver.output_dir, f"{base_id}_main.png"))
                        
                        # Clean up unused images
                        for temp in st.session_state.generated_images:
                            if temp != img_path and os.path.exists(temp): os.remove(temp)
                        
                        # Check if we need to go to Reward Phase
                        ex_idx = next((idx for idx, c in enumerate(scene['choices']) if c['type'] == 'exquisite'), None)
                        if ex_idx is not None:
                            st.session_state.picking_reward = True
                            st.session_state.ex_choice_idx = ex_idx
                            st.session_state.generated_images = [] # Clear batch for next pass
                            st.rerun()
                        else:
                            finalize_ink_node(base_id, scene)
                    else:
                        # === PHASE 2: REWARD ===
                        idx = st.session_state.ex_choice_idx
                        # Move chosen reward to the canonical scene-level reward filename
                        target = os.path.join(weaver.output_dir, f"{base_id}_reward.png")
                        shutil.move(img_path, target)
                        
                        # 🛠️ FIX: Cleanup Unused Reward Images
                        for temp in st.session_state.generated_images:
                            if temp != img_path and os.path.exists(temp): 
                                try:
                                    os.remove(temp)
                                except: pass # Safely ignore file lock errors
                        
                        finalize_ink_node(base_id, scene)

# --- HELPER FUNCTION (Place at very bottom or top) ---
def finalize_ink_node(base_id, scene):
    curr_id = st.session_state.node_id
    next_node_id = f"{base_id}_next"
    
    if curr_id == "intro":
        st.session_state.smith.write_intro(scene, next_node_id)
    else:
        st.session_state.smith.write_main_node_start(base_id, scene['scene_text'], f"{base_id}_main", scene['choices'], next_node_id)
    
    st.session_state.smith.write_choice_outcomes(base_id, scene['choices'], next_node_id)
    
    st.session_state.node_id = next_node_id
    st.session_state.current_step = "narrative"
    st.session_state.scene_data = None
    st.session_state.generated_images = []
    st.session_state.picking_reward = False
    st.rerun()
                        