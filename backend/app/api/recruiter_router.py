"""Recruiter Platform Version 2 API Router — Enterprise REST Endpoints.

Provides APIs for:
- Query processing (/query)
- Candidate Pool Store (/candidates)
- Batch Ingestion (/ingest)
- Workflow Stage Updates (/candidates/{id}/stage)
- Interview Script Generation (/interview)
- Export (/export)
- Dynamic Admin Configuration (/admin/taxonomy, /admin/roles)
"""

from fastapi import APIRouter, HTTPException, Query, Body, File, UploadFile
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from backend.app.services.recruiter.recruiter_orchestration_engine import recruiter_orchestration_engine
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store
from backend.app.services.recruiter.shortlist_management_service import shortlist_management_service
from backend.app.services.recruiter.interview_question_generator import interview_question_generator
from backend.app.services.recruiter.recruiter_report_export_service import recruiter_report_export_service
from backend.app.services.recruiter.recruiter_knowledge_registry import recruiter_knowledge_registry
from backend.app.services.recruiter.job_requirement_builder import job_requirement_builder
from backend.app.services.recruiter.recruiter_query_planner import recruiter_query_planner

router = APIRouter(prefix="/api/v2/recruiter", tags=["Recruiter Platform V2"])


class RecruiterQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language recruiter query")
    session_id: Optional[str] = Field("default_session", description="Conversational session ID")


class BatchIngestRequest(BaseModel):
    candidates: List[Dict[str, Any]] = Field(..., description="List of CandidateProfile objects from V1 ingestion")


class StageUpdateRequest(BaseModel):
    stage: str = Field(..., description="New workflow stage: Shortlisted, Interviewing, On-Hold, Rejected, Unassigned")
    notes: Optional[str] = Field("", description="Recruiter notes")


class RoleConfigRequest(BaseModel):
    department_name: str = Field(..., description="Department name")
    role_name: str = Field(..., description="Role name")
    alternative_titles: Optional[List[str]] = Field([], description="Alternative role titles")
    required_skills: Optional[List[str]] = Field([], description="Required skills")
    preferred_skills: Optional[List[str]] = Field([], description="Preferred skills")
    nice_to_have_skills: Optional[List[str]] = Field([], description="Nice-to-have skills")
    experience_min_years: Optional[float] = Field(0.0, description="Minimum experience required")
    education_requirements: Optional[List[str]] = Field([], description="Required education degrees")
    skill_weight: Optional[float] = Field(4.0, description="Skill weight multiplier")
    role_weight: Optional[float] = Field(2.5, description="Role weight multiplier")


@router.post("/query")
def process_recruiter_query(request: RecruiterQueryRequest):
    """Process natural language recruiter query through Version 2 engine."""
    try:
        res = recruiter_orchestration_engine.process_query(request.query, session_id=request.session_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload_batch")
async def upload_batch_resumes(
    files: List[UploadFile] = File(...)
) -> Dict[str, Any]:
    """Batch upload multiple resumes into CandidatePoolStore for Version 2 Recruiter Platform.

    Pipeline per resume:
    Resume -> Document Parser -> CandidateProfileBuilder -> CandidateProfile -> Candidate Pool Store
    """
    from backend.app.services.ai_orchestrator import ai_orchestrator
    from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder
    from loguru import logger

    results = []
    processed_count = 0
    failed_count = 0

    for file in files:
        try:
            content = await file.read()
            # 1. Document Manager & Parser (Save & parse document text)
            doc_meta, parsed_doc = ai_orchestrator.process_new_document(
                filename=file.filename,
                file_content=content
            )
            raw_text = parsed_doc.get("text", "")

            # 2. CandidateProfileBuilder (Build structured candidate profile)
            candidate_profile = candidate_profile_builder.build_profile(
                raw_entities={},
                raw_text=raw_text
            )

            # 3. Add to CandidatePoolStore
            candidate_id = candidate_pool_store.add_candidate(
                candidate_profile=candidate_profile,
                doc_id=doc_meta["id"],
                filename=file.filename
            )

            processed_count += 1
            results.append({
                "filename": file.filename,
                "doc_id": doc_meta["id"],
                "candidate_id": candidate_id,
                "status": "success"
            })
            logger.info(f"V2 Batch Upload: Successfully processed {file.filename} (Candidate ID: {candidate_id})")

        except Exception as e:
            failed_count += 1
            logger.error(f"V2 Batch Upload: Failed to process resume {file.filename}: {e}")
            results.append({
                "filename": file.filename,
                "status": "failed",
                "error": str(e)
            })

    return {
        "status": "success" if processed_count > 0 else "failed",
        "total_uploaded": len(files),
        "processed_count": processed_count,
        "failed_count": failed_count,
        "results": results
    }


@router.get("/candidates")
def list_candidate_pool(
    domain: Optional[str] = None,
    skill: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None
):
    """List or filter candidate pool."""
    cands = candidate_pool_store.filter_candidates(
        domain=domain,
        skill=skill,
        location=location,
        status=status
    )
    return {
        "count": len(cands),
        "candidates": cands
    }


@router.post("/ingest")
def batch_ingest_candidates(request: BatchIngestRequest):
    """Batch ingest candidate profiles into CandidatePoolStore."""
    added_ids = candidate_pool_store.add_batch_candidates(request.candidates)
    return {
        "status": "success",
        "ingested_count": len(added_ids),
        "candidate_ids": added_ids,
        "total_pool_count": candidate_pool_store.count()
    }


@router.put("/candidates/{candidate_id}/stage")
def update_candidate_stage(candidate_id: str, request: StageUpdateRequest):
    """Update candidate workflow stage."""
    res = shortlist_management_service.update_stage(candidate_id, request.stage, recruiter_notes=request.notes)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/interview")
def generate_interview_questions(candidate_id: str = Query(...), role: Optional[str] = Query(None)):
    """Generate dynamic interview questions script for a candidate."""
    cand = candidate_pool_store.get_candidate(candidate_id)
    if not cand:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    qplan = recruiter_query_planner.plan_query(f"Find {role}" if role else "Find Developer")
    req_profile = job_requirement_builder.build_from_plan(qplan)

    questions = interview_question_generator.generate_questions(cand, req_profile)
    return questions


@router.get("/export")
def export_candidate_report(format_type: str = Query("csv", alias="format")):
    """Export candidate pool to CSV, JSON, or Markdown PDF."""
    cands = candidate_pool_store.list_all()

    if format_type.lower() == "csv":
        data = recruiter_report_export_service.export_to_csv(cands)
        return {"format": "csv", "content": data}
    elif format_type.lower() == "pdf" or format_type.lower() == "markdown":
        data = recruiter_report_export_service.export_to_markdown_pdf(cands)
        return {"format": "pdf_markdown", "content": data}
    else:
        data = recruiter_report_export_service.export_to_json(cands)
        return {"format": "json", "content": data}


@router.get("/admin/taxonomy")
def get_admin_taxonomy():
    """Get complete department and role configuration taxonomy."""
    return {
        "departments": recruiter_knowledge_registry.departments
    }


@router.post("/admin/roles")
def add_or_update_admin_role(request: RoleConfigRequest):
    """Dynamically add or update department role configuration without code changes."""
    r_dict = request.dict()
    dept_name = r_dict.pop("department_name")
    res = recruiter_knowledge_registry.add_or_update_role(dept_name, r_dict)
    if not res:
        raise HTTPException(status_code=400, detail="Failed to add or update role.")
    return {
        "status": "success",
        "updated_role": res
    }
