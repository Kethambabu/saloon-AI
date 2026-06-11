"""
Embedding Pipeline for SalonAI Workforce RAG System.

Provides a configurable, open-source embedding layer supporting:
    - HuggingFace sentence-transformers (free, local, no API key required)
    - Fully offline and privacy-preserving embeddings

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
import requests
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional

from langchain_core.embeddings import Embeddings

from backend.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Gemini API Embeddings
# ---------------------------------------------------------------------------
class GeminiAPIEmbeddings(Embeddings):
    """LangChain compatible Embeddings class that calls Gemini API directly, bypassing PyTorch."""
    def __init__(self, model_name: str = "models/gemini-embedding-2", api_key: str = None):
        self.model_name = model_name
        self.api_key = api_key or get_settings().gemini_api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set to use GeminiAPIEmbeddings")

    def embed_query(self, text: str) -> List[float]:
        url = f"https://generativelanguage.googleapis.com/v1beta/{self.model_name}:embedContent?key={self.api_key}"
        payload = {
            "model": self.model_name,
            "content": {
                "parts": [{"text": text}]
            }
        }
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            raise ValueError(f"Gemini API returned error: {response.status_code} - {response.text}")
        return response.json()["embedding"]["values"]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        url = f"https://generativelanguage.googleapis.com/v1beta/{self.model_name}:batchEmbedContents?key={self.api_key}"
        
        batch_size = 100
        results = []
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            requests_payload = [
                {
                    "model": self.model_name,
                    "content": {
                        "parts": [{"text": text}]
                    }
                }
                for text in chunk
            ]
            payload = {"requests": requests_payload}
            response = requests.post(url, json=payload)
            if response.status_code != 200:
                raise ValueError(f"Gemini API returned error: {response.status_code} - {response.text}")
            embeddings = response.json().get("embeddings", [])
            for emb in embeddings:
                results.append(emb["values"])
        return results


# ---------------------------------------------------------------------------
# Provider Configuration
# ---------------------------------------------------------------------------
class EmbeddingProvider(str, Enum):
    """Supported embedding model providers."""
    HUGGINGFACE = "huggingface"
    GEMINI = "gemini"


@dataclass
class EmbeddingConfig:
    """Configuration for the embedding pipeline."""
    provider: EmbeddingProvider = EmbeddingProvider.HUGGINGFACE

    # HuggingFace settings (open-source)
    hf_model_name: str = "all-MiniLM-L6-v2"
    hf_device: str = "cpu"
    hf_normalize: bool = True

    # Gemini settings
    gemini_model_name: str = "models/gemini-embedding-2"

    # Batch processing
    batch_size: int = 64
    show_progress: bool = True


# ---------------------------------------------------------------------------
# Model Factory
# ---------------------------------------------------------------------------
def _check_torch_available() -> bool:
    """Pre-flight check: verify PyTorch is installed and importable."""
    try:
        import torch  # noqa: F401
        logger.debug(f"[Embeddings] PyTorch {torch.__version__} is available")
        return True
    except ImportError:
        logger.warning(
            "[Embeddings] PyTorch (torch) is NOT installed. "
            "Install it with: pip install torch --index-url https://download.pytorch.org/whl/cpu"
        )
        return False
    except OSError as e:
        logger.warning(
            f"[Embeddings] PyTorch DLL/shared-library loading failed: {e}. "
            "This often means a corrupted install — try: pip install --force-reinstall torch"
        )
        return False


def get_embedding_model(config: Optional[EmbeddingConfig] = None) -> Embeddings:
    """
    Factory function that returns a configured LangChain Embeddings instance.
    Uses local HuggingFace sentence-transformers (free, offline, open-source)
    with a graceful API-based Gemini fallback if PyTorch is missing or broken.

    Args:
        config: Optional EmbeddingConfig. If None, auto-detects from environment.

    Returns:
        A LangChain-compatible Embeddings instance.
    """
    if config is None:
        config = _auto_detect_config()

    if config.provider == EmbeddingProvider.GEMINI:
        logger.info("[Embeddings] Initializing Gemini API embedding model...")
        return _build_gemini_embeddings(config)

    # Pre-flight: check if PyTorch is available before trying HuggingFace
    if not _check_torch_available():
        logger.warning(
            "[Embeddings] PyTorch unavailable — skipping HuggingFace embeddings. "
            "Falling back to Gemini API embeddings."
        )
        fallback_config = EmbeddingConfig(provider=EmbeddingProvider.GEMINI)
        return _build_gemini_embeddings(fallback_config)

    logger.info(f"[Embeddings] Initializing local HuggingFace embedding model ({config.hf_model_name})...")
    try:
        return _build_huggingface_embeddings(config)
    except Exception as e:
        error_msg = str(e)
        if "torch" in error_msg.lower() or "DLL" in error_msg:
            reason = "PyTorch DLL/import error"
        elif "No module named" in error_msg:
            reason = f"Missing dependency: {error_msg}"
        else:
            reason = f"Initialization error: {error_msg}"
        logger.warning(
            f"[Embeddings] Failed to initialize local HuggingFace embeddings ({reason}). "
            f"Falling back to Gemini API embeddings."
        )
        # Force fallback to Gemini
        fallback_config = EmbeddingConfig(provider=EmbeddingProvider.GEMINI)
        return _build_gemini_embeddings(fallback_config)


def _auto_detect_config() -> EmbeddingConfig:
    """Auto-detect the best embedding provider from environment variables."""
    provider_env = os.getenv("EMBEDDING_PROVIDER", "huggingface").lower()
    if provider_env == "gemini":
        return EmbeddingConfig(provider=EmbeddingProvider.GEMINI)
    return EmbeddingConfig(provider=EmbeddingProvider.HUGGINGFACE)


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


def _build_gemini_embeddings(config: EmbeddingConfig) -> Embeddings:
    """Build API-based Gemini embeddings."""
    return GeminiAPIEmbeddings(model_name=config.gemini_model_name)


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
            "model": self.config.hf_model_name,
            "device": self.config.hf_device,
            "batch_size": self.config.batch_size,
        }
