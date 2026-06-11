import os
import sys

# Add backend and root to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend"))
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.abspath(os.path.join(backend_dir, "..")))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from db.database import SessionLocal
from rag.ingest import RAGIngestor
from services.receptionist_rag_service import ReceptionistRAGService

def main():
    logger.info("Initializing manual FAISS index rebuild...")
    db = SessionLocal()
    try:
        # 1. Rebuild interactions index
        logger.info("Rebuilding interactions index...")
        ingestor = RAGIngestor()
        ingestor.ingest_all(force_rebuild=True)
        
        # 2. Rebuild receptionist knowledge index
        logger.info("Rebuilding receptionist knowledge index...")
        rag_service = ReceptionistRAGService()
        rag_service.rebuild_receptionist_knowledge_index(db)
        
        logger.info("✅ FAISS indexes rebuilt successfully with 384-dimensional local embeddings!")
    except Exception as e:
        logger.error(f"❌ Failed to rebuild indexes: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
