import os
import time
import json

class InkSmith:
    def __init__(self, book_id):
        self.base_dir = os.path.join(os.path.dirname(__file__), "..", "data", "output", book_id)
        os.makedirs(self.base_dir, exist_ok=True)
        self.ink_path = os.path.join(self.base_dir, "adventure.ink")
        
        from utils import DashboardUtils
        self.config = DashboardUtils.load_config()
        self.images_per_scene = self.config.get('generation', {}).get('images_per_scene', 4)
        
        # Initialize file (Keep last_node for Resume logic, remove health/morale)
        if not os.path.exists(self.ink_path):
            traits_cfg = self.config.get("traits", {})
            header_lines = ["// Lume & Lore Adventure Script"]
            
            for key in ["trait_1", "trait_2", "trait_3"]:
                trait = traits_cfg.get(key, {})
                if trait.get("label"): # Nur deklarieren, wenn ein Name existiert
                    header_lines.append(f"VAR {key} = {trait.get('initial', 50)}  // {trait['label']}")
            
            header_lines.append("VAR last_node = \"intro\"")
            header_lines.append("-> intro\n\n")
            self._write_to_file(header_lines)
    
    @property
    def output_file(self):
        """Alias for ink_path used by main.py for persistence checks."""
        return self.ink_path
    
    @property
    def assets_dir(self):
        """Directory for storing generated images and assets."""
        return os.path.join(self.base_dir, "assets")

    def get_last_node(self):
        """Findet den letzten echten Szenen-Knoten in der Datei."""
        if not os.path.exists(self.ink_path):
            return "intro"
        
        last_knot = "intro"
        with open(self.ink_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("== ") and "==" in line[3:]:
                    knot_name = line.split("==")[1].strip()
                    # Filter: Ignoriere Ergebnisse und Platzhalter
                    if "_next" not in knot_name.lower() and "_result" not in knot_name.lower():
                        last_knot = knot_name
        return last_knot

    def count_existing_scenes(self):
        """Zählt nur die echten Story-Szenen (ohne Results/Placeholders)."""
        if not os.path.exists(self.ink_path):
            return 0
        
        count = 0
        with open(self.ink_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("== ") and "==" in line[3:]:
                    knot_name = line.split("==")[1].strip()
                    if "_next" not in knot_name.lower() and "_result" not in knot_name.lower():
                        count += 1
        return count

    def get_full_script(self):
        """Returns the entire script content for LLM context."""
        if not os.path.exists(self.ink_path): return ""
        with open(self.ink_path, "r", encoding="utf-8") as f:
            return f.read()
        
    def patch_placeholder_links(self, placeholder_id, real_new_id):
        """
        Reads the Ink file, finds all references to the placeholder (e.g. 'garden_next'),
        and replaces them with the confirmed new scene ID (e.g. 'dungeon').
        """
        if not os.path.exists(self.ink_path):
            return

        with open(self.ink_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # We replace the divert target AND the knot name if it was pre-written
        # 1. Replace the divert: -> garden_next  ==>  -> dungeon
        # 2. Replace the knot (if it exists): == garden_next ==  ==>  == dungeon ==
        # We target the specific placeholder string.
        updated_content = content.replace(placeholder_id, real_new_id)
        
        with open(self.ink_path, "w", encoding="utf-8") as f:
            f.write(updated_content)
            
    def write_intro(self, scene_data, next_slug, audio_file: str = None, audio_prompt: str = None):
        # 🛠️ FIX: Use the actual scene_id (e.g., "intro") so result nodes match
        scene_id = scene_data.get('scene_id', 'intro')
        # Header with ONLY the necessary tracking variable
        header = [
            "// Lume & Lore Adventure Script",
            "VAR last_node = \"intro\"",
            "-> intro\n"
        ]

        lines = [
            "== intro ==",
            f"{scene_data.get('scene_text')}",
        ]
        # Only include an image tag if images are enabled in the config
        if getattr(self, 'images_per_scene', 1) > 0:
            lines.append(f"# IMAGE: intro_main.png")
        if audio_file:
            lines.append(f"# AUDIO: {audio_file}")

        # Render generated choices for the intro the same way other scenes do.
        # If the architect hasn't produced choices, divert to the next slug.
        choices = scene_data.get('choices', [])
        if choices:
            lines.append(self._format_choices('intro', choices, next_slug))
        else:
            lines.append(f"-> {next_slug}")

        lines.append("\n")

        # KEY FIX: Overwrite file to clear previous runs (Fixes duplicate intro)
        self._write_to_file(header + lines)

    def write_main_node_start(self, scene_id, text, image_file, choices, next_slug, audio_file: str = None, audio_prompt: str = None):
        lines = [
            f"== {scene_id} ==",
            f"{text}",
        ]
        # Only include an image tag if images are enabled in the config
        if getattr(self, 'images_per_scene', 1) > 0 and image_file:
            lines.append(f"# IMAGE: {image_file}.png")
        if audio_file:
            lines.append(f"# AUDIO: {audio_file}")
        if not choices:
            lines.append("-> END")
        else:
            lines.append(self._format_choices(scene_id, choices, next_slug))
            
        lines.append("\n")
        self._append_to_file(lines)

    def write_bridge(self, from_id, to_id):
        """🛠️ NEW: Links a placeholder (e.g. intro_next) to a semantic name (e.g. the_tiny_cake)"""
        if from_id == to_id: return # No bridge needed if names match
        lines = [f"== {from_id} ==", f"-> {to_id}\n"]
        self._append_to_file(lines)

    def write_choice_outcomes(self, parent_id, choices, next_main_id):
        lines = []
        for i, choice in enumerate(choices):
            choice_slug = f"{parent_id}_result_{i+1}"
            lines.append(f"== {choice_slug} ==")
            
            outcome = choice.get('outcome_text', "You move forward.")
            lines.append(f"{outcome}")

            if choice.get('type') == 'exquisite':
                # Use a canonical scene-level reward image name (no per-result suffix)
                if getattr(self, 'images_per_scene', 1) > 0:
                    lines.append(f"# IMAGE: {parent_id}_reward.png")
                # Mark successful/exquisite outcomes as an Ink tag (not shown to player)
                lines.append("# good")
            elif choice.get('type') == 'bad':
                # Use an Ink tag for negative outcomes (hidden from the player)
                lines.append("# bad")
                lines.append(f"-> {parent_id}\n")
                continue # Bad path loops back
            
            trait_changes = choice.get('trait_changes', {})
            for t_key, delta in trait_changes.items():
                if delta != 0:
                    # Format: ~ trait_1 = trait_1 + 10
                    operator = "+" if delta > 0 else "-"
                    abs_delta = abs(delta)
                    lines.append(f"~ {t_key} = {t_key} {operator} {abs_delta}")    
            lines.append(f"-> {next_main_id}\n")
            
        self._append_to_file(lines)

    def _format_choices(self, parent_id, choices, next_main_id):
        choice_lines = []
        for i, c in enumerate(choices):
            choice_slug = f"{parent_id}_result_{i+1}"
            choice_lines.append(f"* [{c.get('text')}] -> {choice_slug}")
        return "\n".join(choice_lines)

    # --- THE HELPER METHODS (Ensure these are inside the class!) ---
    def _write_to_file(self, lines):
        with open(self.ink_path, "w", encoding="utf-8") as f:
            f.writelines(line + "\n" for line in lines)

    def _append_to_file(self, lines):
        with open(self.ink_path, "a", encoding="utf-8") as f:
            f.writelines(line + "\n" for line in lines)
    
    def write_placeholder_knot(self, knot_id):
        """Writes a temporary knot to allow compilation of incomplete stories."""
        lines = [
            f"\n== {knot_id} ==",
            f"// TEMPORARY PLACEHOLDER",
            f"[...The story continues in {knot_id}...]",
            "-> END",
            "\n"
        ]
        self._append_to_file(lines)

    def remove_knot(self, knot_id):
        """Removes a specific knot definition from the file (used when replacing a placeholder)."""
        if not os.path.exists(self.ink_path): return
        
        with open(self.ink_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        new_lines = []
        skip = False
        start_marker = f"== {knot_id} =="
        
        for line in lines:
            if line.strip() == start_marker:
                skip = True
            
            if skip:
                # Stop skipping if we hit the next knot (or EOF)
                if line.strip().startswith("==") and line.strip() != start_marker:
                    skip = False
                    new_lines.append(line)
            else:
                new_lines.append(line)
                
        with open(self.ink_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    
    def connect_scenes(self, source_placeholder_id, target_scene_id):
        """
        Updates a placeholder knot (e.g. 'intro_next') to divert to the new scene 
        (e.g. '-> the_oak_closet'), effectively linking the story segments.
        """
        if not os.path.exists(self.ink_path): return

        with open(self.ink_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        inside_target = False
        start_marker = f"== {source_placeholder_id} =="

        for line in lines:
            if line.strip() == start_marker:
                inside_target = True
                new_lines.append(line) # Keep the header (e.g. "== intro_next ==")
                # Write the connection link immediately
                new_lines.append(f"-> {target_scene_id}\n")
                continue

            if inside_target:
                # Skip the old placeholder text ("...Story continues...") until next knot
                if line.strip().startswith("=="):
                    inside_target = False
                    new_lines.append(line)
            else:
                new_lines.append(line)

        with open(self.ink_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)