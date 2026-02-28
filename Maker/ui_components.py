import os
import streamlit as st
from utils import DashboardUtils
from sound_weaver import SoundWeaver
import shutil

def render_character_selection():
    # FIX: Check if selection has already happened to avoid unnecessary re-renders
    if st.session_state.engine_ready:
        if st.session_state.get("selected_protagonist") is not None:
            return st.session_state.selected_protagonist

        if st.session_state.book_pitch is None:
            with st.spinner("📜 Analyzing book and meeting characters..."):
                st.session_state.book_pitch = st.session_state.architect.generate_book_pitch()
        
        pitch = st.session_state.book_pitch
        st.markdown(f"### 📖 Story Briefing\n{pitch.get('summary', '')}")
        st.markdown("---")
        st.subheader("Who will you be?")
        
        char_list = pitch.get('characters', [])
        cols = st.columns(len(char_list))
        for idx, char in enumerate(char_list):
            with cols[idx]:
                st.write(f"**{char['name']}**")
                st.caption(char['description'])
                if st.button(f"Choose {char['name']}", key=f"sel_{idx}", use_container_width=True):
                    return char
        st.stop()
    return None

def render_scene_editor(scene, current_config):
    """
    Renders the UI for editing story text, choices, and traits.
    Returns a tuple: (updated_text, updated_visual_prompt, updated_audio_prompt, updated_choices)
    """
    col_text, col_vis = st.columns([2, 1])
    
    with col_text:
        txt = st.text_area("📖 Story Text", value=scene.get('scene_text', ''), height=250)
    
    with col_vis:
        vp = st.text_area("🎨 Scene Visual Prompt", value=scene.get('visual_prompt', ''), height=120)
        ap = st.text_area("🔊 Audio Prompt (for SFX)", value=scene.get('audio_prompt', ''), height=120)

    st.divider()

    updated_choices = []
    for i, c in enumerate(scene.get('choices', [])):
        icons = {"golden": "🌟", "exquisite": "💎", "bad": "💀"}
        c_type = c.get('type', 'golden')
        label_prefix = f"{icons.get(c_type, '➡️')} {c_type.upper()}"

        col_c, col_o = st.columns([1, 2])
        with col_c:
            c_txt = st.text_area(f"{label_prefix}: Choice", value=c.get('text', ''), height=75, key=f"c_txt_{i}")
        
        with col_o:
            c_out = st.text_area(f"{label_prefix}: Outcome", value=c.get('outcome_text', ''), height=75, key=f"c_out_{i}")
            
            # Trait Logic (Refactored for stability)
            active_traits = {k: v for k, v in current_config.get("traits", {}).items() if v.get('label')}
            current_trait_changes = c.get("trait_changes", {}).copy() if isinstance(c.get("trait_changes"), dict) else {}
            
            if active_traits:
                t_cols = st.columns(len(active_traits))
                for idx, (t_key, t_data) in enumerate(active_traits.items()):
                    with t_cols[idx]:
                        val = st.number_input(f"Δ {t_data['label']}", 
                                           value=current_trait_changes.get(t_key, 0), 
                                           key=f"delta_{t_key}_{i}")
                        current_trait_changes[t_key] = val
            c["trait_changes"] = current_trait_changes

        # Reward prompt for exquisite choices
        if c_type == 'exquisite':
            c['reward_visual_prompt'] = st.text_input("💎 REWARD PROMPT", value=c.get('reward_visual_prompt', vp), key=f"c_rew_{i}")

        c['text'] = c_txt
        c['outcome_text'] = c_out
        updated_choices.append(c)
        
    return txt, vp, ap, updated_choices

