# 🕯️ Lume & Lore: The AI Director Engine

> **Vision:** To transform the silent pages of classic literature into living, breathing, branching interactive adventures using modern AI orchestration.

## 🎭 The Strategy
Lume & Lore is an "AI Director" that bridges the gap between Large Language Models (LLMs) and Game Engines. Instead of just generating text, it acts as a production pipeline that:
1. **Architects:** Analyzes source text (e.g., *Alice in Wonderland*) to create logical narrative beats.
2. **Weaves:** Directs Stable Diffusion to generate high-fidelity, consistent visual assets for every scene.
3. **Smiths:** Translates the AI's creativity into valid **Ink** (inklestudios) code—a professional industry standard for narrative games.

## 🏗️ The Current Blueprint



### 1. The Branch-First Crawler
The engine ensures a 100% playable experience by resolving transitions *before* the story proceeds. For every beat, the engine generates:
* **The Golden Path:** The canonical story progression.
* **The Exquisite Path:** A hidden reward/side-track with variable changes (e.g., +Corruption, -Vitality).
* **The Bad Path:** A terminal failure state that loops back to the chapter start.

### 2. State-Persistence & Memory
To combat LLM "amnesia," the engine uses the current `.ink` script as a persistent memory bank. On restart, the system injects the existing game state back into Gemini's context, ensuring narrative continuity.

### 3. Visual Continuity
Using SDXL with dynamic seeds and strict directorial prompting, the engine prevents generic "static" images, forcing the AI to describe character actions and environments relative to the prose.



## 🚀 Features
* **Director Dashboard:** A visual web interface (Streamlit) to control every aspect of generation.
* **Integrated Library:** Search and download books directly from Project Gutenberg's catalog of 70,000+ titles.
* **Visual Weaver:** Automatic prompt engineering and image generation via WebUI Forge (SDXL).
* **Branch-First Storytelling:** Generates "Golden Paths" (main plot) and "Exquisite Paths" (rewarding side-quests) automatically.
* **Ink Export:** Produces ready-to-compile `.ink` files for game development.

## 🛠️ Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/Jorge-Amargo/Lume-and-Lore.git](https://github.com/Jorge-Amargo/Lume-and-Lore.git)
    cd Lume-and-Lore
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup Environment:**
    Create a `.env` file in the root directory:
    ```env
    GEMINI_API_KEY=your_google_api_key_here
    ```

4.  **Build the Library Index (One-time setup):**
    Ensure `GUTINDEX.ALL.new` is in the root folder, then run:
    ```bash
    python build_library_index.py
    ```

## 🎮 Usage

1.  **Start the Stable Diffusion Server:**
    Launch your WebUI Forge with the API flag:
    ```bash
    ./webui-user.bat --api
    ```

2.  **Launch the Director Dashboard:**
    ```bash
    streamlit run Maker/dashboard.py
    ```

3.  **Create:**
    * Go to the **Library** tab to select or download a book.
    * Go to **Config** to choose your AI Model and Art Style.
    * Click **Initialize Engine** and start directing your story!

## 📂 Project Structure
* `Maker/`: Core Python logic (Architect, Weaver, Smith, Dashboard).
* `data/books/`: Raw text files from Gutenberg.
* `data/output/`: Generated assets and Ink scripts.
* `web/`: HTML/JS templates for playing the generated game.

## 📝 License
MIT