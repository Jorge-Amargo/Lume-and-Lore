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
from utils import DashboardUtils
from session_manager import initialize_session_state, current_dir, BOOKS_DIR, CONFIG_PATH, DEFAULT_LLMS
from ui_components import render_character_selection, render_scene_editor, render_sidebar_tabs, render_art_selection

initialize_session_state()

# --- 1. SETUP & PATHS ---
st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; }
    .stTextArea textarea { font-size: 0.95rem !important; }
    div[data-testid="stExpander"] { margin-bottom: -0.5rem !important; }
    </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Lume & Lore Director", layout="wide", page_icon="🕯️")

os.makedirs(BOOKS_DIR, exist_ok=True)
available_books = [f for f in os.listdir(BOOKS_DIR) if f.endswith(".txt")]
current_config = DashboardUtils.load_config()

# Define the Weaver early so it's available for the sidebar
weaver = VisualWeaver()

# --- 3. RENDER SIDEBAR ---
st.sidebar.title("⚙️ Engine Settings")
# Prepare data for sidebar
available_books = [f for f in os.listdir(BOOKS_DIR) if f.endswith(".txt")]
current_config = DashboardUtils.load_config()
# Call the component to render the sidebar (REPLACES ~170 lines)
render_sidebar_tabs(current_config, weaver, available_books)

# --- 4. DERIVE ACTIVE PROJECT IDS ---
# We do this AFTER the sidebar, because the user might have changed the active book
active_book_id = current_config.get("book_id", "unknown_book")
active_book_filename = current_config.get("book_filename", f"{active_book_id}.txt")
book_path = os.path.join(BOOKS_DIR, active_book_filename)
title = current_config.get("title", "New Adventure")

# Initialize Smith with the (potentially new) active_book_id
smith = InkSmith(active_book_id)

if st.session_state.engine_ready and "architect" not in st.session_state:
    try:
        st.session_state.architect = AutonomousArchitect(os.path.join(BOOKS_DIR, current_book_filename))
        st.session_state.weaver = VisualWeaver()
        target_ink_path = os.path.join(weaver.output_dir, "adventure.ink")
        st.session_state.smith = InkSmith(current_config["book_id"])
    except: st.session_state.engine_ready = False

