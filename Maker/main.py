import os
import shutil
import json
import time
from dotenv import load_dotenv
from architect import AutonomousArchitect
from visual_weaver import VisualWeaver
from ink_smith import InkSmith
from sound_weaver import SoundWeaver

# Load environment variables from project .env if present
current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(current_dir, '..', '.env'))

def run_art_direction(weaver, prompt, base_name, config, sound_weaver=None, book_id=None, audio_prompt: str = None):
    """
    Generates assets but CHECKS if they exist first to prevent looping/overwriting.
    """
    image_name = base_name
    image_path = os.path.join(weaver.output_dir, f"{image_name}.png")
    
    # --- 1. IMAGE HANDLING ---
    candidates = []
    selected_image = None

    # Check if final image already exists
    if os.path.exists(image_path):
        print(f"✅ Image exists: {image_name}")
        selected_image = image_name
    else:
        # Check if we have existing candidates on disk (from a previous interrupted run)
        existing_cands = [
            os.path.join(weaver.output_dir, f) 
            for f in os.listdir(weaver.output_dir) 
            if f.startswith(base_name) and f.endswith(".png") and "final" not in f
        ]
        
        if existing_cands:
            candidates = sorted(existing_cands)
        else:
            # Only generate if absolutely nothing exists
            count = config.get('generation', {}).get('images_per_scene', 3)
            candidates = weaver.generate_batch(prompt, base_name, count=count)

        if not candidates:
            selected_image = f"{base_name}_fallback"
        else:
            # CLI Selection Loop
            print(f"\n--- Gallery for {base_name} ---")
            for i, c in enumerate(candidates):
                print(f"{i}: {os.path.basename(c)}")
            
            # Simple input loop to avoid crashes
            while True:
                pick = input(f"Select Image (0-{len(candidates)-1}) [0]: ").strip()
                if not pick: 
                    idx = 0
                    break
                if pick.isdigit() and 0 <= int(pick) < len(candidates):
                    idx = int(pick)
                    break
            
            # Finalize
            shutil.move(candidates[idx], image_path)
            selected_image = image_name
            
            # Cleanup unused candidates
            for c in candidates:
                if os.path.exists(c) and c != image_path:
                    os.remove(c)

    # --- 2. SOUND HANDLING ---
    selected_sound = None
    gen_cfg = config.get('generation', {})
    sounds_count = gen_cfg.get('sounds_per_scene', 0)
    
    # Construct audio path
    audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'output', str(book_id), 'audio')
    sound_name = f"{base_name}.mp3"
    sound_path = os.path.join(audio_dir, sound_name)

    if sounds_count and sound_weaver:
        if os.path.exists(sound_path):
            print(f"✅ Sound exists: {sound_name}")
            selected_sound = sound_name
        else:
            # Generate or find candidates
            sound_prompt = audio_prompt or f"{prompt} — ambience, background texture, loopable"
            print(f"🎧 Generating sounds for {base_name}...")
            sound_candidates = sound_weaver.generate_candidates(
                book_id, base_name, sound_prompt, 
                count=sounds_count, 
                length_seconds=gen_cfg.get('sound_length_seconds', 5), 
                model=gen_cfg.get('sound_model', 'eleven_text_to_sound_v2')
            )
            
            # Selection UI
            print('\n--- Sound Candidates ---')
            for i, sc in enumerate(sound_candidates):
                print(f"{i}: {os.path.basename(sc['file'])}")

            s_pick = input(f"Select Sound (0-{len(sound_candidates)-1}), [Enter] skip, 'u' upload: ").strip()
            
            temp_path = None
            if s_pick.isdigit() and 0 <= int(s_pick) < len(sound_candidates):
                # Resolve relative path from sound_weaver
                rel_path = sound_candidates[int(s_pick)]['file']
                temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', rel_path)
            elif s_pick.lower() == 'u':
                u_in = input('Path: ').strip()
                if os.path.exists(u_in): temp_path = u_in

            if temp_path and os.path.exists(temp_path):
                os.makedirs(audio_dir, exist_ok=True)
                shutil.copy(temp_path, sound_path)
                selected_sound = sound_name

    return {'image': selected_image, 'sound': selected_sound}

def check_persistence(smith):
    """Checks for existing progress and asks the user how to proceed."""
    if os.path.exists(smith.output_file) and os.path.getsize(smith.output_file) > 100:
        print("\n" + "═"*60)
        print("💾 EXISTING PROGRESS DETECTED")
        print(f"📍 File: {smith.output_file}")
        print("═"*60)
        
        choice = input("\n[C]ontinue from where you left off?\n[N]ew Start (This will DELETE the existing script and assets)?\n\nChoice [C/N]: ").lower()
        
        if choice == 'n':
            confirm = input("⚠️ Are you sure? This action cannot be undone. (y/n): ").lower()
            if confirm == 'y':
                # Wipe the directory for a clean start
                shutil.rmtree(smith.base_dir)
                os.makedirs(smith.assets_dir, exist_ok=True)
                print("✨ Workspace cleared. Starting fresh...")
                return "fresh"
        return "resume"
    return "fresh"

