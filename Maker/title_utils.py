import re
import os
from typing import Optional

def normalize_title_for_path(title: str) -> str:
    """
    Convert a project title to a filesystem-safe folder name.
    
    Rules:
    - Convert to lowercase
    - Replace spaces and special characters with underscores
    - Remove characters that are invalid in Windows/Linux file paths
    - Limit length to prevent path issues
    """
    if not title or not title.strip():
        return "untitled_adventure"
    
    # Convert to lowercase and strip whitespace
    normalized = title.lower().strip()
    
    # Replace spaces and common separators with underscores
    normalized = re.sub(r'[ _-]+', '_', normalized)
    
    # Remove invalid filesystem characters
    # Windows: < > : " | ? * and control characters
    # Linux: / (forward slash)
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    normalized = re.sub(invalid_chars, '', normalized)
    
    # Remove multiple consecutive underscores
    normalized = re.sub(r'_+', '_', normalized)
    
    # Remove leading/trailing underscores
    normalized = normalized.strip('_')
    
    # Ensure we have something left
    if not normalized:
        normalized = "untitled_adventure"
    
    # Limit length to prevent path issues (keep under 100 chars)
    if len(normalized) > 100:
        normalized = normalized[:100].rstrip('_')
    return normalized

def get_adventure_folder_name(book_title: str, protagonist_name: str, scene_count: int) -> str:
    """Creates a folder name from book, protagonist, and scene count."""
    b = normalize_title_for_path(book_title)
    p = normalize_title_for_path(protagonist_name)
    return f"{b}_{p}_{scene_count}"

def get_unique_project_path(base_output_dir: str, title: str) -> str:
    """
    Generate a unique project path for a given title.
    
    If a project with the same normalized title already exists,
    append a number to make it unique.
    """
    base_name = normalize_title_for_path(title)
    project_path = os.path.join(base_output_dir, base_name)
    
    # Check if path already exists
    if not os.path.exists(project_path):
        return project_path
    
    # Find a unique name by appending numbers
    counter = 1
    while True:
        unique_name = f"{base_name}_{counter}"
        project_path = os.path.join(base_output_dir, unique_name)
        if not os.path.exists(project_path):
            return project_path
        counter += 1
        # Safety check to prevent infinite loops
        if counter > 999:
            raise Exception(f"Too many projects with title '{title}'")