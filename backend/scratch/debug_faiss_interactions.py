import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from rag.embeddings import get_embedding_model
from langchain_community.vectorstores import FAISS

def main():
    embedding_model = get_embedding_model()
    index_path = os.path.join("backend", "data", "faiss_indices", "customer_interactions")
    
    print("Checking if index exists at:", index_path)
    if not os.path.exists(os.path.join(index_path, "index.faiss")):
        print("Index file not found!")
        return
        
    try:
        vectorstore = FAISS.load_local(index_path, embedding_model, allow_dangerous_deserialization=True)
        docs = list(vectorstore.docstore._dict.values())
        print(f"Total documents in customer_interactions: {len(docs)}")
        
        # Print first 5 docs
        for idx, doc in enumerate(docs[:5], 1):
            print(f"\nDocument {idx}:")
            print("Content:", doc.page_content)
            print("Metadata:", doc.metadata)
            
    except Exception as e:
        print("Error loading index:", e)

if __name__ == "__main__":
    main()
