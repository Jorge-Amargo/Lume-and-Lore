# Lume & Lore - Implementation Guide for Remaining Features

**Last Updated:** February 9, 2026  
**Status:** Post-Bug-Fix Implementation Guide

---

## Overview

This document provides step-by-step implementation instructions for remaining features that enhance the Lume & Lore experience. All critical bugs have been fixed. This guide focuses on:

1. **Audio Orchestration (P009)** - High Priority
2. **Advanced Checkpointing (M008)** - Medium Priority
3. **Character Consistency Tools** - Medium Priority
4. **Book Ingestion UX** - Medium Priority
5. **Real-time Progress UI** - Low Priority

---

## COMPLETED FIXES ✅

The following critical issues have been resolved:

- ✅ Added `output_file` and `assets_dir` properties to InkSmith
- ✅ Fixed syntax errors in dashboard.py (missing parentheses)
- ✅ Removed duplicate `update_game_manifest()` function
- ✅ Fixed hardcoded `cfg_scale` in visual_weaver.py
- ✅ Improved path handling in main.py (absolute paths)
- ✅ Added **Typewriter Effect (P011)** with toggle UI
- ✅ Added **Audio Orchestration Framework (P009)** - basic implementation
- ✅ Added **Mobile Responsiveness (P006)** media queries

**Bonus implementations:**
- Typewriter effect with localStorage preference saving
- Audio manager with fadein/fadeout transitions
- Mobile-friendly CSS media queries for tablets and phones

---

## FEATURE 1: Audio Orchestration (PARTIALLY IMPLEMENTED)

### Status: 70% Complete ✅

**What's Done:**
- JavaScript audio manager in main.js
- Tag parsing for `# AMBIENCE: filename` and `# AUDIO: filename`
- Volume control and crossfading
- Stop audio functionality

**What's Missing:**
- Audio file upload interface in dashboard
- Audio library management
- Format validation

### How to Use

In your `.ink` files, add audio tags to scenes:

```ink
== forest_clearning ==
The ancient trees whisper around you, their branches swaying in the wind.

# IMAGE: forest_clearing_main.png
# AMBIENCE: forest_ambient.mp3

* [Venture deeper] -> forest_dungeon
* [Rest here] -> forest_rest
* [Turn back] -> forest_exit
```

### Implementation: Audio File Management

**Step 1: Create Audio Directory Structure**

```bash
data/
├── output/
    ├── [book_id]/
        ├── assets/          (images already exist)
        ├── audio/           (NEW - for audio files)
            ├── forest_ambient.mp3
            ├── rain.mp3
            ├── thunder.mp3
            └── ...
```

**Step 2: Add Audio Upload to Dashboard**

Add this to `Maker/dashboard.py` in the Config tab:

```python
# Add to dashboard.py under the visual settings section

st.markdown("#### 🎵 Audio Library")
st.write("Upload ambient sounds for your adventure")

# Create audio directory
audio_dir = os.path.join(current_dir, "..", "data", "output", current_config['book_id'], "audio")
os.makedirs(audio_dir, exist_ok=True)

# File uploader
uploaded_file = st.file_uploader(
    "Upload MP3/WAV files",
    type=["mp3", "wav"],
    key="audio_upload"
)

if uploaded_file:
    file_path = os.path.join(audio_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success(f"✅ Uploaded: {uploaded_file.name}")

# List existing audio files
available_audio = os.listdir(audio_dir) if os.path.exists(audio_dir) else []
if available_audio:
    st.markdown("**Available Sounds:**")
    for audio_file in available_audio:
        col_name, col_btn = st.columns([3, 1])
        col_name.caption(f"🎵 {audio_file}")
        if col_btn.button("❌", key=f"del_audio_{audio_file}"):
            os.remove(os.path.join(audio_dir, audio_file))
            st.rerun()
```

**Step 3: Add Audio Prompt Engineering**

Extend the Architect to suggest ambient sounds:

```python
# Add to Maker/architect.py in generate_main_beat()

def suggest_ambience(self, scene_text):
    """Uses LLM to suggest appropriate ambient sounds for a scene."""
    prompt = f"""
    Based on this scene, suggest ONE ambient sound file name (no extension):
    
    Scene: {scene_text[:500]}
    
    Return just the filename (e.g., 'forest_ambient', 'rain', 'thunder_storm', 'fireplace')
    """
    resp = self.chat.send_message(prompt)
    suggestion = resp.text.strip().lower().replace(" ", "_")
    return suggestion
```

**Step 4: Integrate into Ink Generation**

