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


def test_inksmith_writes_canonical_asset_names(tmp_path, monkeypatch):
    """Verify InkSmith writes canonical image/audio filenames and outcome markers."""
    from Maker.ink_smith import InkSmith

    # Use a temporary book id so we don't touch real output
    book_id = "test_book_assets"
    smith = InkSmith(book_id)
    # Ensure tests are independent of the repo-wide `book_config.json`
    smith.images_per_scene = 1

    # Ensure fresh file
    if os.path.exists(smith.ink_path):
        os.remove(smith.ink_path)

    # Prepare scene data
    intro_scene = {
        'scene_id': 'intro',
        'scene_text': 'Welcome to the test adventure.',
        'choices': [
            {'text': 'Start', 'type': 'exquisite', 'outcome_text': 'A reward awaits.'},
            {'text': 'Look back', 'type': 'bad', 'outcome_text': 'You fail.'}
        ]
    }

    # Write intro with audio
    smith.write_intro(intro_scene, next_slug='intro_next', audio_file='intro.mp3', audio_prompt='soft wind')

    # Write a main node with audio and choices (one exquisite, one bad)
    choices = [
        {'text': 'Be kind', 'type': 'exquisite', 'outcome_text': 'A reward awaits.'},
        {'text': 'Be cruel', 'type': 'bad', 'outcome_text': 'You fail.'}
    ]
    smith.write_main_node_start('scene_1', 'Scene one text.', 'scene_1_main', choices, next_slug='scene_1_next', audio_file='scene_1.mp3')
    smith.write_choice_outcomes('scene_1', choices, 'scene_1_next')

    # Read the resulting .ink
    assert os.path.exists(smith.ink_path), "adventure.ink was not created by InkSmith"
    with open(smith.ink_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Assertions for canonical names
    assert '# IMAGE: intro_main.png' in content
    assert '# AUDIO: intro.mp3' in content
    assert '# IMAGE: scene_1_main.png' in content
    assert '# AUDIO: scene_1.mp3' in content
    # Reward image should be scene-level canonical name
    assert '# IMAGE: scene_1_reward.png' in content
    # Intro should contain the generated choices (not a single "Begin Adventure" link)
    assert '* [Start] -> intro_result_1' in content
    assert '* [Look back] -> intro_result_2' in content
    assert 'Begin Adventure' not in content

    # Outcome markers are stored as Ink tags (hidden from the player)
    assert '# good' in content
    assert '# bad' in content

    # Audio prompts should NOT be persisted into the .ink file
    assert 'AUDIO_PROMPT' not in content

    # The intro knot no longer contains a runtime assignment; header VAR remains
    assert '~ last_node = "intro"' not in content
    assert 'VAR last_node = "intro"' in content

    # Cleanup generated test files
    try:
        os.remove(smith.ink_path)
        assets_dir = os.path.join(os.path.dirname(smith.ink_path), 'assets')
        if os.path.exists(assets_dir):
            for f in os.listdir(assets_dir):
                os.remove(os.path.join(assets_dir, f))
            os.rmdir(assets_dir)
        book_dir = os.path.dirname(smith.ink_path)
        if os.path.exists(book_dir) and not os.listdir(book_dir):
            os.rmdir(book_dir)
    except Exception:
        pass


def test_soundweaver_does_not_write_meta_json(tmp_path, monkeypatch):
    """Sound generation should only write the .mp3 file and not persist any .meta.json on disk."""
    from Maker.sound_weaver import SoundWeaver

    # Prepare a temporary audio directory and force SoundWeaver to use it
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    monkeypatch.setattr('Maker.sound_weaver._ensure_audio_dir', lambda project_id: str(audio_dir))

    sw = SoundWeaver(api_key=None)
    out = sw.generate_candidates('test_project', 'scene_intro', 'A soft wind', count=1, length_seconds=1, dry_run=True)

    # Confirm an mp3 was written
    files = list(audio_dir.iterdir())
    mp3s = [p for p in files if p.suffix == '.mp3']
    assert mp3s, 'mp3 file was not created'

    # Ensure no .meta.json files are left on disk
    meta_files = [p for p in files if p.name.endswith('.meta.json')]
    assert not meta_files, f"Found unexpected .meta.json files: {meta_files}"


def test_visual_weaver_handles_zero_count(monkeypatch):
    """VisualWeaver.generate_batch should safely handle count=0 and not call generate_image."""
    from Maker.visual_weaver import VisualWeaver

    vw = VisualWeaver()
    # Replace generate_image with a mock that would fail if called
    called = {'was_called': False}
    def fail_if_called(prompt, filename):
        called['was_called'] = True
        raise AssertionError("generate_image should NOT be called when count=0")

    monkeypatch.setattr(vw, 'generate_image', fail_if_called)

    res = vw.generate_batch(prompt="noop", base_filename="test_zero", count=0)
    assert res == [], "Expected empty list when count=0"
    assert not called['was_called'], "generate_image was unexpectedly called"


def test_inksmith_omits_image_tags_when_images_disabled(tmp_path):
    """When images_per_scene == 0 InkSmith must NOT write any IMAGE tags into adventure.ink."""
    from Maker.ink_smith import InkSmith

    book_id = "test_no_images"
    smith = InkSmith(book_id)

    # Ensure fresh file
    if os.path.exists(smith.ink_path):
        os.remove(smith.ink_path)

    # Force images disabled regardless of book_config.json
    smith.images_per_scene = 0

    intro_scene = {
        'scene_id': 'intro',
        'scene_text': 'No images here.',
        'choices': [
            {'text': 'Go', 'type': 'exquisite', 'outcome_text': 'You get nothing.'},
        ]
    }

    smith.write_intro(intro_scene, next_slug='intro_next')

    choices = [
        {'text': 'Go', 'type': 'exquisite', 'outcome_text': 'You get nothing.'},
        {'text': 'Back', 'type': 'bad', 'outcome_text': 'Return.'}
    ]
    smith.write_main_node_start('scene_1', 'Text without images.', 'scene_1_main', choices, next_slug='scene_1_next')
    smith.write_choice_outcomes('scene_1', choices, 'scene_1_next')

    assert os.path.exists(smith.ink_path), "adventure.ink was not created"
    with open(smith.ink_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # No IMAGE tags anywhere
    assert '# IMAGE:' not in content
    # Outcome tags and choices should still exist
    assert '* [Go] -> scene_1_result_1' in content
    assert '# good' in content

    # Cleanup generated test files
    try:
        os.remove(smith.ink_path)
        assets_dir = os.path.join(os.path.dirname(smith.ink_path), 'assets')
        if os.path.exists(assets_dir):
            for f in os.listdir(assets_dir):
                os.remove(os.path.join(assets_dir, f))
            os.rmdir(assets_dir)
        book_dir = os.path.dirname(smith.ink_path)
        if os.path.exists(book_dir) and not os.listdir(book_dir):
            os.rmdir(book_dir)
    except Exception:
        pass

if __name__ == "__main__":
    test_resume_initialization()
