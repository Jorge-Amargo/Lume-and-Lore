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

BOOKS_DIR = os.path.join(current_dir, "..", "data", "books")
CONFIG_PATH = os.path.join(current_dir, "..", "book_config.json")
DB_NAME = "gutenberg_index.db"

# --- 2. HELPER FUNCTIONS ---
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    # Default Config
    return {
        "book_id": "default",
        "title": "New Project",
        "llm_model": "gemini-2.0-flash-exp",
        "sd_settings": {"steps": 30, "cfg_scale": 7, "sampler_name": "Euler a"},
        "visual_settings": {"master_style": "Oil painting", "positive_prompt": "", "negative_prompt": ""}
    }

def save_config(new_config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(new_config, f, indent=4)

def check_forge_connection(api_url):
    try:
        requests.get(f"{api_url}/sdapi/v1/options", timeout=2)
        return True
    except:
        return False

# --- 3. ROBUST GUTENBERG HELPERS (Native SQL) ---
def search_gutenberg_native(query, search_type="title"):
    """
    Searches the local sqlite DB directly, bypassing gutenbergpy's complex schema requirements.
    """
    if not os.path.exists(DB_NAME):
        st.error("⚠️ Database not found! Please run 'build_library_index.py' first.")
        return []

    results = []
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Use simple pattern matching
        sql_query = f"%{query}%"
        
        if search_type == "title":
            # Join titles with authors to show nice labels
            c.execute("""
                SELECT t.book_id, t.name, a.name 
                FROM titles t
                LEFT JOIN authors a ON t.book_id = a.book_id
                WHERE t.name LIKE ? LIMIT 500
            """, (sql_query,))
        else:
            c.execute("""
                SELECT a.book_id, t.name, a.name 
                FROM authors a
                LEFT JOIN titles t ON a.book_id = t.book_id
                WHERE a.name LIKE ? LIMIT 500
            """, (sql_query,))
            
        rows = c.fetchall()
        conn.close()
        
        # Format results: "ID: Title - Author"
        # We store the ID but display the full string
        formatted = []
        for r in rows:
            bid, tit, aut = r
            label = f"[{bid}] {tit} - {aut}"
            formatted.append(label)
            
        return formatted

    except Exception as e:
        st.error(f"Search Error: {e}")
        return []

def download_book_robust(book_selection):
    """
    Downloads book text directly from Gutenberg mirrors.
    Selection format: "[1234] Title - Author"
    """
    try:
        # Extract ID from string "[1234] Title..."
        book_id = book_selection.split(']')[0].strip('[')
        
        # Try generic mirror URLs
        urls = [
            f"https://www.gutenberg.org/files/{book_id}/{book_id}-0.txt", # UTF-8
            f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt", # Cache
            f"https://www.gutenberg.org/files/{book_id}/{book_id}.txt"    # ASCII
        ]
        
        content = None
        for url in urls:
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    content = r.text
                    break
            except:
                continue
        
        if not content:
            st.error(f"Could not download Book ID {book_id} from standard mirrors.")
            return None

        # Strip Headers (Simple Logic)
        # Look for "*** START OF" and "*** END OF"
        start_markers = ["*** START OF", "***START OF"]
        end_markers = ["*** END OF", "***END OF"]
        
        start_idx = 0
        end_idx = len(content)
        
        for m in start_markers:
            if m in content:
                # Find the end of the line containing the marker
                start_idx = content.index(m)
                start_idx = content.find('\n', start_idx) + 1
                break
                
        for m in end_markers:
            if m in content:
                end_idx = content.index(m)
                break
                
        clean_text = content[start_idx:end_idx].strip()
        
        # Save
        clean_title = re.sub(r'[^a-zA-Z0-9]', '_', book_selection.split(']')[1].strip())[:50]
        filename = f"{clean_title}.txt"
        
        save_path = os.path.join(BOOKS_DIR, filename)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(clean_text)
            
        return filename

    except Exception as e:
        st.error(f"Download Error: {e}")
        return None

# --- 4. SIDEBAR ---
st.sidebar.title("⚙️ Engine Settings")
tab_lib, tab_conf = st.sidebar.tabs(["📚 Library", "🔧 Config"])

with tab_lib:
    st.markdown("### 🌍 Project Gutenberg")
    
    # SEARCH
    search_mode = st.radio("Search by:", ["Title", "Author"], horizontal=True)
    search_query = st.text_input("Search term", placeholder="e.g. Time Machine")
    
    if st.button("🔍 Search Library"):
        if search_query:
            results = search_gutenberg_native(search_query, search_mode.lower())
            st.session_state.search_results = results
            
    # DOWNLOAD
    if "search_results" in st.session_state and st.session_state.search_results:
        st.write(f"Found {len(st.session_state.search_results)} matches:")
        selected_book_str = st.selectbox("Select Book", st.session_state.search_results)
        
        if st.button("⬇️ Download & Import"):
            with st.spinner("Downloading..."):
                fname = download_book_robust(selected_book_str)
                if fname:
                    st.success(f"Saved: {fname}")
                    time.sleep(1)
                    st.rerun()

    st.markdown("---")
    st.markdown("### 📂 Local Library")
    os.makedirs(BOOKS_DIR, exist_ok=True)
    available_books = [f for f in os.listdir(BOOKS_DIR) if f.endswith(".txt")]
    selected_book_file = st.selectbox("Active Source Text", available_books)

# --- 5. CONFIG TAB ---
with tab_conf:
    current_config = load_config()
    st.markdown("#### 📝 Project Metadata")
    title = st.text_input("Project Title", value=current_config.get("title", "New Adventure"))
    
    st.markdown("#### 🧠 AI Brain")
    llm_options = ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"]
    def_llm = current_config.get("llm_model", "gemini-2.0-flash-exp")
    if def_llm not in llm_options: llm_options.append(def_llm)
    llm_model = st.selectbox("LLM Model", llm_options, index=llm_options.index(def_llm))

    st.markdown("#### 🎨 Visual Style")
    vis_conf = current_config.get("visual_settings", {})
    master_style = st.text_area("Master Style Prompt", value=vis_conf.get("master_style", ""))
    pos_prompt = st.text_area("Universal Positive", value=vis_conf.get("positive_prompt", ""))
    neg_prompt = st.text_area("Universal Negative", value=vis_conf.get("negative_prompt", ""))

    with st.expander("⚙️ Stable Diffusion Advanced"):
        sd_conf = current_config.get("sd_settings", {})
        
        # Model Selector
        st.markdown("**Model Checkpoint**")
        col_m1, col_m2 = st.columns([3, 1])
        current_model = sd_conf.get("sd_model", "juggernautXL_v9.safetensors")
        
        with col_m2:
            if st.button("🔄 Fetch"):
                try:
                    resp = requests.get("http://127.0.0.1:7860/sdapi/v1/sd-models", timeout=2)
                    if resp.status_code == 200:
                        st.session_state.avail_models = [m['title'] for m in resp.json()]
                        st.toast(f"Found {len(st.session_state.avail_models)} models!")
                except: st.error("Forge Offline")

        if "avail_models" in st.session_state:
            idx = 0
            if current_model in st.session_state.avail_models:
                idx = st.session_state.avail_models.index(current_model)
            sd_model_val = st.selectbox("Select Model", st.session_state.avail_models, index=idx)
        else:
            with col_m1:
                sd_model_val = st.text_input("Model Filename", value=current_model)

        steps = st.slider("Steps", 10, 100, sd_conf.get("steps", 30))
        cfg_scale = st.slider("CFG", 1.0, 20.0, float(sd_conf.get("cfg_scale", 7.0)))
        sampler = st.text_input("Sampler", value=sd_conf.get("sampler_name", "Euler a"))

    if st.button("💾 Save Settings", type="primary"):
        new_conf = {
            "title": title, "llm_model": llm_model,
            "visual_settings": {"master_style": master_style, "positive_prompt": pos_prompt, "negative_prompt": neg_prompt},
            "sd_settings": {"sd_model": sd_model_val, "steps": steps, "sampler_name": sampler, "cfg_scale": cfg_scale},
            "book_id": current_config.get("book_id", "default")
        }
        save_config(new_conf)
        st.toast("Saved!")

# --- 6. MAIN INTERFACE ---
st.title(f"🎬 Director Mode: {title}")

if "engine_ready" not in st.session_state:
    st.session_state.engine_ready = False
    st.session_state.scene_data = None
    st.session_state.generated_images = []

if not st.session_state.engine_ready:
    st.info(f"Target: **{selected_book_file}**")
    if st.button("🚀 Initialize Engine"):
        with st.status("Booting...", expanded=True) as status:
            try:
                if not selected_book_file: st.stop()
                
                # Auto ID
                derived_id = "".join(x for x in os.path.splitext(selected_book_file)[0] if x.isalnum() or x in "_-")
                active_config = load_config()
                active_config["book_id"] = derived_id
                save_config(active_config)
                
                status.write("🧠 Loading Architect...")
                st.session_state.architect = AutonomousArchitect(os.path.join(BOOKS_DIR, selected_book_file))
                
                status.write("🎨 Loading Weaver...")
                st.session_state.weaver = VisualWeaver()
                if not check_forge_connection(st.session_state.weaver.base_url):
                    st.error("Forge not running (checking at http://127.0.0.1:7860)")
                    st.stop()
                    
                status.write("🔨 Loading Smith...")
                st.session_state.smith = InkSmith(derived_id)
                
                st.session_state.engine_ready = True
                status.update(label="Online", state="complete")
                st.rerun()
            except Exception as e: st.error(f"Init Failed: {e}")

# --- PRODUCTION LOOP ---
if st.session_state.engine_ready:
    smith = st.session_state.smith
    architect = st.session_state.architect
    weaver = st.session_state.weaver
    
    if "current_step" not in st.session_state:
        st.session_state.current_step = "narrative" 
        st.session_state.node_id = "intro"          
        st.session_state.chapter_start = "intro"    

    # STEP 1: NARRATIVE
    if st.session_state.current_step == "narrative":
        st.subheader(f"📖 Writing: {st.session_state.node_id}")
        
        if st.session_state.scene_data is None:
            if st.button("✍️ Draft Scene"):
                with st.spinner("Writing..."):
                    try:
                        if st.session_state.node_id == "intro":
                            data = architect.initialize_engine()
                            data['next_node_id'] = "chapter1_start"
                        else:
                            data = architect.generate_main_beat(st.session_state.node_id)
                        st.session_state.scene_data = data
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
        else:
            st.info("Review Draft:")
            edited_text = st.text_area("Narrative", value=st.session_state.scene_data.get('scene_text'), height=200)
            edited_prompt = st.text_area("Visual Prompt", value=st.session_state.scene_data.get('visual_prompt'), height=100)
            
            choices = st.session_state.scene_data.get('choices', [])
            if choices:
                with st.expander("Choices"):
                    for c in choices: st.markdown(f"**[{c.get('type','golden')}]** {c.get('text')}")

            c1, c2 = st.columns([1,4])
            with c1: 
                if st.button("♻️ Retry"): 
                    st.session_state.scene_data = None; st.rerun()
            with c2: 
                if st.button("✅ Confirm"):
                    st.session_state.scene_data['scene_text'] = edited_text
                    st.session_state.scene_data['visual_prompt'] = edited_prompt
                    st.session_state.current_step = "art"
                    st.rerun()

    # STEP 2: ART
    elif st.session_state.current_step == "art":
        st.subheader(f"🎨 Art: {st.session_state.node_id}")
        scene = st.session_state.scene_data
        
        if not st.session_state.generated_images:
            if st.button("🎨 Generate"):
                with st.spinner("Rendering..."):
                    base = f"{st.session_state.node_id}_{int(time.time())}"
                    paths = weaver.generate_batch(scene.get('visual_prompt'), base)
                    st.session_state.generated_images = paths
                    st.session_state.base_name_art = base
                    st.rerun()
        else:
            st.write("Select Image:")
            cols = st.columns(4)
            for i, p in enumerate(st.session_state.generated_images):
                with cols[i]:
                    st.image(p)
                    if st.button(f"Select #{i+1}", key=f"b{i}", use_container_width=True):
                        # Finalize
                        fname = f"{st.session_state.base_name_art}_final"
                        shutil.move(p, os.path.join(weaver.output_dir, f"{fname}.png"))
                        
                        # Write Logic
                        curr = st.session_state.node_id
                        if "start" in curr or "intro" in curr: st.session_state.chapter_start = curr
                        
                        if curr == "intro":
                            nxt = scene.get('next_node_id', 'chapter1_start')
                            smith.write_intro(scene, nxt)
                            st.session_state.next_node_buffer = nxt
                        else:
                            smith.write_main_node_start(scene, fname)
                            # Side Branches
                            choices = scene.get('choices', [])
                            gold_next = None
                            rew_id = None
                            
                            with st.status("Building paths...") as s:
                                for c in choices:
                                    ct = c.get('type', 'golden')
                                    if ct == 'exquisite':
                                        s.write("💎 Building Side Quest...")
                                        try:
                                            out = architect.generate_transition(curr, c)
                                            # Weave reward art
                                            rbase = f"{curr}_REW"
                                            rpaths = weaver.generate_batch(out['visual_prompt'], rbase, count=1)
                                            if rpaths:
                                                rfin = f"{rbase}_final"
                                                shutil.move(rpaths[0], os.path.join(weaver.output_dir, f"{rfin}.png"))
                                                rew_id = smith.write_reward_node(out, rfin, curr)
                                                architect.reset_to_main_path(curr)
                                        except Exception as e: st.error(str(e))
                                    elif ct == 'golden':
                                        gold_next = f"node_{int(time.time())}"

                            smith.write_choices(curr, choices, rew_id, st.session_state.chapter_start)
                            if gold_next:
                                smith.finalize_links(gold_next)
                                st.session_state.next_node_buffer = gold_next
                            else:
                                st.session_state.next_node_buffer = None

                        st.success("Saved!")
                        st.session_state.generated_images = []
                        st.session_state.scene_data = None
                        if st.session_state.next_node_buffer:
                            st.session_state.node_id = st.session_state.next_node_buffer
                            st.session_state.current_step = "narrative"
                            st.rerun()
                        else:
                            st.balloons()

            if st.button("Discard"): st.session_state.generated_images = []; st.rerun()