def run_director():
    # Use absolute paths to ensure script works regardless of execution directory
    maker_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(maker_dir)
    
    config_path = os.path.join(root_dir, "book_config.json")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Validate environment for sound generation provider (ElevenLabs)
    gen_cfg = config.get('generation', {})
    sound_model = gen_cfg.get('sound_model', '')
    if 'eleven' in sound_model.lower():
        if not os.getenv('ELEVENLABS_API_KEY'):
            print("⚠️ WARNING: ELEVENLABS_API_KEY not found in environment. ElevenLabs sound generation will be unavailable until you set ELEVENLABS_API_KEY in your .env or environment.")
    
    book_id = config['book_id']
    book_path = os.path.join(root_dir, "data", "books", config.get("book_filename", f"book_{book_id}.txt"))
    
    architect = AutonomousArchitect(book_path)
    weaver = VisualWeaver() 
    smith = InkSmith(book_id)
    sw = SoundWeaver()  # Sound generator (server-side)
    # 1. USER INTERACTION: Resume or Restart
    state = check_persistence(smith)

    if state == "resume":
        print("🔄 RESUMING: Loading Ink script into LLM context...")
        with open(smith.output_file, "r", encoding="utf-8") as f:
            full_ink = f.read()
        
        # Initialize but don't generate new intro text
        architect.initialize_engine(skip_intro=True) 
        
        # Inject the memory of the previous session
        sync = architect.resume_session(full_ink)
        
        # Find where we are to continue the golden path
        main_scene = architect.generate_main_beat(f"Continuation after {sync.get('last_node')}")
    else:
        # Start fresh
        intro_data = architect.initialize_engine()
        first_scene = architect.generate_main_beat("The very start of the story")
        
        # Initial Art (images + optional sounds)
        intro_assets = run_art_direction(weaver, intro_data['visual_prompt'], "INTRO_SCENE", config, sound_weaver=sw, book_id=book_id, audio_prompt=intro_data.get('audio_prompt'))
        smith.write_intro(intro_data, first_scene['node_id'], audio_file=intro_assets.get('sound'), audio_prompt=intro_data.get('audio_prompt'))
        main_scene = first_scene

    while main_scene:
        # FIX: Define current_id immediately at the start of the loop
        current_id = main_scene.get('node_id', 'unknown_node') 
        if main_scene.get('ending'):
            print("\n" + "✧"*60)
            print("🎬 THE ENDING")
            print("-" * 60)
            print(main_scene['ending'])
            print("✧"*60 + "\n")
            
            assets = run_art_direction(weaver, main_scene['visual_prompt'], current_id, config, sound_weaver=sw, book_id=book_id, audio_prompt=main_scene.get('audio_prompt'))
            smith.write_main_node_start(current_id, main_scene['ending'], assets['image'], [], "END", audio_file=assets.get('sound'))
            print("✅ Story recorded successfully. Narrative complete.")
            break
            
        print("\n" + "="*60)
        print(f"📖 NARRATIVE BEAT: {current_id}")
        print("-" * 60)
        print(main_scene.get('scene_text'))
        print("="*60 + "\n")

        # 1. Main Scene Art (images + optional sounds)
        main_assets = run_art_direction(weaver, main_scene['visual_prompt'], current_id, config, sound_weaver=sw, book_id=book_id, audio_prompt=main_scene.get('audio_prompt'))
        next_placeholder = f"{current_id}_NEXT"
        smith.write_main_node_start(current_id, main_scene.get('scene_text'), main_assets['image'], main_scene.get('choices', []), next_placeholder, audio_file=main_assets.get('sound'), audio_prompt=main_scene.get('audio_prompt'))

        # 2. RESOLVE ALL TRANSITIONS
        choices = main_scene.get('choices', [])
        golden_next_node = None
        reward_node_id = None
        
        for choice in choices:
            c_type = choice.get('type') or "golden"
            
            # Now current_id is safely defined and can be passed here
            print(f"  ↪️ Architecting: [{c_type.upper()}] {choice.get('text')[:30]}...")
            outcome = architect.generate_transition(current_id, choice)
            
            if c_type == 'exquisite':
                reward_base = f"{current_id}_result_{i+1}_reward"
                rew_assets = run_art_direction(weaver, outcome['visual_prompt'], f"{current_id}_REW", config, sound_weaver=sw, book_id=book_id, audio_prompt=outcome.get('audio_prompt'))
                # Pass image filename to the reward node writer (function should accept this)
                reward_node_id = smith.write_reward_node(outcome, rew_assets['image'], current_id)
                architect.reset_to_main_path(current_id)
            
            elif c_type == 'golden':
                golden_next_node = outcome

        # 3. Finalize
        smith.write_choices(current_id, choices, reward_node_id, chapter_start_id=current_chapter_start)

        if golden_next_node:
            # Get the ID for the next beat
            next_id = golden_next_node.get('node_id', f"beat_{int(time.time())}")
            smith.finalize_links(next_id)
            
            print(f"✅ Transitions complete. Next: {next_id}")
            cmd = input("\n[Enter] for next / [Q] to quit: ").lower()
            if cmd == 'q': break
            
            main_scene = golden_next_node 
        else:
            break

if __name__ == "__main__":
    run_director()