"""
Configuration for RAGstar - Repository Discovery System
"""

# List of repositories to index
# Format: {"name": "repo_name", "url": "https://github.com/owner/repo"}
REPOSITORIES = [
    {"name": "awesome-copilot", "url": "https://github.com/github/awesome-copilot"},
    {"name": "LightRAG", "url": "https://github.com/HKUDS/LightRAG"},
    {"name": "the-book-of-secret-knowledge", "url": "https://github.com/trimstray/the-book-of-secret-knowledge"},
    # Add your repos here
]

# Embedding model - trade-off between quality and speed
# Options (better = slower, larger):
# - "all-MiniLM-L6-v2" (384 dims, ~22MB, fastest)
# - "all-mpnet-base-v2" (768 dims, ~90MB, better quality)
# - "bge-large-en-v1.5" (1024 dims, ~340MB, best quality for semantic search)
# For searching across diverse topics, use a larger model for better semantic understanding
EMBEDDING_MODEL = "bge-large-en-v1.5"  # 768 dims, good balance of quality and speed

# Summarization model
# Options for local LLM via Ollama (better quality > speed, since it runs once during build):
# - "facebook/bart-large-cnn" (transformer-based, ~1.6GB, fast but lower quality)
# - "mistral" via Ollama (7B, best quality, ~4GB VRAM needed, ~1 min per repo)
# - "neural-chat" via Ollama (7B optimized, ~4GB VRAM, good balance)
# - "llama2" via Ollama (7B/13B/70B options)
# For best results across diverse repos, use a stronger LLM like mistral
SUMMARIZER_MODEL = "mistral-via-ollama"  # Set to "ollama" to use local LLM, "transformer" for BART

# Ollama configuration (if using local LLM)
OLLAMA_MODEL_NAME = "mistral"  # or "neural-chat", "llama2", etc.
OLLAMA_TIMEOUT = 180  # seconds per summary (mistral ~60-90s)

# ChromaDB settings
CHROMA_DB_PATH = "./ragstar_db"
CHROMA_COLLECTION_NAME = "repositories"