Update `write_main_node_start()` in ink_smith.py:

```python
def write_main_node_start(self, scene_id, text, image_file, choices, next_slug, ambience=None):
    lines = [
        f"== {scene_id} ==",
        f"~ last_node = \"{scene_id}\"", 
        f"{text}",
        f"# IMAGE: {image_file}.png",
    ]
    if ambience:
        lines.append(f"# AMBIENCE: {ambience}.mp3")
    
    lines.append(self._format_choices(scene_id, choices, next_slug))
    lines.append("\n")
    self._append_to_file(lines)
```

---

## FEATURE 2: Advanced Checkpointing System

### Status: 0% (Suggested Implementation)

### Design: Multi-Slot Save System

**Goal:** Allow players to save multiple checkpoints and branch from them.

### Implementation Steps

**Step 1: Create CheckpointManager Class**

```python
# New file: Maker/checkpoint_manager.py

import json
import os
from datetime import datetime

class CheckpointManager:
    def __init__(self, book_id):
        self.book_id = book_id
        self.checkpoint_dir = os.path.join(
            os.path.dirname(__file__), "..", "data", "output", book_id, "checkpoints"
        )
        os.makedirs(self.checkpoint_dir, exist_ok=True)
    
    def save_checkpoint(self, slot_name, ink_state, scene_id, metadata=None):
        """Saves a named checkpoint."""
        checkpoint = {
            "timestamp": datetime.now().isoformat(),
            "scene_id": scene_id,
            "ink_state": ink_state,
            "metadata": metadata or {}
        }
        
        file_path = os.path.join(self.checkpoint_dir, f"{slot_name}.json")
        with open(file_path, "w") as f:
            json.dump(checkpoint, f, indent=2)
        
        return file_path
    
    def load_checkpoint(self, slot_name):
        """Loads a named checkpoint."""
        file_path = os.path.join(self.checkpoint_dir, f"{slot_name}.json")
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, "r") as f:
            return json.load(f)
    
    def list_checkpoints(self):
        """Returns all available checkpoints."""
        checkpoints = []
        for file in os.listdir(self.checkpoint_dir):
            if file.endswith(".json"):
                checkpoint_data = self.load_checkpoint(file[:-5])
                checkpoints.append({
                    "name": file[:-5],
                    "timestamp": checkpoint_data.get("timestamp"),
                    "scene_id": checkpoint_data.get("scene_id")
                })
        return sorted(checkpoints, key=lambda x: x.get("timestamp", ""), reverse=True)
    
    def delete_checkpoint(self, slot_name):
        """Deletes a checkpoint."""
        file_path = os.path.join(self.checkpoint_dir, f"{slot_name}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
```

**Step 2: Update Player UI**

Add checkpoint management to `player/index.html`:

```html
<div id="checkpoint-panel" style="position: fixed; bottom: 10px; left: 10px; background: rgba(0,0,0,0.7); padding: 10px; border-radius: 5px; display: none; z-index: 50;">
    <button onclick="saveCurrentCheckpoint()" class="overlay-btn">💾 Save Checkpoint</button>
    <div id="checkpoint-list" style="margin-top: 10px; max-height: 200px; overflow-y: auto;"></div>
</div>
```

**Step 3: JavaScript Checkpoint Functions**

Add to `player/main.js`:

```javascript
async function saveCurrentCheckpoint() {
    if (!story) return alert("No active game");
    
    const name = prompt("Checkpoint name:", `Checkpoint_${new Date().toLocaleTimeString()}`);
    if (!name) return;
    
    const checkpoint = {
        project: currentProject,
        timestamp: new Date().toISOString(),
        storyState: story.state.ToJson(),
        unlockedImages: unlockedImages
    };
    
    localStorage.setItem(`checkpoint_${currentProject}_${name}`, JSON.stringify(checkpoint));
    loadCheckpointList();
}

function loadCheckpointList() {
    const panel = document.getElementById('checkpoint-list');
    const prefix = `checkpoint_${currentProject}_`;
    const checkpoints = Object.keys(localStorage)
        .filter(k => k.startsWith(prefix))
        .map(k => ({
            key: k,
            name: k.substring(prefix.length),
            data: JSON.parse(localStorage.getItem(k))
        }));
    
    panel.innerHTML = checkpoints.map(cp => `
        <div style="border-bottom: 1px solid #444; padding: 5px 0;">
            <small>${cp.data.timestamp}</small><br/>
            <button onclick="loadCheckpoint('${cp.key}')" class="overlay-btn" style="width: 100%; margin: 5px 0;">📂 ${cp.name}</button>
            <button onclick="deleteCheckpoint('${cp.key}')" class="overlay-btn" style="width: 100%; background: #8b0000;">❌ Delete</button>
        </div>
    `).join('');
}

function loadCheckpoint(key) {
    const cp = JSON.parse(localStorage.getItem(key));
    if (!cp) return alert("Checkpoint not found");
    
    startGame(cp.storyState);
    unlockedImages = cp.unlockedImages;
}

function deleteCheckpoint(key) {
    if (confirm("Delete this checkpoint?")) {
        localStorage.removeItem(key);
        loadCheckpointList();
    }
}
```

