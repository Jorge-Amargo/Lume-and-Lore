# 🕯️ Lume & Lore

**Lume & Lore** is an AI-driven interactive storytelling engine that combines the narrative power of ink script with the generative capabilities of Large Language Models (LLMs) and Stable Diffusion. It allows creators to build immersive, branching narratives with dynamically generated visuals and audio.

## 🌟 Features

* **AI-Assisted Writing**: Uses Google Gemini to help draft and expand ink scripts.
* **Visual Weaver**: Generates scene illustrations and character portraits on the fly.
* **Audio Orchestration**: Adds ambient soundscapes and effects to enhance immersion.
* **Interactive Player**: A web-based player to experience the created stories.
* **RPG Trait System**: Define up to 3 custom character traits (e.g., Magic, Strength, Virtue) that are tracked via Ink variables and influenced by player choices.
* **Smart Resume**: Intelligent state synchronization that recognizes the last story beat and maintains the correct scene counter even after restarts.
* **Compact Director Dashboard**: A streamlined UI optimized for horizontal space, allowing side-by-side editing of story text and choice outcomes.
* **Interactive Player**: A web-based player to experience the created stories.

## 🛠️ Prerequisites

* Python 3.10+
* A Google Cloud Project with the Gemini API enabled.
* (Optional) A local Stable Diffusion WebUI instance for visual generation.

## 📦 Installation

1.  **Clone the repository**:
    ```bash
    git clone [https://github.com/your-username/lume-and-lore.git](https://github.com/your-username/lume-and-lore.git)
    cd lume-and-lore
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment**:
    Create a `.env` file in the root directory and add your API keys:
    ```env
    GEMINI_API_KEY=your_api_key_here
    ```

## 🚀 Usage

### Running the Maker Dashboard
To start the creative dashboard for building your story:
```bash
run maker.bat
# Or manually: streamlit run Maker/dashboard.py
Playing the Game
To launch the web player:

Bash
run player.bat
# Or manually: python -m http.server -d player 8000
Then open http://localhost:8000 in your browser.

📂 Project Structure
Maker/: Core Python logic for the story generation engine.
architect.py: Manages the LLM interaction and handles the narrative flow.
ink_smith.py: Translates AI drafts into valid Ink script syntax.
visual_weaver.py: Handles image generation.
sound_weaver.py: Handles audio generation.
dashboard.py: The Streamlit UI.

player/: HTML/JS web player for the game.
book_config.json: Configuration for the current story.