"""API Router for document management, search, and knowledge chat operations.
"""

import json
import asyncio
import re
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from backend.app.services.document_manager import document_manager
from backend.app.services.indexing_service import indexing_service
from backend.app.services.storage_service import storage_service
from backend.app.services.search_coordinator import search_coordinator
from backend.app.services.ai_orchestrator import ai_orchestrator
from backend.app.services.conversation_memory import conversation_memory

router = APIRouter(tags=["Document Intelligence"])


class ChatRequest(BaseModel):
    session_id: str
    question: str
    doc_id: Optional[str] = None
    stream: bool = False
    top_k: int = 3
    similarity_threshold: float = 0.0


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3
    similarity_threshold: float = 0.0


@router.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    chunk_size: int = Form(default=500),
) -> Dict[str, Any]:
    """Uploads, parses, chunks, embeds, and indexes a file locally in the background."""
    try:
        content = await file.read()
        logger_msg = f"API triggered upload for file {file.filename} with chunk_size={chunk_size}"
        from loguru import logger
        logger.info(logger_msg)
        
        # 1. Sync processing: Save File & Parse/Extract Text
        doc_meta, parsed_doc = ai_orchestrator.process_new_document(
            filename=file.filename,
            file_content=content
        )
        
        # 2. Async processing: Chunk, Embed & Vector Index in background
        background_tasks.add_task(
            ai_orchestrator.index_document_background,
            doc_meta["id"],
            parsed_doc,
            chunk_size
        )
        
        return doc_meta
    except Exception as e:
        from loguru import logger
        logger.exception(f"Document upload API failed: {e}")
        raise HTTPException(status_code=500, detail=f"Document upload failed: {str(e)}")


@router.get("/documents")
async def list_documents() -> List[Dict[str, Any]]:
    """Lists metadata for all uploaded documents."""
    return document_manager.list_documents()


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str) -> Dict[str, Any]:
    """Deletes a document and its stored indexing representation."""
    success = document_manager.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
        
    indexing_service.delete_document_index(doc_id)
    return {"success": True, "message": f"Document {doc_id} deleted successfully."}


@router.get("/document/{doc_id}")
async def get_document_details(doc_id: str) -> Dict[str, Any]:
    """Retrieves document metadata, parsed chunks, and backend-calculated candidate intelligence."""
    meta = document_manager.get_document(doc_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Document not found")
        
    chunks = storage_service.get_chunks(doc_id)
    clean_chunks = [{k: v for k, v in c.items() if k != "embedding"} for c in chunks]

    # Fetch structured knowledge & backend-calculated candidate profile metrics
    from backend.app.services.knowledge_service import knowledge_store
    from backend.app.services.reasoning.specialists.resume_reasoner import ResumeReasoner
    from backend.app.services.reasoning.domain_detector import domain_detector
    from backend.app.services.reasoning.role_inference_engine import role_inference_engine

    knowledge = knowledge_store.get_knowledge(doc_id) or {}
    entities = knowledge.get("entities", {})
    text = "\n".join(c.get("text", "") for c in chunks)

    resume_reasoner = ResumeReasoner()
    resume_reasoner.pre_resolve_entities(entities, [text] if text else [])

    health = resume_reasoner.calculate_resume_health_score(entities)
    insights = resume_reasoner.generate_candidate_insights(entities, text)
    domain = domain_detector.detect_domain(entities, text)
    default_role_match = role_inference_engine.calculate_role_similarity(entities, target_role_query="", domain=domain)

    candidate_profile = {
        "name": entities.get("candidate_name") or entities.get("name") or meta.get("filename"),
        "designation": entities.get("designation") or "Professional",
        "domain": domain,
        "total_experience": entities.get("experience_total") or "Not specified",
        "education": entities.get("education") or [],
        "skills": entities.get("skills") or [],
        "projects": entities.get("projects") or [],
        "certifications": entities.get("certifications") or [],
        "email": entities.get("email"),
        "phone": entities.get("phone"),
        "address": entities.get("address"),
        "linkedin": entities.get("linkedin"),
        "github": entities.get("github"),
        "portfolio": entities.get("portfolio")
    }

    return {
        "metadata": meta,
        "chunks": clean_chunks,
        "knowledge": knowledge,
        "profile": candidate_profile,
        "health_score": health["health_score"],
        "health_checklist": health["checklist"],
        "insights": insights,
        "role_match": default_role_match
    }


@router.post("/document/{doc_id}/search")
async def search_document(doc_id: str, req: SearchRequest) -> List[Dict[str, Any]]:
    """Performs semantic similarity search inside a document's chunks."""
    meta = document_manager.get_document(doc_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return search_coordinator.search(
        query=req.query,
        doc_id=doc_id,
        top_k=req.top_k,
        similarity_threshold=req.similarity_threshold,
    )


@router.post("/chat")
async def post_chat(req: ChatRequest):
    """Chats with active document. Supports JSON response or real-time streaming."""
    try:
        formatted_response = ai_orchestrator.process_chat_query(
            session_id=req.session_id,
            question=req.question,
            doc_id=req.doc_id,
            top_k=req.top_k,
            similarity_threshold=req.similarity_threshold,
        )

        if not req.stream:
            return formatted_response

        # SSE Streaming handler
        async def event_generator():
            answer = formatted_response["answer"]
            # Split by words/whitespace
            tokens = re.findall(r"\S+|\s+", answer)
            for token in tokens:
                yield f"data: {json.dumps({'token': token})}\n\n"
                await asyncio.sleep(0.015)  # simulate token-by-token generation

            # Output final metadata once generation finishes
            meta = {
                "confidence": formatted_response["confidence"],
                "sources": formatted_response["sources"],
                "suggested_questions": formatted_response["suggested_questions"]
            }
            yield f"data: {json.dumps({'metadata': meta})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        from loguru import logger
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/history")
async def get_chat_history(session_id: str = Query(..., description="Dialogue session ID")) -> List[Dict[str, Any]]:
    """Fetches full conversation history logs for a session."""
    return conversation_memory.get_history(session_id)


@router.post("/chat/reset")
async def reset_chat(session_id: str = Form(..., description="Session ID to clear")) -> Dict[str, Any]:
    """Resets dialogue history for a session."""
    conversation_memory.clear_history(session_id)
    return {"success": True, "message": "Conversation history reset successfully."}
