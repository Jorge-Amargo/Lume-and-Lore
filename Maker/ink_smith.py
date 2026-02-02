import os
import time

class InkSmith:
    def __init__(self, book_id):
        self.book_id = book_id
        # Define and create the project structure: ../data/output/[ID]/assets/
        self.base_dir = os.path.join("..", "data", "output", str(book_id))
        self.assets_dir = os.path.join(self.base_dir, "assets")
        self.output_file = os.path.join(self.base_dir, f"adventure_{book_id}.ink")
        
        os.makedirs(self.assets_dir, exist_ok=True)

    def write_intro(self, intro_data, first_node_id):
        """Initializes the Ink file with variables and the introduction."""
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(f"// Lume & Lore: {self.book_id} Script\n")
            
            f.write("=== intro ===\n")
            f.write(f"# IMAGE: INTRO_SCENE_final\n")
            f.write(f"{intro_data.get('scene_text', 'The journey begins...')}\n")
            f.write(f"-> {first_node_id}\n\n")

    def log_asset(self, asset_name):
        """Logs the asset to a manifest file for easy verification."""
        manifest_path = os.path.join(self.base_dir, "asset_manifest.txt")
        with open(manifest_path, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] Asset Created: {asset_name}.png\n")

    def write_main_node_start(self, scene, final_image_name):
        node_id = scene.get('node_id', 'unknown')
        # Log it!
        self.log_asset(final_image_name) 
        
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(f"\n=== {node_id} ===\n")
            f.write(f"# IMAGE: {final_image_name}\n")
            f.write(f"{scene.get('scene_text')}\n\n")

    def write_choices(self, main_scene_id, choices, reward_node_id=None, chapter_start_id="intro"):
        """Writes the branching logic. 'Bad' choices now loop back to the chapter start."""
        with open(self.output_file, "a", encoding="utf-8") as f:
            for i, choice in enumerate(choices):
                c_type = choice.get('type') or choice.get('choice_type') or "golden"
                c_text = choice.get('text', f"Option {i+1}")
                
                if c_type == 'golden':
                    f.write(f"+ [{c_text}] -> NEXT_SCENE_PLACEHOLDER\n")
                
                elif c_type == 'exquisite':
                    target = reward_node_id if reward_node_id else "NEXT_SCENE_PLACEHOLDER"
                    f.write(f"+ [{c_text}] -> {target}\n")
                
                elif c_type == 'bad':
                    # Extract the failure message from the AI's response
                    failure_text = choice.get('outcome_text') or choice.get('death_text') or "Fate has a cruel way of intervening."
                    
                    f.write(f"+ [{c_text}]\n")
                    f.write(f"    {failure_text}\n")
                    f.write(f"    *** Better luck next time! Try again. ***\n")
                    # Send the player back to the start of the chapter
                    f.write(f"    -> {chapter_start_id}\n") 
            f.write("\n")

    def write_reward_node(self, reward_scene, final_image_name, parent_id):
        """Writes a side-scene that provides a reward then returns to the main path."""
        reward_node_id = f"{parent_id}_reward"
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(f"=== {reward_node_id} ===\n")
            f.write(f"# IMAGE: {final_image_name}\n")
            
            # Check for variable adjustments (Malus/Bonus)
            updates = reward_scene.get('variable_change') or {}
            if isinstance(updates, dict):
                for var, val in updates.items():
                    # Ink syntax for incrementing/decrementing
                    op = "+=" if val >= 0 else "-="
                    f.write(f"~ {var} {op} {abs(val)}\n")
            
            f.write(f"{reward_scene.get('scene_text', 'A moment of unexpected insight.')}\n")
            f.write(f"+ [Return to the main path] -> NEXT_SCENE_PLACEHOLDER\n\n")
        return reward_node_id

    def finalize_links(self, next_node_id):
        """Searches for placeholders and replaces them with the actual next node ID."""
        if not os.path.exists(self.output_file): return
        
        with open(self.output_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # This connects the 'Golden' and 'Exquisite Return' paths to the next main beat
        new_content = content.replace("NEXT_SCENE_PLACEHOLDER", next_node_id)
        
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(new_content)