import os
import time

class InkSmith:
    def __init__(self, book_id):
        self.base_dir = os.path.join(os.path.dirname(__file__), "..", "data", "output", book_id)
        os.makedirs(self.base_dir, exist_ok=True)
        self.ink_path = os.path.join(self.base_dir, "adventure.ink")
        
        # Initialize file with Variables if it doesn't exist
        if not os.path.exists(self.ink_path):
            header = [
                "// Lume & Lore Adventure Script",
                "VAR health = 100",
                "VAR morale = 50",
                "VAR last_node = \"intro\"",
                "-> intro\n\n"
            ]
            self._write_to_file(header)

    def write_intro(self, scene_data, next_slug):
        # 🛠️ FIX: Use the actual scene_id (e.g., "intro") so result nodes match
        scene_id = scene_data.get('scene_id', 'intro')
        lines = [
            "== intro ==",
            f"~ last_node = \"intro\"",
            f"{scene_data.get('scene_text')}",
            f"# IMAGE: intro_main.png",
            # 🛠️ FIX: This writes the '*' choices into the intro node
            self._format_choices(scene_id, scene_data.get('choices', []), next_slug),
            "\n"
        ]
        self._append_to_file(lines)

    def write_main_node_start(self, scene_id, text, image_file, choices, next_slug):
        lines = [
            f"== {scene_id} ==",
            f"~ last_node = \"{scene_id}\"", 
            f"{text}",
            f"# IMAGE: {image_file}.png",
            self._format_choices(scene_id, choices, next_slug),
            "\n"
        ]
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
                lines.append(f"# IMAGE: {choice_slug}_reward.png")
            elif choice.get('type') == 'bad':
                lines.append("\n<i>Fate frowns. You must try again.</i>")
                lines.append(f"-> {parent_id}\n")
                continue # Bad path loops back
                
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