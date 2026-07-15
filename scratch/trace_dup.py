import sys
import os
import json

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.ai_orchestrator import ai_orchestrator
from backend.app.services.conversation_memory import conversation_memory
from backend.app.services.document_manager import document_manager
from backend.app.services.document_parser import document_parser
from backend.app.services.search_service import search_service
from backend.app.services.context_builder import context_builder
from backend.app.services.reasoning_service import reasoning_service
from backend.app.services.answer_formatter import answer_formatter

def test_pipeline():
    session_id = "test_debug_session"
    # Find the document ID of Updated_Resume_Rekha_R (1).pdf
    doc_id = "12eabdb1-5d44-4fe2-800d-5da352fd3182"
    
    question = "what are the projects"
    print(f"=== Running Query: '{question}' for document: {doc_id} ===")
    
    # 1. Search relevant document chunks
    print("\n--- 1. RETRIEVER OUTPUT ---")
    retrieved_chunks = search_service.search(
        query=question,
        doc_id=doc_id,
        top_k=3,
        similarity_threshold=0.0,
    )
    for i, c in enumerate(retrieved_chunks):
        print(f"Chunk {i}: Similarity: {c.get('similarity') or c.get('score')} | Text snippet: {c['text'][:150]}...")
        
    # 2. Infer user intent
    print("\n--- 2. INTENT INFERENCE ---")
    intent = reasoning_service.infer_intent(question)
    print("Inferred Intent:", intent)
    
    # 3. Construct reasoning context block
    print("\n--- 3. CONTEXT BUILDER OUTPUT ---")
    reasoning_context = context_builder.build_context(
        query=question,
        retrieved_chunks=retrieved_chunks,
        intent=intent,
    )
    print("Reasoning Context Length:", len(reasoning_context))
    print("Reasoning Context Content:")
    print(reasoning_context[:500] + "\n...")
    
    # 4. Evaluate using reasoning engine
    print("\n--- 4. REASONING ENGINE OUTPUT ---")
    raw_answer, confidence, knowledge_used = reasoning_service.reason(
        context=reasoning_context,
        question=question,
        retrieved_chunks=retrieved_chunks,
        intent=intent,
        context_summary="",
        doc_id=doc_id,
    )
    print("Raw Answer:", raw_answer)
    print("Confidence:", confidence)
    print("Knowledge Used:", knowledge_used)
    
    # 5. Format final response output
    print("\n--- 5. ANSWER FORMATTER OUTPUT ---")
    formatted_response = answer_formatter.format_response(
        answer=raw_answer,
        confidence=confidence,
        retrieved_chunks=retrieved_chunks,
        intent=intent,
    )
    print("Formatted Answer:")
    print(formatted_response["answer"])

if __name__ == "__main__":
    test_pipeline()
