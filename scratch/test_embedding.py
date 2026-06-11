from sentence_transformers import SentenceTransformer
import sys

try:
    model = SentenceTransformer('all-MiniLM-L6-v2')
    vec = model.encode('test sentence')
    print('Embedding dimension:', len(vec))
    print('First few values:', vec[:5])
except Exception as e:
    print('Error loading model:', e, file=sys.stderr)
    sys.exit(1)
