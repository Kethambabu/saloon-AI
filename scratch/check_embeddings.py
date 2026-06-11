import sys, os
# Add project root to PYTHONPATH for module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.rag.embeddings import EmbeddingPipeline

pipeline = EmbeddingPipeline()
info = pipeline.get_provider_info()
print('Provider info:', info)

# Test a single embedding
vec = pipeline.embed_text('test sentence')
print('Embedding dimension:', len(vec))
print('First 5 values:', vec[:5])
