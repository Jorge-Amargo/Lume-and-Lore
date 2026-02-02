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

## 🚀 Getting Started

1. **Clone the Repo:** `git clone https://github.com/yourusername/Lume-and-Lore.git`
2. **Setup Environment:**
   * Install requirements: `pip install -r requirements.txt`
   * Create a `.env` file with your `GEMINI_API_KEY`.
3. **Start Stable Diffusion:** Ensure WebUI Forge is running with `--api` enabled.
4. **Launch the Director:** `python Maker/main.py`