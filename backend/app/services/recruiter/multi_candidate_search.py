"""Multi-Candidate Search Engine — Attribute and Semantic Filtering Service.

Filters candidate pool by QueryPlan specifications:
- Skills overlap
- Location (city, state, country)
- Experience thresholds
- Education degrees
- Candidate name search
- Result limits
"""

import re
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store, CandidatePoolStore
from backend.app.services.recruiter.recruiter_query_planner import QueryPlan


class MultiCandidateSearch:
    """Executes multi-attribute candidate retrieval over candidate pool."""

    def __init__(self, store: Optional[CandidatePoolStore] = None):
        self.store = store or candidate_pool_store

    def search(self, query_plan: QueryPlan, pool_override: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Search and filter candidate pool using QueryPlan."""
        candidates = pool_override if pool_override is not None else self.store.list_all()
        if not candidates:
            logger.warning("MultiCandidateSearch: Candidate pool is empty.")
            return []

        filtered = []

        for candidate in candidates:
            profile = candidate.get("candidate_profile") or candidate
            name = (candidate.get("name") or profile.get("name", "")).lower()

            loc_parts = [
                str(candidate.get("current_location") or ""),
                str(profile.get("current_location") or ""),
                str(profile.get("address") or ""),
                str(profile.get("permanent_address") or ""),
                str(profile.get("address_details", {}).get("formatted_address") or ""),
                str(profile.get("address_details", {}).get("city") or ""),
                str(profile.get("address_details", {}).get("state") or "")
            ]
            location = " ".join(loc_parts).lower()
            total_exp_str = str(candidate.get("total_experience") or profile.get("total_experience", "0"))
            skills = [str(s).lower() for s in (candidate.get("skills") or profile.get("skills") or [])]
            education = profile.get("education", [])
            deg_str = " ".join(str(e).lower() for e in education)

            # 1. Candidate Name filter
            if query_plan.candidate_names:
                name_match = any(n.lower() in name for n in query_plan.candidate_names)
                if not name_match:
                    logger.debug(f"Candidate {name} failed candidate_names filter")
                    continue

            # 2. Location filter
            if query_plan.location:
                loc_req = query_plan.location.lower()
                if loc_req not in location:
                    logger.debug(f"Candidate {name} failed location filter: loc_req='{loc_req}' not in location='{location}'")
                    continue

            # 3. Minimum Experience filter
            if query_plan.min_experience is not None and query_plan.min_experience > 0:
                m_exp = re.search(r'(\d+)', total_exp_str)
                cand_years = float(m_exp.group(1)) if m_exp else 0.0
                if cand_years < query_plan.min_experience:
                    logger.debug(f"Candidate {name} failed min_exp filter: cand_years={cand_years} < min_exp={query_plan.min_experience}")
                    continue

            # 4. Education degree filter
            if query_plan.education_degree:
                deg_req = query_plan.education_degree.lower()
                if deg_req not in deg_str:
                    logger.debug(f"Candidate {name} failed degree filter")
                    continue

            # 5. Skills filter (at least one skill overlap if skills specified)
            if query_plan.skills:
                req_skills = [sk.lower() for sk in query_plan.skills]
                all_cand_skills = " ".join(skills)
                has_skill = any(sk in all_cand_skills for sk in req_skills)
                if not has_skill:
                    logger.debug(f"Candidate {name} failed skills filter: req={req_skills} not in skills={all_cand_skills}")
                    continue

            filtered.append(candidate)

        # Apply limit if specified
        if query_plan.limit and query_plan.limit > 0:
            filtered = filtered[:query_plan.limit]

        logger.info(f"MultiCandidateSearch: Query '{query_plan.raw_query}' returned {len(filtered)} / {len(candidates)} candidates.")
        return filtered


# Singleton Instance
multi_candidate_search = MultiCandidateSearch()
