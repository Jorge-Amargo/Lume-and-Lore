import streamlit as st
import os
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '..', '.env')
load_dotenv(os.path.join(current_dir, '..', '.env'))
CONFIG_PATH = os.path.join(current_dir, "..", "book_config.json")
DB_NAME = "gutenberg_index.db"    
BOOKS_DIR = os.path.join(current_dir, "..", "data", "books")
DEFAULT_LLMS = ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"]

def initialize_session_state():
    """Initializes all required Streamlit session state variables."""
    if "engine_ready" not in st.session_state:
        st.session_state.engine_ready = False
        st.session_state.current_step = "narrative"
        st.session_state.node_id = "intro"
        st.session_state.scene_data = None
        st.session_state.generated_images = []
        st.session_state.smith = None
        st.session_state.book_pitch = None
        st.session_state.selected_protagonist = None