def render_sidebar_tabs(current_config, weaver, available_books):
    """Encapsulates all sidebar settings and library management."""
    tab_lib, tab_conf = st.sidebar.tabs(["📚 Library", "🔧 Config"])

    with tab_lib:
        st.markdown("### 🌍 Project Gutenberg")
        langs = {"English": "", "German": "German", "French": "French", "Spanish": "Spanish", "Portuguese": "Portuguese", "Dutch": "Dutch", "Latin": "Latin"}
        selected_lang = st.selectbox("Language", list(langs.keys()), key="lib_lang")
        lang_filter = langs[selected_lang]
        search_mode = st.radio("Search by:", ["Title", "Author"], horizontal=True, key="lib_mode")
        search_query = st.text_input("Search term", key="lib_query")
        if st.button("🔍 Search Library", key="lib_search"):
            st.session_state.search_results = DashboardUtils.search_gutenberg_native(
                search_query, 
                search_mode.lower(), 
                lang_filter
            )
        if "search_results" in st.session_state and st.session_state.search_results:
            st.divider()
            selected_book_str = st.selectbox("Select Result", st.session_state.search_results, key="lib_res")
            if st.button("⬇️ Download & Import", key="lib_dl", use_container_width=True):
                with st.spinner("Downloading..."):
                    fname = DashboardUtils.download_book_robust(selected_book_str)
                    if fname:
                        st.success(f"Imported: {fname}")
                        # Clear results after successful import
                        del st.session_state.search_results
                        st.rerun()

        st.markdown("---")
        st.markdown("### 📂 Local Library")
        if available_books:
            saved_id = current_config.get("book_id", "")
            def_idx = 0
            for i, f in enumerate(available_books):
                if saved_id in f: def_idx = i; break
            
            current_book_filename = st.selectbox("Active Source Text", available_books, index=def_idx, key="local_sel")
            
            if "last_book_sel" not in st.session_state or st.session_state.last_book_sel != current_book_filename:
                new_title = os.path.splitext(current_book_filename)[0].replace('_', ' ')
                st.session_state["c_title"] = new_title
                st.session_state["last_book_sel"] = current_book_filename
                current_config["title"] = new_title
                current_config["book_id"] = "".join(x for x in os.path.splitext(current_book_filename)[0] if x.isalnum() or x in "_-")
                current_config["book_filename"] = current_book_filename
                DashboardUtils.save_config(current_config)

    with tab_conf:
        st.markdown("### 🛠️ Generation Settings")
        gen_cfg = current_config.get('generation', {})
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("🎨 Visuals")
            img_count = st.slider("Images per Scene", 0, 8, gen_cfg.get('images_per_scene', 4))
            scene_count = st.slider("Scenes per Book", 0, 50, gen_cfg.get('target_scene_count', 12))
        with col_g2:
            st.subheader("🎧 Audio")
            snd_count = st.slider("Sounds per Scene", 0, 5, gen_cfg.get('sounds_per_scene', 1))
            snd_len = st.number_input("Sound Duration (sec)", 1, 30, gen_cfg.get('sound_length_seconds', 5))
            snd_loop = st.checkbox("Seamless Loop", value=gen_cfg.get('sound_loop', False))
            
        st.divider()
        title = st.text_input("Project Title", value=st.session_state.get("c_title", current_config.get("title", "New Adventure")), key="c_title_in")
        
        st.markdown("#### 🧠 AI Brain")
        available_llms = DashboardUtils.fetch_gemini_models()
        default_model = current_config.get("llm_model", "gemini-2.0-flash-exp")
        default_idx = available_llms.index(default_model) if default_model in available_llms else 0
        llm_model = st.selectbox("LLM Model", options=available_llms, index=default_idx)

        st.markdown("#### 🎨 Visual Style")
        vis = current_config.get("visual_settings", {})
        m_style = st.text_area("Master Style", value=vis.get("master_style", ""), key="c_style")
        p_prompt = st.text_area("Positive Prompt", value=vis.get("positive_prompt", ""), key="c_pos")
        n_prompt = st.text_area("Negative Prompt", value=vis.get("negative_prompt", ""), key="c_neg")

        st.markdown("🎭 Traits")
        traits_cfg = current_config.get("traits", {"trait_1": {"label": "", "initial": 50}, "trait_2": {"label": "", "initial": 50}, "trait_3": {"label": "", "initial": 50}})
        cols = st.columns(3)
        for i in range(1, 4):
            key = f"trait_{i}"
            with cols[i-1]:
                traits_cfg[key]["label"] = st.text_input(f"Trait {i}", value=traits_cfg[key]["label"], key=f"lab_{key}")
                traits_cfg[key]["initial"] = st.number_input(f"Init {i}", value=traits_cfg[key]["initial"], key=f"init_{key}")

        with st.expander("🖼️ Stable Diffusion Advanced"):
            sd = current_config.get("sd_settings", {})
            
            # Fetch and handle models
            available_models = weaver.get_sd_models() if weaver else []
            current_model_val = sd.get("sd_model", "")
            if available_models:
                if current_model_val and current_model_val not in available_models:
                    available_models.insert(0, current_model_val)
                idx = available_models.index(current_model_val) if current_model_val in available_models else 0
                sd_m = st.selectbox("SD Model", available_models, index=idx)
            else:
                sd_m = st.text_input("SD Model", value=current_model_val)
            
            c1, c2 = st.columns(2)
            with c1:
                width = st.number_input("Width", value=sd.get("width", 512))
                steps = st.number_input("Steps", value=sd.get("steps", 20))
                # RE-INTRODUCED: Sampler
                sampler = st.text_input("Sampler (Method)", value=sd.get("sampler_name", "Euler a"))
            with c2:
                height = st.number_input("Height", value=sd.get("height", 512))
                cfg = st.number_input("CFG Scale", value=sd.get("cfg_scale", 7.0))
                # RE-INTRODUCED: Scheduler
                scheduler = st.text_input("Scheduler (Type)", value=sd.get("scheduler", "normal"))

        st.markdown("#### 👥 Character Bible")
        if "temp_char_map" not in st.session_state:
            st.session_state.temp_char_map = current_config.get("character_map", {}).copy()
        
        c_name = st.text_input("Name", key="bible_name_in")
        c_desc = st.text_input("Visual Description", key="bible_desc_in")
        if st.button("➕ Add Character"):
            if c_name and c_desc:
                st.session_state.temp_char_map[c_name] = c_desc
                st.rerun()

        for name, desc in list(st.session_state.temp_char_map.items()):
            col1, col2 = st.columns([4, 1])
            col1.text(f"{name}: {desc}")
            if col2.button("🗑️", key=f"del_{name}"):
                del st.session_state.temp_char_map[name]
                st.rerun()

        if st.button("💾 Save All Settings", type="primary", use_container_width=True):
            current_config.update({
                "title": title, 
                "llm_model": llm_model, 
                "traits": traits_cfg,
                "character_map": st.session_state.temp_char_map,
                "generation": {
                    "target_scene_count": scene_count, 
                    "images_per_scene": img_count, 
                    "sounds_per_scene": snd_count, 
                    "sound_length_seconds": snd_len, 
                    "sound_loop": snd_loop
                },
                "visual_settings": {
                    "master_style": m_style, 
                    "positive_prompt": p_prompt, 
                    "negative_prompt": n_prompt
                },
                "sd_settings": {
                    "sd_model": sd_m, 
                    "width": width, 
                    "height": height, 
                    "steps": steps, 
                    "cfg_scale": cfg,
                    "sampler_name": sampler,   # Ensure saved to config
                    "scheduler": scheduler      # Ensure saved to config
                }
            })
            DashboardUtils.save_config(current_config)
            st.success("✅ Configuration Saved!")
            st.rerun()

        st.divider()
        if st.button("⚙️ Compile .ink to .json", use_container_width=True):
            success, msg = DashboardUtils.compile_ink_to_json(current_config.get("book_id"))
            if success: st.success(f"✅ {msg}")
            else: st.error(f"⚠️ {msg}")

