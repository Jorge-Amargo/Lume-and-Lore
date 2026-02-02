import os
import re
import requests

class GutenbergHarvester:
    # UPDATED: Added '../' to move up from the /maker folder
    def __init__(self, storage_dir="../data/books"):
        self.storage_dir = storage_dir
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)

    def fetch_book(self, book_id):
        """Downloads the raw text from Project Gutenberg."""
        url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
        print(f"--- Searching for Book ID: {book_id} ---")
        
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        else:
            raise Exception(f"Could not find book with ID {book_id}. Check the ID at gutenberg.org")

    def clean_text(self, raw_text):
        """Strips the legal headers and footers from the book."""
        # Standard Gutenberg markers for start and end
        start_markers = [
            r"\*\*\* START OF THIS PROJECT GUTENBERG EBOOK .* \*\*\*",
            r"\*\*\* START OF THE PROJECT GUTENBERG EBOOK .* \*\*\*"
        ]
        end_markers = [
            r"\*\*\* END OF THIS PROJECT GUTENBERG EBOOK .* \*\*\*",
            r"\*\*\* END OF THE PROJECT GUTENBERG EBOOK .* \*\*\*"
        ]

        clean_content = raw_text
        
        # Find the start and cut off everything before it
        for marker in start_markers:
            match = re.search(marker, clean_content, re.IGNORECASE)
            if match:
                clean_content = clean_content[match.end():].strip()
                break

        # Find the end and cut off everything after it
        for marker in end_markers:
            match = re.search(marker, clean_content, re.IGNORECASE)
            if match:
                clean_content = clean_content[:match.start()].strip()
                break

        return clean_content

    def save_book(self, book_id, content):
        """Saves the cleaned text to your local folder."""
        file_path = os.path.join(self.storage_dir, f"book_{book_id}.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

# --- TEST BLOCK ---
if __name__ == "__main__":
    harvester = GutenbergHarvester()
    
    # Let's try 'The Picture of Dorian Gray' (ID: 174)
    # Or 'Alice in Wonderland' (ID: 11)
    TEST_ID = "174" 
    
    try:
        raw = harvester.fetch_book(TEST_ID)
        clean = harvester.clean_text(raw)
        path = harvester.save_book(TEST_ID, clean)
        
        print(f"SUCCESS!")
        print(f"File saved to: {path}")
        print(f"Preview (First 200 characters):\n{clean[:200]}...")
    except Exception as e:
        print(f"ERROR: {e}")