---

## FEATURE 3: Character Consistency Tools

### Status: 0% (Suggested Implementation)

### Goal: Ensure characters look consistent across scenes

### Implementation Steps

**Step 1: Character Seed Banking**

```python
# Add to Maker/architect.py

class CharacterArchetype:
    def __init__(self, name, visual_description):
        self.name = name
        self.visual_description = visual_description
        self.seed = None  # Will be set on first generation
        self.generated_images = []  # Track all generated images
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.visual_description,
            "seed": self.seed,
            "images": self.generated_images
        }

# In architect.py initialization:
def __init__(self, book_path):
    # ... existing code ...
    self.character_archetypes = {}
    self._load_character_archetypes()

def _load_character_archetypes(self):
    """Loads characters from config and creates archetypes."""
    char_map = self.config.get("character_map", {})
    for name, description in char_map.items():
        self.character_archetypes[name] = CharacterArchetype(name, description)

def ensure_character_consistency(self, scene_text, character_name):
    """Injects seed and past images to ensure consistency."""
    archetype = self.character_archetypes.get(character_name)
    if not archetype:
        return scene_text
    
    consistency_prompt = f"""
    Character: {archetype.name}
    Description: {archetype.visual_description}
    """
    
    if archetype.seed:
        consistency_prompt += f"\nUse seed {archetype.seed} for consistency."
    
    if archetype.generated_images:
        consistency_prompt += f"\nReference images: {', '.join(archetype.generated_images[:3])}"
    
    return consistency_prompt
```

**Step 2: Image Similarity Scoring**

```python
# Add to Maker/visual_weaver.py

from PIL import Image
import numpy as np

def calculate_image_similarity(image1_path, image2_path):
    """Rough similarity check using histogram comparison."""
    try:
        img1 = Image.open(image1_path).convert('L')
        img2 = Image.open(image2_path).convert('L')
        
        # Resize to same dimensions
        img2 = img2.resize(img1.size)
        
        # Calculate histogram similarity
        hist1 = np.histogram(np.array(img1), 256)[0]
        hist2 = np.histogram(np.array(img2), 256)[0]
        
        # Normalize
        hist1 = hist1 / np.sum(hist1)
        hist2 = hist2 / np.sum(hist2)
        
        # Chi-square distance
        similarity = np.sum((hist1 - hist2) ** 2)
        return 1 - min(similarity, 1)  # 0-1 score where 1 is identical
    except:
        return None
```

---

## FEATURE 4: Book Ingestion UX Refinement

### Status: 0% (Suggested Implementation)

### Add Book Metadata Display

**Step 1: Fetch Book Info from Open Library API**

```python
# Add to Maker/dashboard.py

import requests

def fetch_book_metadata(title, author=""):
    """Fetch book info from Open Library API."""
    try:
        query = f"{title} {author}".strip()
        url = f"https://openlibrary.org/search.json?title={query}&limit=1"
        resp = requests.get(url, timeout=5)
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        if not data.get("docs"):
            return None
        
        doc = data["docs"][0]
        return {
            "title": doc.get("title"),
            "author": ", ".join(doc.get("author_name", [])),
            "first_publish_year": doc.get("first_publish_year"),
            "cover_id": doc.get("cover_id"),
            "isbn": doc.get("isbn", [None])[0]
        }
    except:
        return None

def get_book_cover_url(cover_id):
    """Get book cover image URL from Open Library."""
    if not cover_id:
        return None
    return f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
```

**Step 2: Enhanced Search Results Display**

