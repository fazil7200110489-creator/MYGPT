"""Department-Scoped RAG Service for Private Local Company Knowledge Isolation.

Enforces strict department-level and role-based pre-filtering in backend code.
Runs 100% locally with zero external API dependencies.
"""

import time
import math
import re
from typing import Dict, Any, List, Optional, Union, Set
from loguru import logger

from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.security import UserRoleEnum, SecurityLevelEnum
from backend.app.services.security.permission_manager import permission_manager
from backend.app.services.security.audit_logger import audit_logger
from backend.app.services.storage_service import storage_service
from backend.app.services.embedding_service import embedding_service


class DepartmentRAG:
    """Enterprise Department-Scoped Local RAG Service.
    Guarantees that Tech, HR, and Finance document stores are isolated and strictly filtered.
    """

    def __init__(self):
        self._ensure_synthetic_test_data()

    def _ensure_synthetic_test_data(self) -> None:
        """Seeds initial synthetic test documents for Tech, HR, and Finance if not already present."""
        test_docs = [
            {
                "doc_id": "tech_code_review_policy",
                "text": "TECH_TEST_POLICY: All production API changes require code review, unit tests, and staging deployment verification.",
                "department": DepartmentEnum.TECH,
                "document_type": "technical_policy",
                "security_level": SecurityLevelEnum.INTERNAL,
                "role_required": ["EMPLOYEE", "TECH_ADMIN", "ADMIN"]
            },
            {
                "doc_id": "tech_infrastructure_sop",
                "text": "TECH_INFRA_SOP: Database replication failover procedures and Kubernetes cluster ingress maintenance guides.",
                "department": DepartmentEnum.TECH,
                "document_type": "sop",
                "security_level": SecurityLevelEnum.INTERNAL,
                "role_required": ["TECH_ADMIN", "ADMIN"]
            },
            {
                "doc_id": "hr_leave_policy",
                "text": "HR_TEST_POLICY: Employees receive 18 casual leave days and 12 sick leave days per calendar year with prior manager notification.",
                "department": DepartmentEnum.HR,
                "document_type": "hr_policy",
                "security_level": SecurityLevelEnum.INTERNAL,
                "role_required": ["EMPLOYEE", "HR_MANAGER", "ADMIN"]
            },
            {
                "doc_id": "hr_confidential_compensation",
                "text": "HR_CONFIDENTIAL_SALARY_BAND: Executive compensation salary bands, bonus multipliers, and equity grant allocations for FY2026.",
                "department": DepartmentEnum.HR,
                "document_type": "confidential_compensation",
                "security_level": SecurityLevelEnum.CONFIDENTIAL,
                "role_required": ["HR_MANAGER", "ADMIN"]
            },
            {
                "doc_id": "finance_expense_policy",
                "text": "FINANCE_TEST_POLICY: Expense reports and travel receipts must be submitted by the 25th of every month for reimbursement approval.",
                "department": DepartmentEnum.FINANCE,
                "document_type": "finance_policy",
                "security_level": SecurityLevelEnum.INTERNAL,
                "role_required": ["EMPLOYEE", "FINANCE_MANAGER", "ADMIN"]
            },
            {
                "doc_id": "finance_confidential_audit",
                "text": "FINANCE_CONFIDENTIAL_AUDIT: Internal corporate tax audit findings, offshore balance sheets, and executive dividend schedules.",
                "department": DepartmentEnum.FINANCE,
                "document_type": "confidential_audit",
                "security_level": SecurityLevelEnum.CONFIDENTIAL,
                "role_required": ["FINANCE_MANAGER", "ADMIN"]
            }
        ]

        for doc in test_docs:
            existing = storage_service.get_chunks(doc["doc_id"])
            if not existing:
                self.index_document(
                    doc_id=doc["doc_id"],
                    text=doc["text"],
                    department=doc["department"],
                    document_type=doc["document_type"],
                    security_level=doc["security_level"],
                    role_required=doc["role_required"],
                    source="synthetic_test"
                )

    def index_document(
        self,
        doc_id: str,
        text: str,
        department: Union[DepartmentEnum, str],
        document_type: str = "policy",
        security_level: Union[SecurityLevelEnum, str] = SecurityLevelEnum.INTERNAL,
        role_required: Optional[List[str]] = None,
        source: str = "local"
    ) -> List[Dict[str, Any]]:
        """Indexes a document text block into department-scoped chunk storage with full metadata."""
        dept_str = department.value if isinstance(department, DepartmentEnum) else str(department).upper()
        sec_str = security_level.value if isinstance(security_level, SecurityLevelEnum) else str(security_level).upper()
        now = time.time()

        # Split into semantic lines or paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()] or [text.strip()]
        chunks: List[Dict[str, Any]] = []

        for idx, para in enumerate(paragraphs):
            # Compute local embedding vector
            embeddings = embedding_service.get_embeddings([para])
            vector = embeddings[0] if embeddings else []

            chunk_meta = {
                "chunk_id": f"{doc_id}_chunk_{idx}",
                "doc_id": doc_id,
                "text": para,
                "department": dept_str,
                "document_type": document_type,
                "security_level": sec_str,
                "role_required": role_required or ["EMPLOYEE"],
                "source": source,
                "page_number": 1,
                "created_at": now,
                "updated_at": now,
                "embedding": vector
            }
            chunks.append(chunk_meta)

        storage_service.save_chunks(doc_id, chunks)
        logger.info(f"Indexed document '{doc_id}' into department '{dept_str}' with {len(chunks)} chunks.")
        return chunks

    def retrieve(
        self,
        query: str,
        department: Union[DepartmentEnum, str],
        user_role: Union[UserRoleEnum, str] = UserRoleEnum.EMPLOYEE,
        user_id: str = "dev_user",
        top_k: int = 3,
        similarity_threshold: float = 0.25
    ) -> List[Dict[str, Any]]:
        """Performs security-enforced, department-isolated semantic search.

        Enforces:
        1. Pre-retrieval department access validation.
        2. Strict chunk-level department isolation (HR can never retrieve Finance).
        3. Security level & role-required authorization.
        4. Audit logging of every access decision.
        """
        dept_str = department.value if isinstance(department, DepartmentEnum) else str(department).upper()
        role_str = user_role.value if isinstance(user_role, UserRoleEnum) else str(user_role).upper()

        # 1. Permission Check at Department Level
        if not permission_manager.can_access_department(role_str, dept_str):
            audit_logger.log_event(
                user_id=user_id,
                user_role=role_str,
                department=dept_str,
                requested_resource=f"query:{query[:40]}",
                operation="KNOWLEDGE_RETRIEVAL",
                access_allowed=False,
                details={"reason": f"Role '{role_str}' lacks permission for department '{dept_str}'"}
            )
            logger.warning(f"Access DENIED for user '{user_id}' ({role_str}) to department '{dept_str}'.")
            return []

        # 2. Fetch all chunks
        all_chunks = storage_service.get_all_chunks()

        # 3. Pre-Filter by Department and Security in Backend Code
        permitted_chunks: List[Dict[str, Any]] = []
        for chunk in all_chunks:
            chunk_dept = str(chunk.get("department") or "GENERAL").upper()
            chunk_sec = str(chunk.get("security_level") or "INTERNAL").upper()
            role_req = chunk.get("role_required", ["EMPLOYEE"])

            # Strict Department Partitioning:
            # When querying a specific department (TECH, HR, FINANCE), chunk MUST explicitly belong to that department.
            # When querying GENERAL, chunk must be GENERAL or unassigned.
            if dept_str == "GENERAL":
                if chunk_dept != "GENERAL":
                    continue
            else:
                if chunk_dept != dept_str:
                    continue

            # Role & Security Level Permission Check
            if not permission_manager.can_access_chunk(
                role=role_str,
                target_department=chunk_dept,
                chunk_security_level=chunk_sec,
                role_required=role_req
            ):
                continue

            permitted_chunks.append(chunk)

        if not permitted_chunks:
            audit_logger.log_event(
                user_id=user_id,
                user_role=role_str,
                department=dept_str,
                requested_resource=f"query:{query[:40]}",
                operation="KNOWLEDGE_RETRIEVAL",
                access_allowed=True,
                details={"matched_chunks": 0, "filter_note": "No permitted chunks matched department scope"}
            )
            return []

        # 4. Local Embedding & Cosine Similarity Ranking
        query_vec = embedding_service.get_embeddings([query])
        q_embedding = query_vec[0] if query_vec else []

        scored_chunks: List[Dict[str, Any]] = []
        for chunk in permitted_chunks:
            chunk_emb = chunk.get("embedding", [])
            if q_embedding and chunk_emb and len(q_embedding) == len(chunk_emb):
                score = self._cosine_similarity(q_embedding, chunk_emb)
            else:
                score = 0.0

            # Lexical term overlap scoring boost for local precision
            term_score = self._term_overlap_score(query, chunk.get("text", ""))
            combined_score = max(score, term_score * 0.95)

            if combined_score >= similarity_threshold:
                clean_chunk = {k: v for k, v in chunk.items() if k != "embedding"}
                clean_chunk["department"] = chunk.get("department") or dept_str
                clean_chunk["document_type"] = chunk.get("document_type") or "policy"
                clean_chunk["security_level"] = chunk.get("security_level") or "INTERNAL"
                clean_chunk["role_required"] = chunk.get("role_required") or ["EMPLOYEE"]
                clean_chunk["created_at"] = chunk.get("created_at") or time.time()
                clean_chunk["score"] = round(float(combined_score), 4)
                scored_chunks.append(clean_chunk)

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        results = scored_chunks[:top_k]

        # 5. Record Audit Trace
        audit_logger.log_event(
            user_id=user_id,
            user_role=role_str,
            department=dept_str,
            requested_resource=f"query:{query[:40]}",
            operation="KNOWLEDGE_RETRIEVAL",
            access_allowed=True,
            details={
                "candidate_chunks": len(permitted_chunks),
                "retrieved_count": len(results),
                "top_doc_ids": [r.get("doc_id") for r in results]
            }
        )

        logger.info(f"Department RAG retrieved {len(results)} chunks for query in '{dept_str}' (Role={role_str}).")
        return results

    def _cosine_similarity(self, v1: List[float], v2: List[float]) -> float:
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = math.sqrt(sum(a * a for a in v1))
        n2 = math.sqrt(sum(b * b for b in v2))
        return dot / (n1 * n2) if (n1 > 0 and n2 > 0) else 0.0

    def _term_overlap_score(self, query: str, text: str) -> float:
        """Local word overlap ratio for term-level accuracy, filtering generic stopwords."""
        stopwords = {
            "what", "which", "how", "who", "when", "why", "where", "the", "our", "are",
            "company", "policy", "does", "have", "has", "can", "tell", "about", "for",
            "with", "this", "that", "any", "and", "you", "your", "give", "show", "from"
        }
        q_words = {w for w in re.findall(r"\b\w{3,}\b", query.lower()) if w not in stopwords}
        t_words = {w for w in re.findall(r"\b\w{3,}\b", text.lower()) if w not in stopwords}
        if not q_words:
            return 0.0
        return len(q_words & t_words) / len(q_words)


# Global singleton instance
department_rag = DepartmentRAG()
