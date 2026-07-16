import re
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.conversation_memory import conversation_memory
from backend.app.services.knowledge_service import knowledge_store

class EntityRelationshipResolver:
    """Resolves pronouns and context references ('he', 'it', 'that project') in follow-up queries."""

    def resolve(self, query: str, session_id: str, doc_id: Optional[str] = None) -> str:
        """Analyzes dialogue history and resolves pronoun references in the query."""
        q_lower = query.lower()
        
        # Pronouns we want to resolve
        pronoun_patterns = {
            "candidate": r'\b(he|him|his|she|her|candidate|applicant|candidate\'s)\b',
            "project": r'\b(that project|the project|this project|project)\b',
            "invoice": r'\b(it|its|invoice|bill)\b',
            "excel": r'\b(it|table|sheet|data)\b'
        }

        # Check if the query has any pronouns
        has_pronouns = any(re.search(pat, q_lower) for pat in pronoun_patterns.values())
        if not has_pronouns:
            return query

        # Load knowledge facts if doc_id is available
        knowledge = knowledge_store.get_knowledge(doc_id) if doc_id else None
        doc_type = knowledge.get("document_type", "Generic") if knowledge else "Generic"
        facts = knowledge.get("facts", {}) if knowledge else {}
        entities = knowledge.get("entities", {}) if knowledge else {}

        resolved_query = query
        history = conversation_memory.get_history(session_id)

        # 1. Resolve Candidate Names (he/she/his/her)
        if re.search(pronoun_patterns["candidate"], q_lower):
            name = facts.get("name") or (entities.get("people", [None])[0])
            if not name and history:
                # Fallback: scan history user queries for a name
                for msg in reversed(history):
                    if msg["role"] == "user":
                        m = re.search(r'\b(who is|about)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b', msg["content"])
                        if m:
                            name = m.group(2)
                            break
            if name:
                # Replace pronouns with the candidate name
                resolved_query = re.sub(r'\b(he|she|the candidate|the applicant)\b', name, resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r'\b(his|her)\b', f"{name}'s", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r'\b(him)\b', name, resolved_query, flags=re.IGNORECASE)

        # 2. Resolve Projects (that project / this project)
        if re.search(pronoun_patterns["project"], q_lower):
            project_name = None
            # Check facts for project names
            projects = facts.get("projects")
            if isinstance(projects, list) and projects:
                project_name = projects[0]
            elif isinstance(projects, str):
                # Grab the first line or name
                project_name = projects.split('\n')[0].strip().split('.')[0].strip()

            if not project_name and history:
                # Scan history for a mentioned project
                for msg in reversed(history):
                    for word in re.findall(r'\b[A-Z][A-Za-z0-9_]{2,}\b', msg["content"]):
                        if word.lower() not in ["resume", "cv", "candidate", " Delhi", "Google", "Microsoft"]:
                            project_name = word
                            break
                    if project_name:
                        break

            if project_name:
                resolved_query = re.sub(r'\b(that project|the project|this project)\b', f"'{project_name}'", resolved_query, flags=re.IGNORECASE)

        # 3. Resolve Document specific 'it' (Invoice / Excel)
        if re.search(r'\b(it|its)\b', q_lower):
            if doc_type == "Invoice":
                invoice_num = facts.get("invoice_number") or "invoice"
                resolved_query = re.sub(r'\b(it)\b', f"invoice {invoice_num}", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r'\b(its)\b', f"invoice {invoice_num}'s", resolved_query, flags=re.IGNORECASE)
            elif doc_type == "Excel":
                resolved_query = re.sub(r'\b(it)\b', "the sheet records", resolved_query, flags=re.IGNORECASE)
                resolved_query = re.sub(r'\b(its)\b', "the sheet's", resolved_query, flags=re.IGNORECASE)
            elif doc_type == "Resume":
                # For resume, 'it' might refer to the last project mentioned
                project_name = None
                if history:
                    for msg in reversed(history):
                        for word in re.findall(r'\b[A-Z][A-Za-z50-9_]{2,}\b', msg["content"]):
                            if word.lower() not in ["resume", "cv", "candidate"]:
                                project_name = word
                                break
                        if project_name:
                            break
                if project_name:
                    resolved_query = re.sub(r'\b(it)\b', f"'{project_name}'", resolved_query, flags=re.IGNORECASE)
                    resolved_query = re.sub(r'\b(its)\b', f"'{project_name}'s", resolved_query, flags=re.IGNORECASE)

        if resolved_query != query:
            logger.info(f"Resolved reference query: '{query}' -> '{resolved_query}'")

        return resolved_query
