import sqlite3
import re
import os

# CONFIGURATION
INPUT_FILE = "GUTINDEX.ALL.new"  # Change to "Gutindex_test.txt" to test first
DB_NAME = "gutenberg_index.db"

def build_database():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found.")
        return

    # 1. Setup Database
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS titles")
    c.execute("DROP TABLE IF EXISTS authors")
    c.execute("CREATE TABLE titles (book_id INTEGER, name TEXT)")
    c.execute("CREATE TABLE authors (book_id INTEGER, name TEXT)")

    print(f"🛠️  Processing {INPUT_FILE}...")

    # 2. Parsing Logic
    # We read the file and split into blocks by detecting the book ID at the end of lines
    with open(INPUT_FILE, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Regex to find a title/author block ending with a 1-6 digit ID
    # Matches: [Title/Author Text] [Spaces] [ID]
    entries = re.findall(r"(.+?)\s+(\d{1,6})\n", content, re.DOTALL)

    processed_count = 0
    for text_block, book_id in entries:
        # Clean up newlines and extra spaces within the title/author block
        clean_text = " ".join(text_block.split())
        
        # Detect Author (Gutenberg usually uses "Title, by Author")
        if ", by " in clean_text:
            parts = clean_text.split(", by ")
            title = parts[0].strip()
            author = parts[1].strip()
        else:
            title = clean_text.strip()
            author = "Unknown"

        # Check for [Language: ...] or [Subtitle: ...] in the block
        # and append it to the title so the Search Filter can find it.
        # This ensures "[Language: French]" is indexed!
        extra_meta = re.findall(r"(\[.*?\])", clean_text)
        if extra_meta:
            # Re-attach metadata to title for indexing
            meta_str = " ".join(extra_meta)
            # Remove meta from the clean title to avoid duplication
            for m in extra_meta:
                title = title.replace(m, "").strip()
            title = f"{title} {meta_str}"

        # 3. Insert into DB
        c.execute("INSERT INTO titles VALUES (?, ?)", (book_id, title))
        c.execute("INSERT INTO authors VALUES (?, ?)", (book_id, author))
        processed_count += 1

    conn.commit()
    conn.close()
    print(f"✅ Success! Indexed {processed_count} books into {DB_NAME}.")

if __name__ == "__main__":
    build_database()