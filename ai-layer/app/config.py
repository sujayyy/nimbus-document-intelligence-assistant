from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

APP_DIR = Path(__file__).resolve().parent
AI_LAYER_DIR = APP_DIR.parent


class Settings(BaseSettings):

    # -----------------------------------------------------
    # Application
    # -----------------------------------------------------

    app_name: str = (
        "Document Intelligence AI Layer"
    )

    # -----------------------------------------------------
    # Embeddings
    # -----------------------------------------------------

    embedding_model: str = (
        "sentence-transformers/all-MiniLM-L6-v2"
    )

    # -----------------------------------------------------
    # Chunking
    # -----------------------------------------------------

    chunk_size: int = 512
    chunk_overlap: int = 50

    # -----------------------------------------------------
    # Retrieval
    # -----------------------------------------------------

    # Number of final chunks returned to the generation layer.
    top_k: int = 5

    # Number of FAISS candidates considered before reranking.
    candidate_k: int = 50

    # Kept for compatibility with existing configuration.
    #
    # Retrieval currently uses candidate ranking rather than
    # applying this as a hard similarity cutoff.
    similarity_threshold: float = 0.35

    # -----------------------------------------------------
    # Rank Fusion
    # -----------------------------------------------------

    # Relative contribution of dense FAISS ranking.
    rrf_dense_weight: float = 0.70

    # Relative contribution of CrossEncoder ranking.
    rrf_reranker_weight: float = 0.30

    # Standard RRF constant.
    rrf_k: int = 60

    # -----------------------------------------------------
    # Query-aware retrieval
    # -----------------------------------------------------

    # Additional score contribution for chunks that contain
    # multiple financial metrics requested by the question.
    #
    # This is deliberately small so that query-aware matching
    # improves retrieval without overriding semantic ranking.
    financial_query_weight: float = 0.10

    # Maximum number of chunks returned from one page.
    max_chunks_per_page: int = 2

    # -----------------------------------------------------
    # Reranker
    # -----------------------------------------------------

    reranker_model: str = (
        "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )

    # -----------------------------------------------------
    # LLM
    # -----------------------------------------------------

    anthropic_api_key: str

    llm_model: str = "claude-sonnet-5"
    llm_max_tokens: int = 1024

    # -----------------------------------------------------
    # Paths
    # -----------------------------------------------------

    base_dir: Path = AI_LAYER_DIR

    data_dir: Path = (
        base_dir / "data"
    )

    # uploaded documents can be stored.

    uploads_dir: Path = (
        data_dir / "uploads"
    )

    # document-specific vector indexes are stored.

    indexes_dir: Path = (
        data_dir / "indexes"
    )

    # -----------------------------------------------------
    # Environment configuration
    # -----------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=AI_LAYER_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# ---------------------------------------------------------
# Global settings instance
# ---------------------------------------------------------

settings = Settings()


# ---------------------------------------------------------
# Ensure required directories exist
# ---------------------------------------------------------

settings.uploads_dir.mkdir(
    parents=True,
    exist_ok=True,
)