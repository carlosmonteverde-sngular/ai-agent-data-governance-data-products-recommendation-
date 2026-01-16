import os
import shutil
import sys
from pathlib import Path

def ignore_patterns(path, names):
    return {'.git', '.venv', '__pycache__', 'output', '.DS_Store'}

def main():
    current_dir = Path(os.getcwd()) # Should be .../ai-agent-data-governance-data-quality
    parent_dir = current_dir.parent
    new_dir_name = "ai-agent-data-governance-data-products-recommendations"
    new_dir = parent_dir / new_dir_name

    print(f"Current dir: {current_dir}")
    print(f"Target dir: {new_dir}")

    if new_dir.exists():
        print(f"Target directory {new_dir} already exists.")
        # We don't overwrite to be safe, unless empty?
        # Just warn.
    else:
        print(f"Copying project to {new_dir}...")
        try:
            shutil.copytree(current_dir, new_dir, ignore=ignore_patterns, dirs_exist_ok=True)
            print("Copy completed successfully.")
        except Exception as e:
            print(f"Error copying: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
