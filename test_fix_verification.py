import os
import sys
from unittest.mock import MagicMock, patch

# Add the project root to sys.path to allow importing Maker modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_root)

# Mocking the google.genai and other dependencies before importing AutonomousArchitect
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()
sys.modules['google.genai.types'] = MagicMock()

from Maker.architect import AutonomousArchitect

def test_resume_initialization():
    print("Testing AutonomousArchitect.resume_session initialization...")
    
    # Mock book path and config
    book_path = "mock_book.txt"
    with open(book_path, "w") as f: f.write("Once upon a time...")
    
    mock_config = {
        "book_id": "test_book",
        "llm_model": "test-model"
    }
    
    with patch("Maker.architect.genai.Client"), \
         patch("Maker.architect.load_dotenv"), \
         patch("builtins.open", MagicMock(side_effect=[
             MagicMock(read=lambda: '{"book_id": "test_book", "llm_model": "test-model"}'), # config load
             MagicMock(read=lambda: 'Once upon a time...') # book load
         ])):
        
        # Initialize architect
        # We need to bypass the actual book_config.json load in __init__
        with patch("json.load", return_value=mock_config):
            architect = AutonomousArchitect(book_path)
        
        # Manually mock things that would be created by GenAI
        architect.client = MagicMock()
        architect.client.caches.create.return_value = MagicMock(name="mock-cache-name")
        architect.client.chats.create.return_value = MagicMock()
        
        # Test resume_session
        print("Calling resume_session...")
        try:
            # Setting self.chat to None explicitly to test initialization
            architect.chat = None
            architect.cache = None
            
            # This should NOT fail with NoneType error now because it calls _ensure_chat_ready
            ink_summary = "test summary"
            architect.resume_session(ink_summary)
            
            # Verify that _ensure_chat_ready was effectively called (chat and cache are created)
            assert architect.client.caches.create.called, "Cache creation was not called!"
            assert architect.client.chats.create.called, "Chat creation was not called!"
            assert architect.chat.send_message.called, "send_message was not called!"
            
            print("✅ Verification SUCCESS: resume_session correctly initializes the chat session.")
            
        except Exception as e:
            print(f"❌ Verification FAILED: {e}")
            sys.exit(1)
    
    # Cleanup
    if os.path.exists(book_path): os.remove(book_path)

if __name__ == "__main__":
    test_resume_initialization()
