import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from rag.retriever import get_retriever

def main():
    retriever = get_retriever()
    
    # Test queries
    queries = [
        "Tailored Haircut",
        "haircut",
        "Ravi Sharma haircut",
        "Ravi Sharma",
        "Marcus Johnson"
    ]
    
    for q in queries:
        print(f"\n======================================")
        print(f"Query: '{q}'")
        print(f"======================================")
        
        # Search interactions directly
        try:
            results = retriever.interaction_retriever.search(q, k=5)
            print(f"Direct search returned {len(results)} results:")
            for idx, (doc, score) in enumerate(results, 1):
                print(f"  {idx}. [Score: {score:.4f}] {doc.page_content[:100]}... | Metadata: {doc.metadata}")
        except Exception as e:
            print("Direct search failed:", e)
            
        # Search using search_customer_interactions wrapper
        try:
            from rag.retriever import search_customer_interactions
            res_str = search_customer_interactions(q, k=5)
            print(f"Wrapper result: {res_str}")
        except Exception as e:
            print("Wrapper search failed:", e)

if __name__ == "__main__":
    main()
