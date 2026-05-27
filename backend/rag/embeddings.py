"""
Embedding Pipeline for SalonAI Workforce RAG System.

Provides a configurable, multi-provider embedding layer supporting:
    - HuggingFace sentence-transformers (free, local, no API key)
    - OpenAI text-embedding-ada-002 / text-embedding-3-small (cloud)
    - Groq-compatible OpenAI embeddings via custom base_url

Architecture:
    EmbeddingProvider (enum)  →  selects provider
    EmbeddingConfig (dataclass)  →  holds configuration
    get_embedding_model()  →  factory that returns a LangChain Embeddings instance
    EmbeddingPipeline  →  high-level class for batch/single text embedding

All embedding models conform to the LangChain `Embeddings` interface,
making them drop-in compatible with FAISS, Chroma, Pinecone, etc.
"""

import os
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.embeddings import Embeddings

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Provider Configuration
# ---------------------------------------------------------------------------
class EmbeddingProvider(str, Enum):
    """Supported embedding model providers."""
    HUGGINGFACE = "huggingface"
    OPENAI = "openai"


@dataclass
class EmbeddingConfig:
    """Configuration for the embedding pipeline."""
    provider: EmbeddingProvider = EmbeddingProvider.HUGGINGFACE

    # HuggingFace settings
    hf_model_name: str = "all-MiniLM-L6-v2"
    hf_device: str = "cpu"
    hf_normalize: bool = True

    # OpenAI settings
    openai_model: str = "text-embedding-3-small"
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None

    # Batch processing
    batch_size: int = 64
    show_progress: bool = True


# ---------------------------------------------------------------------------
# Model Factory
# ---------------------------------------------------------------------------
def get_embedding_model(config: Optional[EmbeddingConfig] = None) -> Embeddings:
    """
    Factory function that returns a configured LangChain Embeddings instance.

    Priority logic (if no explicit config is provided):
        1. If OPENAI_API_KEY is set → use OpenAI embeddings
        2. Otherwise → use free local HuggingFace sentence-transformers

    Args:
        config: Optional EmbeddingConfig. If None, auto-detects from environment.

    Returns:
        A LangChain-compatible Embeddings instance.
    """
    if config is None:
        config = _auto_detect_config()

    logger.info(f"[Embeddings] Initializing {config.provider.value} embedding model...")

    if config.provider == EmbeddingProvider.OPENAI:
        return _build_openai_embeddings(config)
    else:
        return _build_huggingface_embeddings(config)


def _auto_detect_config() -> EmbeddingConfig:
    """Auto-detect the best embedding provider from environment variables."""
    openai_key = os.environ.get("OPENAI_API_KEY")

    if openai_key:
        logger.info("[Embeddings] Auto-detected OpenAI API key → using OpenAI embeddings")
        return EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            openai_api_key=openai_key,
        )

    logger.info("[Embeddings] No cloud API keys found → using local HuggingFace embeddings (free)")
    return EmbeddingConfig(provider=EmbeddingProvider.HUGGINGFACE)


def _build_openai_embeddings(config: EmbeddingConfig) -> Embeddings:
    """Build OpenAI embeddings client."""
    from langchain_openai import OpenAIEmbeddings

    kwargs = {
        "model": config.openai_model,
        "openai_api_key": config.openai_api_key or os.environ.get("OPENAI_API_KEY"),
    }
    if config.openai_base_url:
        kwargs["openai_api_base"] = config.openai_base_url

    model = OpenAIEmbeddings(**kwargs)
    logger.info(f"[Embeddings] OpenAI embeddings ready (model={config.openai_model})")
    return model


def _build_huggingface_embeddings(config: EmbeddingConfig) -> Embeddings:
    """Build local HuggingFace sentence-transformers embeddings."""
    from langchain_huggingface import HuggingFaceEmbeddings

    model = HuggingFaceEmbeddings(
        model_name=config.hf_model_name,
        model_kwargs={"device": config.hf_device},
        encode_kwargs={"normalize_embeddings": config.hf_normalize},
    )
    logger.info(
        f"[Embeddings] HuggingFace embeddings ready "
        f"(model={config.hf_model_name}, device={config.hf_device})"
    )
    return model


# ---------------------------------------------------------------------------
# Embedding Pipeline
# ---------------------------------------------------------------------------
class EmbeddingPipeline:
    """
    High-level embedding pipeline for converting text into dense vectors.

    Supports single-text and batch embedding with configurable providers.
    All outputs are standard Python lists of floats compatible with FAISS indexing.
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or _auto_detect_config()
        self._model: Optional[Embeddings] = None
        logger.info(f"[EmbeddingPipeline] Initialized (provider={self.config.provider.value})")

    @property
    def model(self) -> Embeddings:
        """Lazy-load the embedding model on first access."""
        if self._model is None:
            self._model = get_embedding_model(self.config)
        return self._model

    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string into a dense vector.

        Args:
            text: Input text to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text.")

        logger.debug(f"[EmbeddingPipeline] Embedding single text ({len(text)} chars)")
        return self.model.embed_query(text)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of text strings into dense vectors.

        Args:
            texts: List of input texts to embed.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        # Filter empty strings
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            raise ValueError("All provided texts are empty.")

        logger.info(f"[EmbeddingPipeline] Embedding batch of {len(valid_texts)} texts")
        return self.model.embed_documents(valid_texts)

    def get_embedding_dimension(self) -> int:
        """Get the dimensionality of the embedding vectors."""
        sample = self.embed_text("dimension check")
        return len(sample)

    def get_provider_info(self) -> dict:
        """Return metadata about the current embedding configuration."""
        return {
            "provider": self.config.provider.value,
            "model": (
                self.config.openai_model
                if self.config.provider == EmbeddingProvider.OPENAI
                else self.config.hf_model_name
            ),
            "device": self.config.hf_device if self.config.provider == EmbeddingProvider.HUGGINGFACE else "cloud",
            "batch_size": self.config.batch_size,
        }
