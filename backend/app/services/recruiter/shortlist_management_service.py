"""Shortlist Management Service — Candidate Pipeline Stage Tracking.

Workflow Stages:
- Unassigned
- Shortlisted
- Interviewing
- On-Hold
- Rejected
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store, CandidatePoolStore


class ShortlistManagementService:
    """Manages candidate recruitment pipeline stages and notes."""

    def __init__(self, store: Optional[CandidatePoolStore] = None):
        self.store = store or candidate_pool_store

    def update_stage(self, candidate_id: str, new_stage: str, recruiter_notes: str = "") -> Dict[str, Any]:
        """Update candidate workflow stage."""
        valid_stages = ["Unassigned", "Shortlisted", "Interviewing", "On-Hold", "Rejected"]
        matched_stage = next((s for s in valid_stages if s.lower() == new_stage.lower()), None)

        if not matched_stage:
            return {"success": False, "error": f"Invalid stage '{new_stage}'. Valid stages: {valid_stages}"}

        ok = self.store.update_status(candidate_id, matched_stage, notes=recruiter_notes)
        if ok:
            candidate = self.store.get_candidate(candidate_id)
            logger.info(f"ShortlistManagementService: Candidate {candidate_id} moved to '{matched_stage}'")
            return {
                "success": True,
                "candidate_id": candidate_id,
                "candidate_name": candidate.get("name"),
                "new_stage": matched_stage,
                "notes": recruiter_notes
            }
        return {"success": False, "error": f"Candidate ID '{candidate_id}' not found."}

    def get_pipeline_summary(self) -> Dict[str, Any]:
        """Get count of candidates in each stage."""
        all_cands = self.store.list_all()
        summary = {
            "Unassigned": 0,
            "Shortlisted": 0,
            "Interviewing": 0,
            "On-Hold": 0,
            "Rejected": 0,
            "Total": len(all_cands)
        }
        for c in all_cands:
            st = c.get("status", "Unassigned")
            if st in summary:
                summary[st] += 1
            else:
                summary[st] = 1
        return summary

    def list_by_stage(self, stage: str) -> List[Dict[str, Any]]:
        """List all candidates in a given stage."""
        return self.store.filter_candidates(status=stage)


# Singleton Instance
shortlist_management_service = ShortlistManagementService()
