import json
import os

class ProgressManager:
    def __init__(self, filepath="checkpoint.json"):
        self.filepath = filepath

    def save_progress(self, book_id, last_chunk_index):
        data = {
            "book_id": book_id,
            "last_chunk_index": last_chunk_index
        }
        with open(self.filepath, 'w') as f:
            json.dump(data, f)
        print(f"--- Progress Saved: Chunk {last_chunk_index} ---")

    def load_progress(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                return json.load(f)
        return {"book_id": None, "last_chunk_index": 0}