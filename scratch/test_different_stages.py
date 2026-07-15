import sys
import os
import json
import re

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.document_parser import document_parser
from backend.app.services.chunk_service import chunk_service
from backend.app.services.knowledge_service import knowledge_builder, knowledge_store
from backend.app.services.search_service import search_service
from backend.app.services.context_builder import context_builder
from backend.app.services.reasoning_service import reasoning_service
from backend.app.services.answer_formatter import answer_formatter

# Let's create a temporary document with the test text
test_text = """
AGILAN
Bachelor of Science
Developer
Summary of profile.
Based on the skills.
According to the details.
"""

doc_id = "test_dup_doc"

def trace_stages():
    print("=========================================")
    print("TRACING STAGES FOR DUP ANALYSIS")
    print("=========================================")
    
    # Stage 1: Parser
    parsed_doc = {
        "text": document_parser.normalize_text(document_parser.clean_text(test_text)),
        "pages": [{"page_number": 1, "text": test_text}],
        "file_type": ".txt"
    }
    print("\n[STAGE 1] Parser Output Text:")
    print(repr(parsed_doc["text"]))
    
    # Stage 2: Chunk Builder
    chunks = chunk_service.chunk_document(parsed_doc, doc_id, chunk_size=500)
    print("\n[STAGE 2] Chunk Builder Output Chunks Text:")
    for idx, c in enumerate(chunks):
        print(f" Chunk {idx}: {repr(c['text'])}")
        
    # Stage 3: Knowledge Object Builder (build_knowledge)
    knowledge = knowledge_builder.build_knowledge(
        text=parsed_doc["text"],
        file_type=parsed_doc["file_type"],
        metadata={"chunk_size": 500},
        pages=parsed_doc["pages"]
    )
    print("\n[STAGE 3] Knowledge Builder Output Facts:")
    print(json.dumps(knowledge.get("facts"), indent=2))
    
    # Let's mock the retrieval chunk
    retrieved_chunk = chunks[0].copy()
    retrieved_chunk["score"] = 1.0
    retrieved_chunk["similarity"] = 1.0
    retrieved_chunks = [retrieved_chunk]
    
    # Stage 4: Context Builder
    reasoning_context = context_builder.build_context(
        query="who is agilan",
        retrieved_chunks=retrieved_chunks,
        intent="General"
    )
    print("\n[STAGE 4] Context Builder Output:")
    print(repr(reasoning_context))
    
    # Stage 5: Reasoning Service
    knowledge_store.save_knowledge(doc_id, knowledge)
    raw_answer, confidence, knowledge_used = reasoning_service.reason(
        context=reasoning_context,
        question="give me the summary and experience",
        retrieved_chunks=retrieved_chunks,
        intent="Summary",
        context_summary="",
        doc_id=doc_id
    )
    print("\n[STAGE 5] Reasoning Service Output (Raw Answer):")
    print(repr(raw_answer))
    
    # Stage 6: Answer Formatter
    formatted = answer_formatter.format_response(
        answer=raw_answer,
        confidence=confidence,
        retrieved_chunks=retrieved_chunks,
        intent="Summary"
    )
    print("\n[STAGE 6] Answer Formatter Output:")
    print(repr(formatted["answer"]))

if __name__ == "__main__":
    trace_stages()
