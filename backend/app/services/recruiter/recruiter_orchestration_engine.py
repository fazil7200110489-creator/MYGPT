"""Recruiter Orchestration Engine — End-to-End Execution Pipeline for Recruiter Platform Version 2.

Pipeline Flow:
Recruiter NL Query / Request
       │
       ▼
Recruiter Intent Classifier (Maps request to 1 of 10 Recruiter Intents)
       │
       ▼
Recruiter Query Planner (Extracts QueryPlan: Role, Skills, Location, MinExp, Limit)
       │
       ▼
Job Requirement Builder (Constructs canonical RequirementProfile)
       │
       ▼
Recruiter Session Memory (Tracks conversational state & candidate IDs)
       │
       ▼
Execution Engine (Search / Ranking / Explanation / Comparison / Shortlist / Interview / Export)
       │
       ▼
Formatted Recruiter Response Payload
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.recruiter.recruiter_intent_classifier import RecruiterIntent, recruiter_intent_classifier
from backend.app.services.recruiter.recruiter_query_planner import recruiter_query_planner, QueryPlan
from backend.app.services.recruiter.job_requirement_builder import job_requirement_builder
from backend.app.services.recruiter.recruiter_session_memory import recruiter_session_memory
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store
from backend.app.services.recruiter.multi_candidate_search import multi_candidate_search
from backend.app.services.recruiter.multi_candidate_ranking import multi_candidate_ranking
from backend.app.services.recruiter.candidate_explanation_engine import candidate_explanation_engine
from backend.app.services.recruiter.candidate_comparison_engine import candidate_comparison_engine
from backend.app.services.recruiter.shortlist_management_service import shortlist_management_service
from backend.app.services.recruiter.interview_question_generator import interview_question_generator
from backend.app.services.recruiter.recruiter_report_export_service import recruiter_report_export_service


class RecruiterOrchestrationEngine:
    """Orchestrates end-to-end recruiter operations across Version 2 modules."""

    def process_query(self, raw_query: str, session_id: str = "default_session") -> Dict[str, Any]:
        """Process natural language recruiter query through the V2 pipeline."""
        logger.info(f"RecruiterOrchestrationEngine: Processing query '{raw_query}' (Session: {session_id})")

        # 1. Intent Classification
        intent = recruiter_intent_classifier.classify(raw_query)

        # 2. Query Planning
        query_plan = recruiter_query_planner.plan_query(raw_query, default_intent=intent)

        # 3. Session Context Retrieval & Fallback
        session = recruiter_session_memory.get_session(session_id)
        if not query_plan.target_role and session.get("active_target_role"):
            query_plan.target_role = session.get("active_target_role")
            query_plan.department = session.get("active_department")

        # 4. Job Requirement Building
        req_profile = job_requirement_builder.build_from_plan(query_plan)

        response_payload = {
            "session_id": session_id,
            "raw_query": raw_query,
            "intent": intent.value,
            "query_plan": query_plan.to_dict(),
            "requirement_profile": req_profile.to_dict(),
            "result_type": intent.value,
            "data": {}
        }

        # 5. Intent Routing
        if intent in (RecruiterIntent.CANDIDATE_SEARCH, RecruiterIntent.CANDIDATE_FILTERING):
            search_results = multi_candidate_search.search(query_plan)
            ranked_results = multi_candidate_ranking.rank_candidates(search_results, req_profile)

            cids = [r["candidate_id"] for r in ranked_results]
            recruiter_session_memory.add_turn(
                session_id=session_id,
                raw_query=raw_query,
                intent=intent.value,
                query_plan=query_plan,
                requirement_profile=req_profile,
                candidate_ids=cids,
                ranked_results=ranked_results
            )

            response_payload["data"] = {
                "total_matches": len(ranked_results),
                "ranked_candidates": ranked_results
            }

        elif intent == RecruiterIntent.CANDIDATE_RANKING:
            all_pool = candidate_pool_store.list_all()
            search_results = multi_candidate_search.search(query_plan, pool_override=all_pool)
            ranked_results = multi_candidate_ranking.rank_candidates(search_results, req_profile)

            cids = [r["candidate_id"] for r in ranked_results]
            recruiter_session_memory.add_turn(
                session_id=session_id,
                raw_query=raw_query,
                intent=intent.value,
                query_plan=query_plan,
                requirement_profile=req_profile,
                candidate_ids=cids,
                ranked_results=ranked_results
            )

            response_payload["data"] = {
                "total_ranked": len(ranked_results),
                "ranked_candidates": ranked_results
            }

        elif intent == RecruiterIntent.CANDIDATE_EXPLANATION:
            last_ranked = session.get("last_ranked_results", [])
            if not last_ranked:
                all_pool = candidate_pool_store.list_all()
                last_ranked = multi_candidate_ranking.rank_candidates(all_pool, req_profile)

            target_cand = last_ranked[0] if last_ranked else {}
            explanation = candidate_explanation_engine.explain(target_cand, req_profile)
            response_payload["data"] = explanation

        elif intent == RecruiterIntent.CANDIDATE_COMPARISON:
            last_ranked = session.get("last_ranked_results", [])
            if len(last_ranked) < 2:
                all_pool = candidate_pool_store.list_all()
                last_ranked = multi_candidate_ranking.rank_candidates(all_pool, req_profile)

            comp_result = candidate_comparison_engine.compare(last_ranked[:5], req_profile)
            response_payload["data"] = comp_result

        elif intent == RecruiterIntent.INTERVIEW_QUESTION_GENERATION:
            last_cids = session.get("last_candidate_ids", [])
            cand_rec = None
            if last_cids:
                cand_rec = candidate_pool_store.get_candidate(last_cids[0])
            if not cand_rec:
                all_cands = candidate_pool_store.list_all()
                cand_rec = all_cands[0] if all_cands else {}

            questions = interview_question_generator.generate_questions(cand_rec, req_profile)
            response_payload["data"] = questions

        elif intent == RecruiterIntent.EXPORT:
            last_ranked = session.get("last_ranked_results", []) or candidate_pool_store.list_all()
            csv_data = recruiter_report_export_service.export_to_csv(last_ranked)
            md_pdf_data = recruiter_report_export_service.export_to_markdown_pdf(last_ranked, req_profile.target_role)

            response_payload["data"] = {
                "csv_content": csv_data,
                "markdown_pdf_content": md_pdf_data,
                "exported_candidate_count": len(last_ranked)
            }

        elif intent == RecruiterIntent.ANALYTICS:
            summary = shortlist_management_service.get_pipeline_summary()
            response_payload["data"] = {
                "total_candidates": summary["Total"],
                "pipeline_stages": summary,
                "active_role": req_profile.target_role,
                "department": req_profile.department
            }

        else:
            all_pool = candidate_pool_store.list_all()
            ranked_results = multi_candidate_ranking.rank_candidates(all_pool, req_profile)
            response_payload["data"] = {
                "total_candidates": len(ranked_results),
                "ranked_candidates": ranked_results
            }

        logger.info(f"RecruiterOrchestrationEngine completed processing for '{raw_query}'")
        return response_payload


# Singleton Instance
recruiter_orchestration_engine = RecruiterOrchestrationEngine()
