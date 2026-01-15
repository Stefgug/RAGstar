"""
Configuration for RAGstar - Repository Discovery System
"""

# List of repositories to index
# Format: {"name": "repo_name", "url": "https://github.com/owner/repo"}
REPOSITORIES = [
    {"name": "repo_name_1", "url": "https://github.com/github/awesome-copilot"},
    {"name": "repo_name_2", "url": "https://github.com/HKUDS/LightRAG"},
    {"name": "repo_name_3", "url": "https://github.com/trimstray/the-book-of-secret-knowledge"},
    # Add your 100 repos here
]

# Summarization settings
SUMMARY_MAX_LENGTH = 500  # Maximum length of generated summary
SUMMARY_MIN_LENGTH = 100  # Minimum length of generated summary

# ChromaDB settings
CHROMA_DB_PATH = "./ragstar_db"
CHROMA_COLLECTION_NAME = "repositories"

# Embedding model (lightweight, local, free)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast, ~22MB

# Summarization model (lightweight, local, free)
SUMMARIZER_MODEL = "facebook/bart-large-cnn"  # Good quality, reasonably fast