def render_art_selection(scene, current_config, weaver, current_dir):
    """Handles the UI and file logic for selecting Scene Art, Reward Art, and Audio."""
    base_id = scene.get('scene_id', 'unknown')
    audio_dir = os.path.join(current_dir, "..", "data", "output", current_config['book_id'], "audio")
    final_main_img = os.path.join(weaver.output_dir, f"{base_id}_main.png")
    final_sound = os.path.join(audio_dir, f"{base_id}.mp3")
    
    # --- PHASE 1: SCENE IMAGES ---
    img_count = current_config.get('generation', {}).get('images_per_scene', 4)
    if img_count > 0 and not os.path.exists(final_main_img):
        st.subheader(f"🎨 Scene Art: {base_id}")
        gen_key = f"gen_main_{base_id}"
        
        if gen_key not in st.session_state:
            is_online, err_msg = weaver.check_connection()
            if not is_online:
                st.warning(f"⚠️ Stable Diffusion Offline: {err_msg}")
                if st.button("🔄 Retry Connection"): st.rerun()
                st.stop()

            with st.spinner("💎 Painting Scene..."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                def update_ui(p, c, t):
                    progress_bar.progress(p)
                    status_text.text(f"🎨 Image {c}/{t} ({p}%)")
                
                paths = weaver.generate_batch(prompt=scene['visual_prompt'], count=img_count, base_filename=base_id, callback=update_ui)
                st.session_state[gen_key] = paths
                st.rerun()
        
        candidates = st.session_state.get(gen_key, [])
        if candidates:
            cols = st.columns(len(candidates))
            for idx, img_path in enumerate(candidates):
                with cols[idx]:
                    st.image(img_path)
                    if st.button("Select", key=f"sel_main_{idx}"):
                        shutil.move(img_path, final_main_img)
                        for c in candidates: 
                            if os.path.exists(c) and c != final_main_img: os.remove(c)
                        st.session_state.pop(gen_key, None)
                        st.rerun()
        st.stop()

    # --- PHASE 2: REWARD IMAGES ---
    exquisite_choice = next((c for c in scene['choices'] if c['type'] == 'exquisite'), None)
    if exquisite_choice:
        reward_target = os.path.join(weaver.output_dir, f"{base_id}_reward.png")
        if not os.path.exists(reward_target) and img_count > 0:
            st.subheader(f"💎 Reward Art: {base_id}_REW")
            gen_key_rew = f"gen_rew_{base_id}"
            
            if gen_key_rew not in st.session_state:
                with st.spinner("Painting Reward..."):
                    imgs = weaver.generate_batch(prompt=exquisite_choice.get('reward_visual_prompt'), count=img_count, base_filename=f"{base_id}_REW")
                    st.session_state[gen_key_rew] = imgs
                    st.rerun()

            candidates = st.session_state.get(gen_key_rew, [])
            if candidates:
                cols = st.columns(len(candidates))
                for idx, img_path in enumerate(candidates):
                    with cols[idx]:
                        st.image(img_path)
                        if st.button("Select", key=f"sel_rew_{idx}"):
                            shutil.move(img_path, reward_target)
                            for c in candidates:
                                if os.path.exists(c) and c != reward_target: os.remove(c)
                            st.session_state.pop(gen_key_rew, None)
                            st.rerun()
            st.stop()

    # --- PHASE 3: SOUND GENERATION ---
    snd_count = current_config.get('generation', {}).get('sounds_per_scene', 1)
    if snd_count > 0 and not os.path.exists(final_sound):
        st.subheader("🎧 Audio Atmosphere")
        snd_key = f"gen_snd_{base_id}"
        
        if snd_key not in st.session_state:
            sw = SoundWeaver()
            with st.spinner(f"🎧 Composing {snd_count} Audio Candidates..."):
                snds = sw.generate_candidates(
                    current_config['book_id'], base_id, 
                    scene.get('audio_prompt', scene['visual_prompt']), 
                    count=snd_count,
                    length_seconds=current_config['generation'].get('sound_length_seconds', 5),
                    loop=current_config['generation'].get('sound_loop', False)
                )
                st.session_state[snd_key] = snds
                st.rerun()

        sounds = st.session_state.get(snd_key, [])
        if sounds:
            for idx, s in enumerate(sounds):
                c1, c2 = st.columns([1, 4])
                with c1:
                    if st.button(f"Select #{idx+1}", key=f"sel_snd_{base_id}_{idx}"):
                        os.makedirs(audio_dir, exist_ok=True)
                        shutil.copy(os.path.join(current_dir, "..", s['file']), final_sound)
                        for cand in sounds:
                            try:
                                p = os.path.join(current_dir, "..", cand['file'])
                                if os.path.exists(p): os.remove(p)
                                if os.path.exists(p.replace(".mp3", ".json")): os.remove(p.replace(".mp3", ".json"))
                            except: pass
                        st.session_state.pop(snd_key, None)
                        st.session_state['sound_selected_map'] = {base_id: f"{base_id}.mp3"}
                        st.rerun()
                with c2:
                    st.audio(s['file'])
        st.stop()