"""
Unit and Integration Tests for LangChain + FAISS RAG Memory System.
Verifies chunking, static knowledge base ingestion, semantic retrievers,
multi-index fused searches, and AutoGen wrapper tools.
"""

import os
import sys
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.embeddings import EmbeddingConfig, EmbeddingProvider
from rag.ingest import DocumentChunker, RAGIngestor
from rag.retriever import SalonRAGRetriever, search_salon_knowledge, search_all_context


# ---------------------------------------------------------------------------
# Mock Embeddings for completely offline, high-speed testing
# ---------------------------------------------------------------------------
from langchain_core.embeddings import Embeddings

class MockEmbeddings(Embeddings):
    """Mock LangChain Embeddings that returns deterministic zero vectors."""
    def __init__(self):
        super().__init__()
        self.dimension = 384

    def embed_documents(self, texts):
        return [[0.0] * self.dimension for _ in texts]

    def embed_query(self, text):
        return [0.0] * self.dimension

    def __call__(self, text: str):
        return self.embed_query(text)


@pytest.fixture(name="mock_embedding_model")
def fixture_mock_embedding_model():
    """Patches get_embedding_model to return our MockEmbeddings class across all RAG modules."""
    mock_model = MockEmbeddings()
    with patch("rag.embeddings.get_embedding_model", return_value=mock_model), \
         patch("rag.ingest.get_embedding_model", return_value=mock_model), \
         patch("rag.retriever.get_embedding_model", return_value=mock_model):
        yield mock_model


def test_document_chunker():
    """Verifies that DocumentChunker correctly splits large text block with metadata and overlap."""
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
    
    text = (
        "SalonAI is a premium workforce scheduling and receptionist dashboard. "
        "It supports multi-location setups, automated bookings, and beautiful React styles. "
        "This is the third sentence to ensure we hit chunk limits."
    )
    
    metadata = {"category": "test"}
    chunks = chunker.chunk_text(text, metadata=metadata)
    
    assert len(chunks) > 0
    for i, doc in enumerate(chunks):
        assert isinstance(doc, Document)
        assert doc.metadata["category"] == "test"
        assert doc.metadata["chunk_index"] == i
        assert "content_hash" in doc.metadata


def test_rag_ingestion_and_retrieval(mock_embedding_model):
    """Verifies building local FAISS indexes, running retrievers, and fused search results."""
    # Use temporary directory for FAISS files
    with tempfile.TemporaryDirectory() as tmpdir:
        ingestor = RAGIngestor(
            index_dir=tmpdir,
            chunk_size=200,
            chunk_overlap=20
        )

        # 1. Ingest custom receptionist knowledge base
        custom_kb = [
            Document(page_content="Our cancellation policy requires appointments to be cancelled at least 24 hours in advance to avoid a fee.", metadata={"source": "salon_knowledge_base", "type": "policy", "document_type": "cancellation_policy", "title": "Cancellation Policy"}),
        ]
        res = ingestor.ingest_custom_documents(custom_kb, index_name="receptionist_knowledge")
        assert res["success"] is True
        assert res["chunks_indexed"] > 0
        assert os.path.exists(os.path.join(tmpdir, "receptionist_knowledge", "index.faiss"))

        # 2. Ingest custom test documents
        custom_docs = [
            Document(page_content="Marcus Vance is a Senior Stylist at Downtown Elite", metadata={"category": "staff"}),
            Document(page_content="Sarah Jenkins is a Master Esthetician at Downtown Elite", metadata={"category": "staff"}),
        ]
        custom_res = ingestor.ingest_custom_documents(custom_docs, index_name="customer_interactions")
        assert custom_res["success"] is True
        assert os.path.exists(os.path.join(tmpdir, "customer_interactions", "index.faiss"))

        # 3. Retrieve using SalonRAGRetriever
        retriever = SalonRAGRetriever(
            index_dir=tmpdir,
            knowledge_threshold=0.0,    # Set score thresholds to 0.0 to guarantee matches with mock embeddings
            interaction_threshold=0.0
        )

        # Check status
        status = retriever.get_status()
        assert status["knowledge_index"]["exists"] is True
        assert status["interaction_index"]["exists"] is True

        # Test knowledge search
        kb_results = retriever.search_knowledge("cancellation policy", k=2)
        assert len(kb_results) > 0
        assert "content" in kb_results[0]
        assert kb_results[0]["metadata"]["source"] == "salon_knowledge_base"

        # Test interactions search
        int_results = retriever.search_interactions("Marcus", k=2)
        assert len(int_results) > 0
        assert "Marcus Vance" in int_results[0]["content"]

        # Test unified fused search
        fused = retriever.search_all("Downtown salon info", k=3)
        assert len(fused) > 0
        # Ensure we have results merged
        source_indices = [item["source_index"] for item in fused]
        assert "knowledge" in source_indices or "interactions" in source_indices

        # Test formatted agent context
        context_block = retriever.get_context_for_agent("policy", k=2)
        assert "Relevant Context" in context_block
        assert "End of Context" in context_block


@pytest.mark.asyncio
async def test_rag_autogen_agent_tools(mock_embedding_model):
    """Verifies that RAG search tools returned correct payload structures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the active retriever instance directory
        with patch("rag.retriever._DEFAULT_INDEX_DIR", tmpdir), \
             patch("rag.retriever._retriever_instance", None):
            
            # Ingest to temp directory
            ingestor = RAGIngestor(index_dir=tmpdir)
            custom_kb = [
                Document(page_content="Our cancellation policy requires appointments to be cancelled at least 24 hours in advance to avoid a fee.", metadata={"source": "salon_knowledge_base", "type": "policy", "document_type": "cancellation_policy", "title": "Cancellation Policy"}),
            ]
            ingestor.ingest_custom_documents(custom_kb, index_name="receptionist_knowledge")

            # Test knowledge search tool wrapper
            res_str = search_salon_knowledge("What is the cancellation policy?")
            # Parse output string representation of dict
            import ast
            res = ast.literal_eval(res_str)

            assert res["success"] is True
            assert res["total"] > 0
            assert "results" in res
            assert any("cancellation" in item["content"].lower() for item in res["results"])

            # Test all context search tool wrapper
            all_str = search_all_context("pricing")
            all_res = ast.literal_eval(all_str)
            assert all_res["success"] is True
            assert all_res["total"] > 0
