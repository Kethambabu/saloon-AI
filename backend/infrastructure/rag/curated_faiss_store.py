import os
import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

# Project imports
from core.config import get_settings
from infrastructure.rag.embeddings import get_embedding_model

logger = logging.getLogger(__name__)
settings = get_settings()

_DEFAULT_FAISS_DIR = os.path.join(settings.data_dir, "faiss")
_store_lock = threading.Lock()


class CuratedFAISSStore:
    """
    Per-tenant, per-domain FAISS vector store manager.
    Saves and searches memories under backend/data/faiss/<tenant_id>/<domain>/
    """

    def __init__(self, index_dir: Optional[str] = None):
        self.index_dir = index_dir or _DEFAULT_FAISS_DIR
        self.embedding_model = get_embedding_model()

    def get_index_path(self, tenant_id: str, domain: str) -> str:
        """Get directory path for the tenant's domain index."""
        # Sanitize inputs
        clean_tenant = "".join(c for c in tenant_id if c.isalnum() or c in ("-", "_")).lower()
        clean_domain = "".join(c for c in domain if c.isalnum() or c in ("-", "_")).lower()
        return os.path.join(self.index_dir, clean_tenant, clean_domain)

    def upsert(self, memory_id: str, text: str, metadata: Dict[str, Any]) -> None:
        """
        Add or update a memory vector in the tenant/domain FAISS index.
        Thread-safe write.
        """
        tenant_id = metadata.get("tenant_id", "default")
        scope = metadata.get("scope", "customer")
        index_path = self.get_index_path(tenant_id, scope)
        os.makedirs(index_path, exist_ok=True)

        doc = Document(
            page_content=text,
            metadata={
                "memory_id": str(memory_id),
                "tenant_id": str(tenant_id),
                "scope": str(scope),
                "owner_id": str(metadata.get("owner_id", "")),
                "importance": float(metadata.get("importance", 0.5)),
                "confidence": float(metadata.get("confidence", 1.0)),
                "consent_class": str(metadata.get("consent_class", "standard")),
                "expires_at": metadata.get("expires_at").isoformat() if hasattr(metadata.get("expires_at"), "isoformat") else metadata.get("expires_at")
            }
        )

        with _store_lock:
            vectorstore = None
            if os.path.exists(os.path.join(index_path, "index.faiss")):
                try:
                    vectorstore = FAISS.load_local(
                        index_path,
                        self.embedding_model,
                        allow_dangerous_deserialization=True
                    )
                    # Deduplicate: delete old version if it exists
                    docstore_id_to_delete = None
                    for doc_id, existing_doc in vectorstore.docstore._dict.items():
                        if existing_doc.metadata.get("memory_id") == str(memory_id):
                            docstore_id_to_delete = doc_id
                            break
                    if docstore_id_to_delete:
                        vectorstore.delete([docstore_id_to_delete])
                        logger.info(f"[CuratedFAISSStore] Removed old vector for memory {memory_id} before upsert")
                except Exception as e:
                    logger.warning(f"[CuratedFAISSStore] Failed to load existing index at {index_path}: {e}. Creating new index.")

            if vectorstore is None:
                vectorstore = FAISS.from_documents([doc], self.embedding_model)
            else:
                vectorstore.add_documents([doc])

            vectorstore.save_local(index_path)
            logger.info(f"[CuratedFAISSStore] Saved memory vector {memory_id} to {index_path}")

    def delete(self, memory_id: str, tenant_id: str, scope: str) -> None:
        """
        Delete a memory vector from the tenant/domain FAISS index.
        Thread-safe write.
        """
        index_path = self.get_index_path(tenant_id, scope)
        if not os.path.exists(os.path.join(index_path, "index.faiss")):
            return

        with _store_lock:
            try:
                vectorstore = FAISS.load_local(
                    index_path,
                    self.embedding_model,
                    allow_dangerous_deserialization=True
                )
                docstore_id_to_delete = None
                for doc_id, existing_doc in vectorstore.docstore._dict.items():
                    if existing_doc.metadata.get("memory_id") == str(memory_id):
                        docstore_id_to_delete = doc_id
                        break
                if docstore_id_to_delete:
                    vectorstore.delete([docstore_id_to_delete])
                    vectorstore.save_local(index_path)
                    logger.info(f"[CuratedFAISSStore] Deleted memory vector {memory_id} from {index_path}")
            except Exception as e:
                logger.error(f"[CuratedFAISSStore] Failed to delete memory vector {memory_id} from {index_path}: {e}")

    def search(
        self,
        query: str,
        tenant_id: str,
        domain: str,
        k: int = 5,
        relevance_threshold: float = 0.25
    ) -> List[Dict[str, Any]]:
        """
        Search tenant/domain index. Enforces tenant isolation.
        """
        index_path = self.get_index_path(tenant_id, domain)
        if not os.path.exists(os.path.join(index_path, "index.faiss")):
            logger.info(f"[CuratedFAISSStore] Index does not exist at {index_path}")
            return []

        try:
            # Dangerous deserialization allowed since these are local indices we manage
            vectorstore = FAISS.load_local(
                index_path,
                self.embedding_model,
                allow_dangerous_deserialization=True
            )
            raw_results = vectorstore.similarity_search_with_relevance_scores(query, k=k * 2)

            filtered = []
            for doc, score in raw_results:
                if score < relevance_threshold:
                    continue

                # Ensure tenant isolation and check metadata matches
                doc_tenant_id = doc.metadata.get("tenant_id", "default")
                if doc_tenant_id != tenant_id:
                    logger.warning(f"[CuratedFAISSStore] Tenant mismatch in search results! Expected {tenant_id}, got {doc_tenant_id}")
                    continue

                # Parse expiry date
                expires_at_str = doc.metadata.get("expires_at")
                if expires_at_str:
                    try:
                        # Handle timezone-aware or naive iso format
                        expires_at = datetime.fromisoformat(expires_at_str)
                        if expires_at.tzinfo is None:
                            now = datetime.now()
                        else:
                            now = datetime.now(timezone.utc)
                        if expires_at < now:
                            logger.info(f"[CuratedFAISSStore] Memory {doc.metadata.get('memory_id')} expired at {expires_at_str}")
                            continue
                    except ValueError:
                        pass

                filtered.append({
                    "memory_id": doc.metadata.get("memory_id"),
                    "content": doc.page_content,
                    "score": float(score),
                    "metadata": doc.metadata
                })

            filtered.sort(key=lambda x: x["score"], reverse=True)
            return filtered[:k]
        except Exception as e:
            logger.error(f"[CuratedFAISSStore] Search failed for {index_path}: {e}", exc_info=True)
            return []
