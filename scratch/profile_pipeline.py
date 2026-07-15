"""Profiling script to trace and measure ingestion pipeline execution time stage-by-stage.
"""

import os
import sys
import time

# Add root folder to sys path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from backend.app.services.document_parser import document_parser
from backend.app.services.chunk_service import chunk_service
from backend.app.services.embedding_service import embedding_service
from backend.app.services.storage_service import storage_service
from backend.app.services.indexing_service import indexing_service
from backend.app.services.document_manager import document_manager


def run_profile():
    print("=========================================")
    print("INGESTION PIPELINE PROFILE & DIAGNOSTICS")
    print("=========================================")

    # 1. Create a dummy test file
    scratch_dir = os.path.join(base_dir, "scratch", "profile_temp")
    os.makedirs(scratch_dir, exist_ok=True)
    filepath = os.path.join(scratch_dir, "profile_doc.txt")
    
    # Create ~10kb of text (approx. 4 pages of text)
    dummy_text = "The quick brown fox jumps over the lazy dog. Local AI inference is private and secure.\n\n" * 120
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(dummy_text)

    # Stage-by-stage timing
    try:
        t0 = time.time()
        
        # 1. Upload/Register File
        t_upload_start = time.time()
        doc_meta = document_manager.upload_document("profile_doc.txt", dummy_text.encode("utf-8"))
        doc_id = doc_meta["id"]
        t_upload = time.time() - t_upload_start
        print(f"[UPLOAD] Saved document to local disk: {t_upload*1000:.2f} ms")

        # 2. Document Parsing
        t_parse_start = time.time()
        parsed_doc = document_parser.parse(doc_meta["file_path"])
        t_parse = time.time() - t_parse_start
        print(f"[PARSER] Extracted and normalized text: {t_parse*1000:.2f} ms")

        # 3. Semantic Chunking
        t_chunk_start = time.time()
        chunks = chunk_service.chunk_document(parsed_doc, doc_id, chunk_size=500)
        t_chunk = time.time() - t_chunk_start
        print(f"[CHUNK] Generated {len(chunks)} chunks: {t_chunk*1000:.2f} ms")

        # 4. Model Pre-load Check
        t_preload_start = time.time()
        from backend.app.services.model_manager import model_manager as mm
        model = mm.load_model()
        t_preload = time.time() - t_preload_start
        print(f"[MODEL] Checked/Loaded model weights: {t_preload*1000:.2f} ms")

        # 5. Embedding Generation
        t_embed_start = time.time()
        chunk_texts = [c["text"] for c in chunks]
        embeddings = embedding_service.get_embeddings(chunk_texts)
        t_embed = time.time() - t_embed_start
        print(f"[EMBEDDING] Generated embedding vectors: {t_embed*1000:.2f} ms")

        # 6. Indexing & Storage
        t_store_start = time.time()
        for idx, emb in enumerate(embeddings):
            chunks[idx]["embedding"] = emb
        storage_service.save_chunks(doc_id, chunks)
        t_store = time.time() - t_store_start
        print(f"[INDEX] Saved chunks and vector indexes: {t_store*1000:.2f} ms")

        total_time = time.time() - t0
        print(f"\n[TOTAL] Ingestion process finished: {total_time*1000:.2f} ms")

        # Clean up
        document_manager.delete_document(doc_id)
        storage_service.delete_chunks(doc_id)

    finally:
        if os.path.exists(scratch_dir):
            import shutil
            shutil.rmtree(scratch_dir)


if __name__ == "__main__":
    run_profile()
