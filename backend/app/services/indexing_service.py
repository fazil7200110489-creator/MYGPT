"""Indexing Service for chunking, embedding, and saving parsed documents.
"""

from typing import Dict, Any, List
from loguru import logger

from backend.app.services.chunk_service import chunk_service
from backend.app.services.embedding_service import embedding_service
from backend.app.services.storage_service import storage_service
from backend.app.services.document_manager import document_manager


class IndexingService:
    """Handles the document indexing pipeline: chunking -> embedding -> storage."""

    def index_document(self, doc_id: str, parsed_doc: Dict[str, Any], chunk_size: int = 500) -> None:
        """Runs the index generation pipeline on a parsed document.
        
        Args:
            doc_id: Unique document ID.
            parsed_doc: Dictionary returned from DocumentParser.parse.
            chunk_size: Target chunk size.
        """
        logger.info(f"Indexing document: {doc_id}")
        document_manager.update_status(doc_id, "processing")

        try:
            # 1. Semantic Chunking
            chunks = chunk_service.chunk_document(parsed_doc, doc_id, chunk_size=chunk_size)
            if not chunks:
                logger.warning(f"No chunks generated for document {doc_id}.")
                document_manager.update_status(doc_id, "processed")
                storage_service.save_chunks(doc_id, [])
                return

            # 2. Extract chunk texts and generate embeddings
            chunk_texts = [c["text"] for c in chunks]
            embeddings = embedding_service.get_embeddings(chunk_texts)

            # 3. Attach embeddings to chunks
            for idx, embedding in enumerate(embeddings):
                chunks[idx]["embedding"] = embedding

            # 4. Save chunks with embeddings to local storage
            storage_service.save_chunks(doc_id, chunks)

            # 5. Mark document as processed
            document_manager.update_status(doc_id, "processed")
            logger.info(f"Successfully indexed document {doc_id}. {len(chunks)} chunks persisted.")
        except Exception as e:
            logger.error(f"Failed to index document {doc_id}: {e}")
            document_manager.update_status(doc_id, "error", error_message=str(e))
            raise e

    def delete_document_index(self, doc_id: str) -> None:
        """Deletes stored index chunks and embeddings for a document.
        
        Args:
            doc_id: Unique document ID.
        """
        logger.info(f"Deleting document index: {doc_id}")
        storage_service.delete_chunks(doc_id)
        try:
            from backend.app.services.knowledge_service import knowledge_store
            knowledge_store.delete_knowledge(doc_id)
        except Exception as e:
            logger.error(f"Failed to delete knowledge store entry: {e}")


indexing_service = IndexingService()
