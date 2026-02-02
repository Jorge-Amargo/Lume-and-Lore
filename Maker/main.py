import os
import shutil
import json   
import time
from architect import AutonomousArchitect
from visual_weaver import VisualWeaver
from ink_smith import InkSmith

def run_art_direction(weaver, prompt, base_name):
    candidates = weaver.generate_batch(prompt, base_name)
    if not candidates: return f"{base_name}_fallback"
    
    print(f"\n--- Gallery for {base_name} ---")
    pick = input(f"Select Image (0-3) [0]: ")
    idx = int(pick) if pick.isdigit() and 0 <= int(pick) < 4 else 0
    
    final_name = f"{base_name}_final"
    final_path = os.path.join(weaver.output_dir, f"{final_name}.png")
    import shutil
    shutil.move(candidates[idx], final_path)
    
    for c in candidates:
        if os.path.exists(c) and c != final_path:
            os.remove(c)
    return final_name

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
    with open("../book_config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    
    book_id = config['book_id']
    architect = AutonomousArchitect(f"../data/books/book_{book_id}.txt")
    weaver = VisualWeaver() 
    smith = InkSmith(book_id)

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
        
        # Initial Art
        intro_img = run_art_direction(weaver, intro_data['visual_prompt'], "INTRO_SCENE")
        smith.write_intro(intro_data, first_scene['node_id'])
        main_scene = first_scene

    while main_scene:
        # FIX: Define current_id immediately at the start of the loop
        current_id = main_scene.get('node_id', 'unknown_node') 
        
        print("\n" + "="*60)
        print(f"📖 NARRATIVE BEAT: {current_id}")
        print("-" * 60)
        print(main_scene.get('scene_text'))
        print("="*60 + "\n")

        # 1. Main Scene Art
        main_img = run_art_direction(weaver, main_scene['visual_prompt'], current_id)
        smith.write_main_node_start(main_scene, main_img)

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
                rew_img = run_art_direction(weaver, outcome['visual_prompt'], f"{current_id}_REW")
                reward_node_id = smith.write_reward_node(outcome, rew_img, current_id)
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