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
        
        # Normalize SD model location: prefer top-level sd_model but fallback to sd_settings.sd_model
        sd_settings = self.config.get("sd_settings", {})
        print(f"📖 book_config.json loaded. sd_settings keys: {list(sd_settings.keys())}")
        print(f"📖 book_config.json sd_settings.sd_model: {sd_settings.get('sd_model')}")
        print(f"📖 book_config.json top-level sd_model: {self.config.get('sd_model')}")
        
        if not self.config.get("sd_model") and sd_settings.get("sd_model"):
            self.config["sd_model"] = sd_settings.get("sd_model")
            print(f"✅ Normalized: copied sd_settings.sd_model to top-level sd_model")
        # Also keep a convenience attribute
        self.sd_model = self.config.get("sd_model")
        print(f"✅ VisualWeaver initialized with SD model: {self.sd_model}")

        self.base_url = api_url.rstrip('/')
        # Defensive check: if someone passed a book_id by mistake (no scheme), fall back to localhost
        if not self.base_url.startswith('http'):
            print(f"⚠️ VisualWeaver received non-URL api_url '{api_url}'. Falling back to http://127.0.0.1:7860")
            self.base_url = "http://127.0.0.1:7860"
        
        # FIX: Ensure the output directory is also absolute
        # This points to: .../Lume_and_Lore/data/output/[ID]/assets
        self.output_dir = os.path.join(current_dir, "..", "data", "output", str(self.config['book_id']), "assets")
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
    
    def check_connection(self):
        """Checks if the SD WebUI is reachable. Returns (Success, Message)."""
        try:
            response = requests.get(f"{self.base_url}/sdapi/v1/options", timeout=3)
            if response.status_code == 200:
                return True, "Connected"
            elif response.status_code == 404:
                return False, "Server Running but API not found. Add '--api' to COMMANDLINE_ARGS."
            else:
                return False, f"Server Error (Status: {response.status_code})"
        except requests.exceptions.ConnectionError:
            return False, "Connection Refused. Is WebForge running?"
        except Exception as e:
            return False, f"Error: {e}"
    
    def get_sd_models(self):
        """Fetches the list of available model checkpoints from SD WebUI."""
        try:
            response = requests.get(f"{self.base_url}/sdapi/v1/sd-models", timeout=3)
            if response.status_code == 200:
                # Return list of model titles (e.g. "v1-5-pruned.ckpt [e144158e]")
                return [m['title'] for m in response.json()]
        except Exception as e:
            print(f"Warning: Could not fetch SD models: {e}")
        return []
        
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
        # Ensure the desired SD model from config is active before starting
        try:
            self.ensure_correct_model()
        except Exception as e:
            print(f"⚠️ Warning: ensure_correct_model raised: {e}")

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
        """Ensure the Web UI is using the SD model specified in book_config.json.
        Supports model being defined either at top-level `sd_model` or under `sd_settings.sd_model`.
        """
        target_model = getattr(self, 'sd_model', None) or self.config.get('sd_model')
        if not target_model:
            print("ℹ️ No SD model configured in book_config.json; leaving Web UI model unchanged.")
            return

        try:
            opt_res = requests.get(f"{self.base_url}/sdapi/v1/options", timeout=5)
            if opt_res.status_code == 200:
                current_model = opt_res.json().get("sd_model_checkpoint")
                print(f"🔍 Web UI currently has sd_model_checkpoint: {current_model}")
                print(f"🔍 Target model from book_config.json: {target_model}")
                if current_model != target_model:
                    print(f"🔄 Switching model to: {target_model}...")
                    requests.post(f"{self.base_url}/sdapi/v1/options", json={"sd_model_checkpoint": target_model})
                    # Give it a few seconds to load the heavy weights
                    time.sleep(5)
                    print(f"✅ Model switch completed")
                else:
                    print(f"✅ SD model already set to: {target_model}")
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
            "cfg_scale": self.config.get("sd_settings", {}).get("cfg_scale", 7.0),
            "override_settings": {
                "sd_model_checkpoint": self.config.get("sd_model")
            }
        }

        save_path = os.path.join(self.output_dir, f"{filename}.png")
        
        print(f"📋 Payload will use sd_model_checkpoint: {self.config.get('sd_model')}")

        # FIX: The retry loop logic
        for attempt in range(retries):
            try:
                print(f"Posting to {self.base_url}/sdapi/v1/txt2img with payload keys: {list(payload.keys())}")
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