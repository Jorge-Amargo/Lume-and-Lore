import os
import re
import sqlite3

# --- CONFIGURATION ---
FILENAME = "GUTINDEX.ALL.new"
DB_NAME = "gutenberg_index.db"

def parse_index_file(file_path):
    print(f"📖 Reading index file: {file_path}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ Error: File '{FILENAME}' not found in current directory.")
        return []

    # 1. Extract Listings Section
    start_marker = "<===LISTINGS===>"
    end_marker = "<==End of GUTINDEX.ALL==>"
    
    try:
        # We look for the markers to slice the relevant content
        start_idx = content.index(start_marker) + len(start_marker)
        end_idx = content.index(end_marker)
        listings = content[start_idx:end_idx]
        print("   ✅ Markers found. Processing listings...")
    except ValueError:
        print("❌ Error: Start/End markers not found in file.")
        return []

    # 2. Split into blocks (entries are separated by blank lines)
    # Using regex to split by double newlines (or more)
    blocks = re.split(r'\n\s*\n', listings)
    
    extracted_entries = []
    skipped_count = 0
    
    for block in blocks:
        lines = [l for l in block.split('\n') if l.strip()]
        if not lines: continue

        # --- FILTERING LOGIC ---
        is_english = True
        clean_lines = []
        
        for line in lines:
            # Check for Language tag
            if line.strip().startswith('[Language:'):
                lang = line.strip()[10:].split(']')[0].strip()
                if lang.lower() != 'english':
                    is_english = False
            
            # Skip Metadata: lines starting with '[' or indented lines
            if line.strip().startswith('[') or line.startswith(' ') or line.startswith('\t'):
                continue
            
            clean_lines.append(line)

        # Skip if non-English or no valid text lines remain
        if not is_english:
            skipped_count += 1
            continue
            
        if not clean_lines:
            continue

        # --- EXTRACTION LOGIC ---
        book_id = None
        
        # Find the line ending with the Book ID number
        for i, line in enumerate(clean_lines):
            # Regex: look for number at the very end of the line
            match = re.search(r'\s+(\d+)\s*$', line)
            if match:
                book_id = match.group(1)
                # Remove the ID from the text line so it doesn't end up in the title
                clean_lines[i] = line[:match.start()].strip()
                break
        
        if book_id:
            # Combine remaining text (handles multi-line titles)
            full_text = " ".join(clean_lines)
            full_text = re.sub(r'\s+', ' ', full_text).strip()
            
            # Split Title and Author by the first ", by "
            if ", by " in full_text:
                parts = full_text.split(", by ", 1)
                title = parts[0].strip()
                author = parts[1].strip()
            else:
                title = full_text
                author = "Unknown"

            extracted_entries.append((book_id, title, author))

    print(f"   ℹ️ Skipped {skipped_count} non-English entries.")
    return extracted_entries

def build_database(entries):
    print(f"🔨 Building Database '{DB_NAME}' with {len(entries)} entries...")
    
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
        
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Create Tables (Schema matching Dashboard requirements)
    c.execute('CREATE TABLE titles (name TEXT, book_id INTEGER)')
    c.execute('CREATE TABLE authors (name TEXT, book_id INTEGER)')
    c.execute('CREATE TABLE books (id INTEGER PRIMARY KEY, rights INTEGER, language INTEGER, gutenberg_book_id INTEGER)')
    
    count = 0
    for book_id, title, author in entries:
        try:
            bid = int(book_id)
            c.execute('INSERT OR IGNORE INTO books (id, rights, language, gutenberg_book_id) VALUES (?, 1, 1, ?)', (bid, bid))
            c.execute('INSERT INTO titles (name, book_id) VALUES (?, ?)', (title, bid))
            c.execute('INSERT INTO authors (name, book_id) VALUES (?, ?)', (author, bid))
            count += 1
        except ValueError:
            pass # Skip if ID is not an integer
            
    conn.commit()
    conn.close()
    print(f"🎉 SUCCESS! Database ready with {count} books.")

def main():
    # Get Current Directory
    current_dir = os.getcwd()
    file_path = os.path.join(current_dir, FILENAME)
    
    entries = parse_index_file(file_path)
    
    if entries:
        build_database(entries)
    else:
        print("⚠️ No entries found. Check if the file exists and is not empty.")

if __name__ == "__main__":
    main()