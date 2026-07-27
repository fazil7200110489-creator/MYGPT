"""AI Orchestrator coordinating all local platform services for upload and QA.
"""

import time
from typing import Dict, Any, List, Optional
from loguru import logger

from backend.app.services.document_manager import document_manager
from backend.app.services.document_parser import document_parser
from backend.app.services.search_service import search_service
from backend.app.services.context_builder import context_builder
from backend.app.services.reasoning_service import reasoning_service
from backend.app.services.answer_formatter import answer_formatter
from backend.app.services.conversation_memory import conversation_memory
from backend.app.services.chunk_service import chunk_service
from backend.app.services.embedding_service import embedding_service


class AIOrchestrator:
    """Central controller coordinating knowledge ingestion and retrieval question workflows."""

    def __init__(self) -> None:
        logger.info("Initializing AIOrchestrator with v3 extensibility slots.")
        # Future training / fine-tuning slots
        self.lora_adapters: Dict[str, Any] = {}
        self.training_callbacks: List[Any] = []
        
        # Multimodal inputs / voice slots
        self.voice_encoders: Dict[str, Any] = {}
        self.image_understanding_hooks: List[Any] = []
        self.video_understanding_hooks: List[Any] = []
        
        # Extensions, plugins, and agentic AI slots
        self.plugins: Dict[str, Any] = {}
        self.agent_decision_loops: List[Any] = []
        self.search_engines: List[Any] = []

    def process_new_document(self, filename: str, file_content: bytes) -> tuple[Dict[str, Any], Any]:
        """Saves the file and extracts text synchronously."""
        logger.info("UPLOAD START")
        t_start = time.time()
        
        # 1. Save file to disk
        doc_meta = document_manager.upload_document(filename, file_content)
        doc_id = doc_meta["id"]
        logger.info("UPLOAD END")
        
        # 2. Update status to extracting and run parsing
        document_manager.update_status(doc_id, "extracting")
        logger.info("PARSING START")
        try:
            parsed_doc = document_parser.parse(doc_meta["file_path"])
            logger.info("PARSING END")
            
            # Log detailed metrics
            text = parsed_doc.get("text", "")
            words = text.split()
            elapsed_ms = (time.time() - t_start) * 1000
            
            logger.info("=" * 40)
            logger.info("INGESTION DEBUG METRICS")
            logger.info("=" * 40)
            logger.info(f"DOCUMENT TYPE: {parsed_doc.get('file_type', '').upper()}")
            logger.info(f"Extracted Characters: {len(text)}")
            logger.info(f"Extracted Words: {len(words)}")
            logger.info("Validation Passed: YES")
            logger.info(f"Execution Time: {elapsed_ms:.2f} ms")
            logger.info("=" * 40)
            
            # Fetch updated metadata
            updated_meta = document_manager.get_document(doc_id)
            return updated_meta or doc_meta, parsed_doc
        except Exception as e:
            logger.error(f"Failed to parse document {doc_id}: {e}")
            logger.info("Validation Passed: NO")
            document_manager.update_status(doc_id, "error", error_message=str(e))
            raise e

    def index_document_background(self, doc_id: str, parsed_doc: Dict[str, Any], chunk_size: int = 500) -> None:
        """Runs the remaining chunking, embedding generation, and vector index persistence in a background worker thread."""
        t_total_start = time.time()
        
        meta = document_manager.get_document(doc_id)
        fname = meta["filename"] if meta else doc_id
        
        try:
            # 1. Chunking
            document_manager.update_status(doc_id, "chunking")
            logger.info("CHUNKING START")
            chunks = chunk_service.chunk_document(parsed_doc, doc_id, chunk_size=chunk_size)
            logger.info(f"CHUNK COUNT: {len(chunks)}")
            
            if not chunks:
                logger.warning(f"No chunks generated for document {doc_id}.")
                document_manager.update_status(doc_id, "processed")
                from backend.app.services.storage_service import storage_service
                storage_service.save_chunks(doc_id, [])
                return
            
            # 1.5 Document Understanding Engine & Knowledge Builder
            document_manager.update_status(doc_id, "understanding")
            logger.info("DOCUMENT UNDERSTANDING START")
            from backend.app.services.knowledge_service import knowledge_builder, knowledge_store
            knowledge = knowledge_builder.build_knowledge(
                text=parsed_doc.get("text", ""),
                file_type=parsed_doc.get("file_type", ""),
                metadata={
                    "chunk_size": chunk_size
                },
                pages=parsed_doc.get("pages", [])
            )
            knowledge_store.save_knowledge(doc_id, knowledge)
            logger.info("DOCUMENT UNDERSTANDING END")
            logger.info("Knowledge Built: YES")
            logger.info(f"DEBUG STAGE: {fname} - Knowledge Saved ✓")
            
            # 2. Embedding Generation
            document_manager.update_status(doc_id, "embedding")
            logger.info("EMBEDDING START")
            chunk_texts = [c["text"] for c in chunks]
            embeddings = embedding_service.get_embeddings(chunk_texts)
            logger.info("EMBEDDING END")
            
            # 3. Vector indexing & db storage
            document_manager.update_status(doc_id, "indexing")
            logger.info("INDEXING START")
            for idx, emb in enumerate(embeddings):
                chunks[idx]["embedding"] = emb
            from backend.app.services.storage_service import storage_service
            storage_service.save_chunks(doc_id, chunks)
            logger.info("INDEXING END")
            logger.info(f"Indexed Chunks: {len(chunks)}")
            
            # 4. Ingestion complete
            document_manager.update_status(doc_id, "processed")
            logger.info(f"DEBUG STAGE: {fname} - Frontend Status Updated ✓")
            t_total = time.time() - t_total_start
            logger.info(f"TOTAL LATENCY: {t_total*1000:.2f} ms")
            
        except Exception as e:
            logger.exception(f"Background ingestion pipeline failed for document {doc_id}: {e}")
            document_manager.update_status(doc_id, "error", error_message=str(e))

    def process_chat_query(
        self,
        session_id: str,
        question: str,
        doc_id: Optional[str] = None,
        top_k: int = 3,
        similarity_threshold: float = 0.0,
    ) -> Dict[str, Any]:
        """Orchestrates QA pipeline: memory, retrieval search, context building, model reasoning."""
        # Future training / LoRA callbacks or plugin hook slots
        for plugin in self.plugins.values():
            if hasattr(plugin, "on_before_retrieve"):
                question = plugin.on_before_retrieve(question)

        # 1. Update session active document state
        conversation_memory.set_active_document(session_id, doc_id)

        # Get context summary for follow-up coherence
        context_summary = conversation_memory.get_context_summary(session_id)

        # Auto-restore doc_id from conversation memory on follow-up questions for single resume analysis
        if not doc_id:
            stored_doc_id = conversation_memory.get_active_document(session_id)
            if stored_doc_id:
                doc_id = stored_doc_id

        # 2.5 Infer user intent first so search can prioritize sections based on it
        intent = reasoning_service.infer_intent(question)

        # 2. Search relevant document chunks locally (hybrid: keyword + semantic)
        retrieved_chunks = search_service.search(
            query=question,
            doc_id=doc_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            context_summary=context_summary,
            intent=intent,
        )

        # 3. Construct reasoning context block (de-duplicate & rank)
        logger.info("CONTEXT BUILD")
        reasoning_context = context_builder.build_context(
            query=question,
            retrieved_chunks=retrieved_chunks,
            intent=intent,
        )

        # 4. Evaluate using reasoning engine
        raw_answer, confidence, knowledge_used = reasoning_service.reason(
            context=reasoning_context,
            question=question,
            retrieved_chunks=retrieved_chunks,
            intent=intent,
            context_summary=context_summary,
            doc_id=doc_id,
            session_id=session_id,
        )

        # 5. Format final response output
        formatted_response = answer_formatter.format_response(
            answer=raw_answer,
            confidence=confidence,
            retrieved_chunks=retrieved_chunks,
            intent=intent,
        )

        # Record turns in memory
        conversation_memory.add_message(session_id, "user", question)
        conversation_memory.add_message(session_id, "assistant", formatted_response["answer"], metadata={
            "sources": formatted_response["sources"],
            "confidence": formatted_response["confidence"],
            "suggested_questions": formatted_response["suggested_questions"]
        })

        # 6. Save training sample if successful QA turn
        if doc_id and formatted_response.get("confidence", 0.0) > 0.0:
            try:
                from backend.app.services.trainer_service import trainer_service
                # Strip sources block from the answer text to keep the training target clean
                import re
                clean_answer = re.sub(r"\n\n\*\*Sources:\*\*.*$", "", formatted_response["answer"], flags=re.DOTALL).strip()
                trainer_service.save_training_sample(
                    doc_id=doc_id,
                    question=question,
                    answer=clean_answer,
                    confidence=formatted_response["confidence"],
                    retrieved_context=reasoning_context,
                    intent=intent,
                    knowledge_used=knowledge_used,
                    supporting_chunks=retrieved_chunks,
                )
            except Exception as e:
                logger.error(f"Error calling save_training_sample: {e}")

        return formatted_response


ai_orchestrator = AIOrchestrator()