# --- 4. MAIN INTERFACE ---
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

            # Allow starting a new project immediately; cleanup happens automatically
            if st.button("🚀 Start New Adventure", type="primary", use_container_width=True, key="btn_new_project"):
                # Delete old files (user was warned above)
                deleted_count, success = DashboardUtils.cleanup_old_adventure_files(active_book_id, confirm_first=True)

                if success:
                    weaver = VisualWeaver()
                    print(f"ℹ️ VisualWeaver SD model on Start New Adventure: {getattr(weaver, 'sd_model', None)}")
                    st.session_state.weaver = weaver
                    target_ink_path = os.path.join(weaver.output_dir, "adventure.ink")
                    source_book_path = os.path.join(BOOKS_DIR, st.session_state.get("local_sel", current_config.get("book_filename")))
                    st.session_state.smith = InkSmith(current_config["book_id"])
                    st.session_state.architect = AutonomousArchitect(source_book_path)
                    existing_scenes = st.session_state.smith.count_existing_scenes()
                    st.session_state.architect.set_scene_number(existing_scenes)
                    content_to_send = st.session_state.smith.get_full_script()
                    response = st.session_state.architect.resume_session(content_to_send)
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
        # Nutzen der verbesserten Scan-Logik aus InkSmith
        temp_smith = InkSmith(current_config["book_id"])
        last_node = temp_smith.get_last_node()
        
        if last_node:
            st.success(f"Found Save: `{last_node}`")
            if st.button("📂 Resume Adventure", use_container_width=True, key="btn_resume_active"):
                weaver = VisualWeaver()
                st.session_state.weaver = weaver

                source_book_path = os.path.join(BOOKS_DIR, st.session_state.get("local_sel", current_config.get("book_filename")))
                active_filename = st.session_state.get("local_sel", current_config.get("book_filename"))
                
                if not active_filename:
                    st.error("Could not find source text filename. Please re-select it in the Library tab.")
                    st.stop()        
                try:
                    with st.spinner("🧠 Waking up the Architect (connecting to Google)..."):
                        # 1. Initialize Components
                        st.session_state.smith = InkSmith(current_config["book_id"])
                        st.session_state.architect = AutonomousArchitect(source_book_path)
                        
                        # 2. Sync Scene Counter
                        existing_count = st.session_state.smith.count_existing_scenes()
                        st.session_state.architect.current_scene_num = existing_count
                        print(f"🔄 Synced Architect to scene #{existing_count}")

                        # 3. Read the existing Ink file & Handshake
                        content_to_send = st.session_state.smith.get_full_script()
                        response = st.session_state.architect.resume_session(content_to_send)
                        
                        if response is None:
                            st.session_state.engine_ready = False # Reset state
                            st.error("Architect failed to synchronize. See terminal for details.")
                            st.stop() # Stoppt die Ausführung hier sofort
                        
                        # WICHTIG: Den Fortschritt im Session State verankern
                        actual_last = response.get('last_node', last_node)
                        st.session_state.node_id = f"{actual_last}_next"
                        st.success(f"Architect Online! Resuming after: {actual_last}")
                
                except Exception as e:
                    st.error(f"❌ CONNECTION FAILED: {str(e)}")
                    st.stop()

                # State aufräumen und Engine starten
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
        scene = st.session_state.get("scene_data")
        base_id = scene.get('scene_id') if scene else "unknown"
        weaver = st.session_state.weaver
        smith = st.session_state.get("smith") 
        # Final safety check: if smith is missing for some reason, stop
        if not smith:
            st.error("InkSmith initialization failed. Please restart the project.")
            st.stop()
        
        # Phase: Character Selection
        saved_char = DashboardUtils.get_protagonist_from_ink(current_config["book_id"])
        
        if not saved_char and not st.session_state.get("character_selected"):
            selected_char = render_character_selection()
            if selected_char:
                DashboardUtils.initialize_ink_file(current_config["book_id"], selected_char)
                st.session_state["character_selected"] = True
                # Ensure the component knows we are done
                st.session_state["selected_protagonist"] = selected_char 
                st.session_state.current_step = "narrative"
                if "node_id" not in st.session_state:
                    st.session_state.node_id = "intro"
                st.rerun()
            st.stop() 

        
    # --- MAIN PRODUCTION LOOP ---
    if st.session_state.current_step == "narrative":
        st.subheader(f"📖 Scripting: {st.session_state.node_id}")
        
        if st.session_state.scene_data is None:
            with st.spinner("🕵️ Architect is drafting..."):
                try:
                    if st.session_state.node_id == "intro":
                        # FIX: Pass the protagonist name to the engine
                        p_name = saved_char.get('name') if saved_char else None
                        data = architect.initialize_engine(protagonist_name=p_name)
                    else:
                        is_forced_end = st.session_state.get('force_next_ending', False)
                        data = architect.generate_main_beat(st.session_state.node_id, force_ending=is_forced_end)
                        if is_forced_end:
                            st.session_state.force_next_ending = False
                except Exception as e:
                    st.error(f"Architect exception: {e}")
                    st.stop()
                
                if data:
                    if 'scene_id' not in data: data['scene_id'] = f"node_{int(time.time())}"
                    st.session_state.scene_data = data
                    st.session_state.current_step = "edit"
                    st.rerun()

    # --- STEP 1: TEXT & CHOICE EDITING ---
    elif st.session_state.current_step == "edit":
        scene = st.session_state.scene_data
        st.subheader(f"📝 Review Scene: {scene.get('scene_id', 'Draft')}")
        
        # FIX: Ensure the submit button is INSIDE the form block
        with st.form("scene_editor_form"):
            txt, vp, ap, updated_choices = render_scene_editor(scene, current_config)
            submit_btn = st.form_submit_button("🎨 Confirm & Generate Art", type="primary", use_container_width=True)
            
        if submit_btn:
            st.session_state.scene_data['scene_text'] = txt
            st.session_state.scene_data['visual_prompt'] = vp
            st.session_state.scene_data['audio_prompt'] = ap
            st.session_state.scene_data['choices'] = updated_choices
            st.session_state.current_step = "art"
            st.rerun()

    # --- STEP 2: ART SELECTION ---
    elif st.session_state.current_step == "art":
        weaver = st.session_state.weaver
        
        # This replaces ~180 lines of candidate handling and file logic
        render_art_selection(scene, current_config, weaver, current_dir)

        
        # --- PHASE 4: FINALIZE (Only reached if all selections are done) ---
        st.success("✅ Scene Assets Complete!")
        
        # Show Progress
        curr = st.session_state.architect.current_scene_num
        targ = st.session_state.architect.target_scene_count
        st.caption(f"📖 Story Progress: Scene {curr} / {targ}")
        if st.session_state.get("adventure_finished"):
            st.info("🌟 Das Abenteuer ist abgeschlossen!")
            c_ex1, c_ex2 = st.columns(2)
            with c_ex1:
                if st.button("📦 Export .ink to .json", use_container_width=True):
                    success, msg = DashboardUtils.compile_ink_to_json(base_id)
                    if success: st.success(msg)
                    else: st.error(msg)
            with c_ex2:
                if st.button("🏠 Neustart (Library)", use_container_width=True):
                    for k in ['architect', 'current_scene', 'adventure_finished', 'scene_data']:
                        if k in st.session_state: del st.session_state[k]
                    st.rerun()
        else:
            c_fin_1, c_fin_2 = st.columns([1, 1])
            with c_fin_1:
                # Wenn Ziel erreicht, Button für das Finale zeigen
                label = "🌟 Finale generieren" if curr >= targ else "🎬 Speichern & Weiter"
                if st.button(label, type="primary" if curr >= targ else "secondary"):
                    if curr >= targ:
                        conclusion = st.session_state.architect.generate_conclusion(scene.get('scene_text', ''))
                        DashboardUtils.finalize_ink_node(base_id, conclusion)
                        st.session_state["adventure_finished"] = True
                    else:
                        DashboardUtils.finalize_ink_node(base_id, scene)
                    st.rerun()