"""
Clear ChromaDB - Remove all stored repository summaries
"""

import shutil
from pathlib import Path
from config import CHROMA_DB_PATH


def clear_database():
    """
    Delete the entire ChromaDB database to start fresh.
    """
    db_path = Path(CHROMA_DB_PATH)
    
    if not db_path.exists():
        print(f"Database at {CHROMA_DB_PATH} doesn't exist yet.")
        return
    
    try:
        shutil.rmtree(db_path)
        print(f"✓ Cleared database at {CHROMA_DB_PATH}")
        print("  You can now run 'python ingest.py build' to rebuild from scratch.")
    except Exception as e:
        print(f"Error clearing database: {e}")


if __name__ == "__main__":
    clear_database()
