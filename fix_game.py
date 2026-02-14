import os
import json

def fix_installation():
    # 1. Determine Paths
    root_dir = os.path.abspath(os.path.dirname(__file__))
    data_dir = os.path.join(root_dir, "data", "output")
    manifest_path = os.path.join(data_dir, "manifest.json")
    
    print(f"🔍 Scanning: {data_dir}")

    if not os.path.exists(data_dir):
        print("❌ Error: 'data/output' folder not found!")
        return

    # 2. Find Games (Folders with adventure.json)
    games = []
    for folder_name in os.listdir(data_dir):
        folder_path = os.path.join(data_dir, folder_name)
        adventure_path = os.path.join(folder_path, "adventure.json")
        
        if os.path.isdir(folder_path) and os.path.exists(adventure_path):
            print(f"   ✅ Found game: {folder_name}")
            games.append({
                "id": folder_name,
                "title": folder_name.replace("_", " ").title() # Make a pretty title
            })

    if not games:
        print("❌ No games found! Make sure you have an 'adventure.json' inside a folder in data/output.")
        return

    # 3. Write Valid Manifest
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(games, f, indent=4)
        print(f"🎉 Success! Created valid manifest.json with {len(games)} games.")
        print(f"   Location: {manifest_path}")
    except Exception as e:
        print(f"❌ Failed to write file: {e}")

if __name__ == "__main__":
    fix_installation()
    input("\nPress Enter to exit...")