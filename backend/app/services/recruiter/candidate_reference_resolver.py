"""Candidate Reference & Alias Resolver Engine for Recruiter Multi-Resume Platform.

Resolves candidate entity references, first/last name aliases, pronouns, ordinals, standalone keywords,
and explicit candidate numbers against the candidate pool and active conversation session memory.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from backend.app.services.recruiter.recruiter_session_memory import recruiter_session_memory


class CandidateReferenceResolver:
    """Resolves candidate references, pronouns, aliases, numeric indexes, ordinals, and ambiguous queries."""

    @staticmethod
    def resolve_candidates_with_ambiguity(
        query: str,
        pool: List[Dict[str, Any]],
        session_id: str = "default_session"
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Resolves target candidates and detects ambiguous pronoun/ordinal references.

        Returns:
            Tuple[List[Dict[str, Any]], is_ambiguous: bool]
        """
        if not pool:
            return [], False

        q_lower = (query or "").lower().strip()

        # ----------------------------------------------------------------------------------------
        # 1. Explicit Candidate Number Matching ("candidate 1", "candidate 2", "of candidate 2", "of 2", "#2")
        # ----------------------------------------------------------------------------------------
        num_m = re.search(r'\b(?:candidate\s*#?|candidate\s+id\s*|of\s+candidate\s+|of\s+)(10|[1-9])\b', q_lower)
        if not num_m:
            num_m = re.search(r'\b#([1-9]|10)\b', q_lower)

        if num_m:
            idx_1based = int(num_m.group(1))
            if 1 <= idx_1based <= len(pool):
                target_cand = pool[idx_1based - 1]
                logger.info(f"CandidateReferenceResolver: Matched numeric candidate index #{idx_1based} -> {target_cand.get('candidate_name') or target_cand.get('name')}")
                return [target_cand], False

        # ----------------------------------------------------------------------------------------
        # 2. Universal Keywords ("both", "all", "all candidates", "both candidates")
        # ----------------------------------------------------------------------------------------
        if any(re.search(r'\b' + kw + r'\b', q_lower) for kw in ["both", "both candidates"]):
            return pool[:2] if len(pool) >= 2 else pool, False

        if any(re.search(r'\b' + kw + r'\b', q_lower) for kw in ["all", "all candidates", "everyone", "every candidate"]):
            return pool, False

        # ----------------------------------------------------------------------------------------
        # 3. Direct & Fuzzy Candidate Name / Alias Matching ("Mohamed", "Fazil", "Ravi Kumar", "Shekhar", "Komal")
        # ----------------------------------------------------------------------------------------
        COMMON_NAME_ALIASES = {
            "mohd": "mohamed",
            "md": "mohamed",
            "muhammad": "mohamed",
            "sanjay": "sanjaya",
            "umamahesh": "uma mahesh",
            "umamaheshwar": "uma mahesh"
        }

        # Step 3a: Tier 1 - Full Name Exact / Substring Phrase Match
        tier1_matches = []
        for cand in pool:
            profile = cand.get("candidate_profile", {})
            cname = cand.get("candidate_name") or profile.get("name") or cand.get("name") or ""
            if not cname or cname in ("Not Mentioned", "Candidate"):
                continue

            cname_lower = cname.lower().strip()
            cname_no_space = cname_lower.replace(" ", "")

            # Exact multi-word phrase or space-insensitive match (e.g. "ravi kumar", "komal kumari")
            q_no_space = q_lower.replace(" ", "")
            if len(cname_lower.split()) > 1:
                pattern = r'\b' + re.escape(cname_lower) + r'(?:s|\'s)?\b'
                if re.search(pattern, q_lower) or cname_no_space in q_no_space:
                    tier1_matches.append(cand)
            elif cname_lower in q_lower or cname_no_space in q_no_space:
                tier1_matches.append(cand)

        if tier1_matches:
            logger.info(f"CandidateReferenceResolver: Tier 1 Matched explicit full name(s) -> {[c.get('candidate_name') or c.get('name') for c in tier1_matches]}")
            return tier1_matches, False

        # Step 3b: Tier 2 - Unique First/Last Name & Alias Match
        tier2_matches = []
        tier2_ids = set()
        GENERIC_SURNAMES = {"kumar", "kumari", "singh", "sharma", "patel", "kaur", "devi"}

        for cand in pool:
            profile = cand.get("candidate_profile", {})
            cname = cand.get("candidate_name") or profile.get("name") or cand.get("name") or ""
            if not cname or cname in ("Not Mentioned", "Candidate"):
                continue

            cname_lower = cname.lower().strip()
            name_parts = [p for p in re.split(r'\s+', cname_lower) if len(p) >= 3]

            # Alias lookup matching
            alias_matched = False
            for alias_k, canonical_v in COMMON_NAME_ALIASES.items():
                if re.search(r'\b' + re.escape(alias_k) + r'\b', q_lower):
                    if canonical_v in cname_lower:
                        if cand.get("candidate_id") not in tier2_ids:
                            tier2_matches.append(cand)
                            tier2_ids.add(cand.get("candidate_id"))
                        alias_matched = True
                        break

            if alias_matched:
                continue

            # Unique part matching
            for part in name_parts:
                alias_pattern = r'\b' + re.escape(part) + r'(?:a|s|\'s)?\b'
                if re.search(alias_pattern, q_lower):
                    # Skip generic surnames matching if query contains other words and surname is generic
                    if part in GENERIC_SURNAMES and len(name_parts) > 1 and len(q_lower.split()) > 2:
                        # Check if any candidate has a stronger non-generic match
                        has_first_name_match = any(
                            re.search(r'\b' + re.escape(p) + r'(?:a|s|\'s)?\b', q_lower)
                            for p in name_parts if p not in GENERIC_SURNAMES
                        )
                        if not has_first_name_match:
                            continue
                    if cand.get("candidate_id") not in tier2_ids:
                        tier2_matches.append(cand)
                        tier2_ids.add(cand.get("candidate_id"))
                    break

        if tier2_matches:
            logger.info(f"CandidateReferenceResolver: Tier 2 Matched name part/alias -> {[c.get('candidate_name') or c.get('name') for c in tier2_matches]}")
            return tier2_matches, False


        # ----------------------------------------------------------------------------------------
        # 4. Ordinal Keywords ("first", "second", "third", "last", "top candidate", "rank 1")
        # ----------------------------------------------------------------------------------------
        session = recruiter_session_memory.get_session(session_id)
        last_ranked = session.get("last_ranked_results", [])
        last_cand_ids = session.get("last_candidate_ids", [])

        if any(re.search(r'\b' + kw + r'\b', q_lower) for kw in ["first candidate", "the first candidate", "1st candidate", "first", "top candidate", "rank 1", "winner"]):
            if last_ranked:
                top_id = last_ranked[0].get("candidate_id")
                found = [c for c in pool if c.get("candidate_id") == top_id or c.get("id") == top_id]
                if found:
                    return found, False
            elif len(pool) >= 1:
                return [pool[0]], False

        if any(re.search(r'\b' + kw + r'\b', q_lower) for kw in ["second candidate", "the second candidate", "2nd candidate", "second", "rank 2"]):
            if last_ranked and len(last_ranked) >= 2:
                sec_id = last_ranked[1].get("candidate_id")
                found = [c for c in pool if c.get("candidate_id") == sec_id or c.get("id") == sec_id]
                if found:
                    return found, False
            elif len(pool) >= 2:
                return [pool[1]], False

        if "last candidate" in q_lower or "the last candidate" in q_lower or re.search(r'\blast\b', q_lower):
            if pool:
                return [pool[-1]], False

        # ----------------------------------------------------------------------------------------
        # 5. Pronoun Resolution & Ambiguity Detection ("his", "her", "him", "he", "she", "them")
        # ----------------------------------------------------------------------------------------
        has_singular_pronoun = any(re.search(r'\b' + p + r'\b', q_lower) for p in ["his", "her", "him", "he", "she", "this candidate"])
        has_plural_pronoun = any(re.search(r'\b' + p + r'\b', q_lower) for p in ["them", "their", "these candidates"])

        if has_singular_pronoun and last_cand_ids and len(last_cand_ids) > 1:
            # Ambiguity detected! Singular pronoun used after a multi-candidate comparison/turn
            logger.info(f"CandidateReferenceResolver: Ambiguous singular pronoun reference detected over multiple candidates: {last_cand_ids}")
            return [], True

        if (has_singular_pronoun or has_plural_pronoun) and last_cand_ids:
            target_ids = last_cand_ids[:1] if has_singular_pronoun else last_cand_ids
            found = [c for c in pool if c.get("candidate_id") in target_ids or c.get("id") in target_ids]
            if found:
                logger.info(f"CandidateReferenceResolver: Resolved pronoun reference to -> {[c.get('candidate_name') or c.get('name') for c in found]}")
                return found, False

        return [], False

    @classmethod
    def resolve_candidates(
        cls,
        query: str,
        pool: List[Dict[str, Any]],
        session_id: str = "default_session"
    ) -> List[Dict[str, Any]]:
        """Convenience method returning resolved candidates list."""
        cands, _ = cls.resolve_candidates_with_ambiguity(query, pool, session_id)
        return cands


candidate_reference_resolver = CandidateReferenceResolver()