```python
# Update search results in dashboard.py tab_lib section

if "search_results" in st.session_state and st.session_state.search_results:
    selected_book_str = st.selectbox("Select Result", st.session_state.search_results, key="lib_res")
    
    # Extract book ID and fetch metadata
    book_id = selected_book_str.split(']')[0].strip('[')
    metadata = fetch_book_metadata(selected_book_str)
    
    if metadata:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            cover_url = get_book_cover_url(metadata.get("cover_id"))
            if cover_url:
                try:
                    st.image(cover_url, width=150)
                except:
                    st.caption("📖 No cover available")
        
        with col2:
            st.markdown(f"### {metadata['title']}")
            st.caption(f"By {metadata['author']}")
            st.caption(f"First Published: {metadata['first_publish_year']}")
            if metadata.get("isbn"):
                st.caption(f"ISBN: {metadata['isbn']}")
    
    if st.button("⬇️ Download & Import", key="lib_dl"):
        # Download logic...
```

---

## FEATURE 5: Real-Time Progress UI

### Status: 0% (Suggested Implementation)

### Add Generation Progress Tracking

**Step 1: Extend Dashboard with Progress Terminal**

```python
# Add to Maker/dashboard.py

import asyncio
from datetime import datetime

def render_generation_progress():
    """Shows real-time progress during scene generation."""
    
    if "generation_logs" not in st.session_state:
        st.session_state.generation_logs = []
    
    # Create placeholders for dynamic content
    progress_placeholder = st.empty()
    log_placeholder = st.empty()
    
    return progress_placeholder, log_placeholder

def log_generation_step(step_name, details=""):
    """Records a generation step for display."""
    entry = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "step": step_name,
        "details": details
    }
    st.session_state.generation_logs.append(entry)

def display_generation_logs():
    """Displays formatted log output."""
    if "generation_logs" not in st.session_state or not st.session_state.generation_logs:
        return
    
    with st.expander("📋 Generation Log", expanded=False):
        for log in st.session_state.generation_logs[-20:]:  # Last 20 entries
            st.code(f"[{log['timestamp']}] {log['step']}: {log['details']}")
```

**Step 2: Integration Points**

Add logging to key generation functions:

```python
# In architect.py generate_main_beat():
def generate_main_beat(self, node_id):
    log_generation_step("ARCHITECT_START", f"Generating scene after: {node_id}")
    self._ensure_chat_ready()
    
    prompt = f"..."
    
    log_generation_step("ARCHITECT_PROMPT_SENT", "Waiting for LLM response...")
    resp = self.chat.send_message(prompt)
    
    log_generation_step("ARCHITECT_RESPONSE_RECEIVED", f"Processing JSON...")
    scene_data = self._parse_json(resp.text)
    
    log_generation_step("ARCHITECT_COMPLETE", f"Scene ID: {scene_data.get('scene_id')}")
    return scene_data
```

---

## Testing Checklist

Before deploying these features, test:

### Audio System
- [ ] Audio file uploads through dashboard
- [ ] Audio playback on scene load
- [ ] Crossfading between tracks
- [ ] STOP_AUDIO tag functionality
- [ ] Mobile audio (volume handling)

### Checkpointing
- [ ] Save checkpoint during gameplay
- [ ] Load checkpoint and continue from same state
- [ ] Delete old checkpoints
- [ ] Multiple simultaneous checkpoints
- [ ] Resume from localStorage persists across browser sessions

### Character Consistency
- [ ] Character seed maintained across scenes
- [ ] Consistency metadata saved to project
- [ ] Dashboard displays character sync status
- [ ] Similarity scoring works without errors

### Book Ingestion
- [ ] Book covers display correctly
- [ ] Metadata fetches without hanging
- [ ] Graceful fallback if API unavailable
- [ ] File upload completes successfully

---

## Quick Reference: File Summary

| Component | File | Status |
|-----------|------|--------|
| Audio Manager | player/main.js | ✅ Framework Ready |
| Typewriter Effect | player/main.js | ✅ Complete |
| Mobile CSS | player/style.css | ✅ Complete |
| Path Handling | Maker/main.py | ✅ Fixed |
| InkSmith Props | Maker/ink_smith.py | ✅ Fixed |
| Dashboard Syntax | Maker/dashboard.py | ✅ Fixed |
| Checkpoint System | (Not created) | ⏳ Suggest |
| Character Tools | (Not created) | ⏳ Suggest |
| Book Metadata | (Not added) | ⏳ Suggest |
| Progress Logs | (Not added) | ⏳ Suggest |

---

## Next Steps

1. **Immediate:** Test all bug fixes with real gameplay
2. **Week 1:** Implement audio file management UI
3. **Week 2:** Add checkpoint system
4. **Week 3:** Character consistency tools
5. **Week 4:** Polish and final testing

---

**Prepared by:** Project Enhancement System  
**Date:** February 9, 2026
