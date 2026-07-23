"""Recruiter Knowledge Registry — Dynamic Department & Role Configuration Service.

Manages dynamic department structures, roles, alternative titles, skills,
experience/education requirements, tools, weights, and synonyms without code changes.
"""

import os
import json
from typing import Dict, Any, List, Optional
from loguru import logger

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config")
DEPT_TAXONOMY_PATH = os.path.join(CONFIG_DIR, "department_taxonomy.json")


class RecruiterKnowledgeRegistry:
    """Manages dynamic department, role, skill, and weight configurations."""

    def __init__(self, config_path: str = DEPT_TAXONOMY_PATH):
        self.config_path = config_path
        self.departments: Dict[str, Any] = {}
        self.load_configurations()

    def load_configurations(self) -> None:
        """Load department and role configurations from JSON file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.departments = data.get("departments", {})
                logger.info(f"RecruiterKnowledgeRegistry loaded {len(self.departments)} departments from {self.config_path}")
            except Exception as e:
                logger.error(f"Failed to load department taxonomy from {self.config_path}: {e}")
                self.departments = {}
        else:
            logger.warning(f"Department taxonomy file not found at {self.config_path}. Initializing empty registry.")
            self.departments = {}

    def save_configurations(self) -> bool:
        """Persist updated department configurations back to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({"departments": self.departments}, f, indent=2)
            logger.info("Successfully persisted department configurations to file.")
            return True
        except Exception as e:
            logger.error(f"Failed to save department configurations to {self.config_path}: {e}")
            return False

    def list_departments(self) -> List[str]:
        """Return list of all registered department names."""
        return list(self.departments.keys())

    def get_department(self, dept_name: str) -> Optional[Dict[str, Any]]:
        """Get department details by name (case-insensitive search)."""
        dept_lower = dept_name.strip().lower()
        for name, details in self.departments.items():
            if name.lower() == dept_lower:
                return details
        return None

    def list_roles(self, department_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List roles across a specific department or all departments."""
        roles = []
        if department_name:
            dept = self.get_department(department_name)
            if dept and "roles" in dept:
                for role_key, rdata in dept["roles"].items():
                    r_copy = dict(rdata)
                    r_copy["department"] = dept.get("department_name", department_name)
                    roles.append(r_copy)
        else:
            for dept_name, dept_data in self.departments.items():
                for role_key, rdata in dept_data.get("roles", {}).items():
                    r_copy = dict(rdata)
                    r_copy["department"] = dept_data.get("department_name", dept_name)
                    roles.append(r_copy)
        return roles

    def find_role(self, role_name: str, department_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find role by name or alternative title across departments."""
        target_lower = role_name.strip().lower()
        candidate_roles = self.list_roles(department_name)

        # 1. Exact match on role_name
        for r in candidate_roles:
            if r.get("role_name", "").lower() == target_lower:
                return r

        # 2. Match in alternative_titles or synonyms
        for r in candidate_roles:
            alts = [a.lower() for a in r.get("alternative_titles", [])]
            syns = [s.lower() for s in r.get("synonyms", [])]
            if target_lower in alts or target_lower in syns:
                return r

        # 3. Partial substring match
        for r in candidate_roles:
            if target_lower in r.get("role_name", "").lower():
                return r

        return None

    def add_or_update_department(self, dept_name: str, department_weight: float = 1.0) -> Dict[str, Any]:
        """Add a new department or update an existing department weight."""
        dept = self.get_department(dept_name)
        if dept:
            dept["department_weight"] = department_weight
        else:
            self.departments[dept_name] = {
                "department_name": dept_name,
                "department_weight": department_weight,
                "roles": {}
            }
        self.save_configurations()
        return self.departments[dept_name]

    def add_or_update_role(self, department_name: str, role_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add or update a role under a specific department."""
        dept_name_resolved = department_name
        dept = self.get_department(department_name)
        if not dept:
            dept = self.add_or_update_department(department_name)

        rname = role_config.get("role_name")
        if not rname:
            logger.error("role_name is required to add or update a role.")
            return None

        normalized_config = {
            "role_name": rname,
            "alternative_titles": role_config.get("alternative_titles", []),
            "required_skills": role_config.get("required_skills", []),
            "preferred_skills": role_config.get("preferred_skills", []),
            "nice_to_have_skills": role_config.get("nice_to_have_skills", []),
            "experience_min_years": role_config.get("experience_min_years", 0),
            "education_requirements": role_config.get("education_requirements", []),
            "certification_requirements": role_config.get("certification_requirements", []),
            "tools": role_config.get("tools", []),
            "technology_stack": role_config.get("technology_stack", []),
            "synonyms": role_config.get("synonyms", []),
            "skill_weight": role_config.get("skill_weight", 4.0),
            "role_weight": role_config.get("role_weight", 2.5),
            "domain_weight": role_config.get("domain_weight", 2.0)
        }

        if "roles" not in dept:
            dept["roles"] = {}
        dept["roles"][rname] = normalized_config
        self.save_configurations()
        return normalized_config

    def delete_role(self, department_name: str, role_name: str) -> bool:
        """Delete a role from a department."""
        dept = self.get_department(department_name)
        if dept and "roles" in dept:
            for rname in list(dept["roles"].keys()):
                if rname.lower() == role_name.lower():
                    del dept["roles"][rname]
                    self.save_configurations()
                    return True
        return False


# Singleton Instance
recruiter_knowledge_registry = RecruiterKnowledgeRegistry()
