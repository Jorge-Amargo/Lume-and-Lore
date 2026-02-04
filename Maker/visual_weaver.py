import requests
import base64
import os
import json
import time
import sys # Added for real-time terminal clearing
import random

class VisualWeaver:
    def __init__(self, api_url="http://127.0.0.1:7860"):
        # FIX: Use absolute paths so Streamlit can find the file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "..", "book_config.json")
        
        # Verify it exists before trying to open
        if not os.path.exists(config_path):
             raise FileNotFoundError(f"VisualWeaver could not find config at: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        
        self.base_url = api_url.rstrip('/')
        
        # FIX: Ensure the output directory is also absolute
        # This points to: .../Lume_and_Lore/data/output/[ID]/assets
        self.output_dir = os.path.join(current_dir, "..", "data", "output", str(self.config['book_id']), "assets")
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)

    def _draw_progress_bar(self, current, total, status="Generating"):
        """Creates a smooth terminal progress bar."""
        length = 40
        filled_length = int(length * current // total)
        bar = '█' * filled_length + '-' * (length - filled_length)
        percent = f"{100 * (current / total):.0f}"
        sys.stdout.write(f'\r{status} |{bar}| {percent}% ({current}/{total})')
        sys.stdout.flush()
        if current == total:
            print() # Move to next line when done

    def generate_batch(self, prompt, base_filename, count=4, callback=None):
        """
        Generates 'count' images.
        :param callback: A function that accepts (current_step, total_steps) to update UI.
        """
        paths = []
        print(f"\n🎨 Starting art production for: {base_filename}")
        
        # Initial terminal bar
        self._draw_progress_bar(0, count)
        
        # Initial UI update (if connected)
        if callback: callback(0, count)
        
        for i in range(count):
            file_name = f"{base_filename}_{i}"
            path = self.generate_image(prompt, file_name)
            
            if path:
                paths.append(path)
            
            # 1. Update Terminal Bar
            self._draw_progress_bar(i + 1, count)
            
            # 2. 🛠️ FIX: Update Streamlit UI Bar (if callback provided)
            if callback:
                callback(i + 1, count)
            
        return paths

    def ensure_correct_model(self):
        target_model = self.config.get("sd_model")
        if not target_model: return

        try:
            opt_res = requests.get(f"{self.base_url}/sdapi/v1/options", timeout=5)
            if opt_res.status_code == 200:
                current_model = opt_res.json().get("sd_model_checkpoint")
                if current_model != target_model:
                    print(f"🔄 Switching model to: {target_model}...")
                    requests.post(f"{self.base_url}/sdapi/v1/options", json={"sd_model_checkpoint": target_model})
                    # Give it a few seconds to load the heavy weights
                    time.sleep(5) 
        except Exception as e:
            print(f"⚠️ Could not check/switch model: {e}")

    def generate_image(self, prompt, filename, retries=3):
        sampler = self.config.get("sd_settings", {}).get("sampler_name", "Euler a")
        scheduler = self.config.get("sd_settings", {}).get("scheduler", "Automatic")
        random_seed = random.randint(1, 1000000000)
        width = self.config.get("visual_settings", {}).get("width", 512)
        height = self.config.get("visual_settings", {}).get("height", 768)
        
        payload = {
            "width": width,   
            "height": height, 
            "prompt": f"{self.config['visual_settings']['master_style']}, {prompt}, {self.config['visual_settings']['positive_prompt']}",
            "negative_prompt": self.config['visual_settings']['negative_prompt'],
            "steps": self.config.get("sd_settings", {}).get("steps", 30),
            "sampler_name": sampler,
            "scheduler": scheduler,
            "seed": random_seed,
            "cfg_scale": 7,
            "override_settings": {
                "sd_model_checkpoint": self.config.get("sd_model")
            }
        }

        save_path = os.path.join(self.output_dir, f"{filename}.png")

        # FIX: The retry loop logic
        for attempt in range(retries):
            try:
                response = requests.post(f"{self.base_url}/sdapi/v1/txt2img", json=payload, timeout=60)
                response.raise_for_status()
                r = response.json()

                # Process and save the image
                image_data = base64.b64decode(r['images'][0])
                with open(save_path, "wb") as f:
                    f.write(image_data)
                
                return save_path # Success! Return the path

            except Exception as e:
                print(f"⚠️ Attempt {attempt+1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2) # Brief pause before trying again
                else:
                    print("❌ All retries failed for image generation.")
                    return None