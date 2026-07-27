import re
from typing import Dict, Any, List, Tuple

class ProjectAnalyzer:
    """Extracts candidate projects and evaluates their complexity tier (Low, Medium, High)."""

    def analyze(self, entities: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        projects_list, has_dedicated_projects = self._extract_projects(entities, raw_text)
        
        # Evaluate complexity and build the structured projects object
        analyzed_projects = []
        for p in projects_list:
            comp_tier, details = self._evaluate_project_complexity(p, raw_text)
            analyzed_projects.append({
                "name": p,
                "complexity_tier": comp_tier,
                "confidence_score": 90.0 if len(p) > 10 else 70.0,
                "evidence_snippet": details
            })
            
        return {
            "projects": projects_list,
            "has_dedicated_projects": has_dedicated_projects,
            "detailed_projects": analyzed_projects
        }

    def _extract_projects(self, entities: Dict[str, Any], text: str) -> Tuple[List[str], bool]:
        """Extract projects supporting both single-line comma-separated lists and multiline blocks."""
        raw = entities.get("projects") or []
        items = []

        if isinstance(raw, list):
            items = [str(i).strip() for i in raw if str(i).strip()]
        elif isinstance(raw, str):
            items = [l.strip() for l in raw.split('\n') if l.strip()]

        if not items and text:
            # 1. Try matching single line style: Projects: Project A, Project B
            m_single = re.search(r'(?i)\bprojects?\b\s*:\s*([^\n]+)', text)
            if m_single:
                val = m_single.group(1).strip()
                if ',' in val or ';' in val:
                    items = [i.strip() for i in re.split(r'[,;]', val) if i.strip()]
                else:
                    items = [val]
            
            # 2. Try matching multiline block style
            if not items:
                m = re.search(r'(?i)\bprojects?\b\s*:?\s*\n([\s\S]{5,500}?)(?=\n\s*[A-Z\s]{4,20}\n|\Z)', text)
                if m:
                    proj_block = m.group(1).strip()
                    items = [l.strip().lstrip('1234567890.-*• ') for l in proj_block.split('\n') if l.strip()]

        has_dedicated = bool(items) or bool(
            re.search(r'(?i)\bprojects?\b', text)
        )

        return items, has_dedicated

    def _evaluate_project_complexity(self, project_name: str, full_text: str) -> Tuple[str, str]:
        """Heuristically evaluates project complexity and matches details in raw text."""
        p_lower = project_name.lower()
        
        # Locate project context or description in raw text
        snippet = ""
        lines = full_text.split('\n')
        for idx, line in enumerate(lines):
            if p_lower in line.lower():
                # Take matching line plus next 2 lines as description context
                snippet = " ".join(l.strip() for l in lines[idx:idx+3] if l.strip())
                break
                
        desc = snippet or project_name
        desc_lower = desc.lower()

        # Indicators
        high_complexity_kws = ["architecture", "migration", "optimization", "distributed", "microservices", "scale", "performance", "real-time", "pipeline", "infrastructure", "kubernetes", "cloud-native", "enterprise"]
        medium_complexity_kws = ["database", "automation", "integration", "rest api", "dashboard", "frontend", "backend", "web application", "deployed"]

        high_matches = sum(1 for kw in high_complexity_kws if kw in desc_lower)
        med_matches = sum(1 for kw in medium_complexity_kws if kw in desc_lower)

        # Word count & technology stack size
        tech_words = ["react", "node", "python", "aws", "docker", "angular", "flask", "django", "postgres", "mysql", "mongodb"]
        tech_matches = sum(1 for tw in tech_words if tw in desc_lower)

        if high_matches >= 2 or (high_matches >= 1 and tech_matches >= 2) or len(desc) > 150:
            return "High", desc
        elif med_matches >= 2 or tech_matches >= 1 or len(desc) > 80:
            return "Medium", desc
        else:
            return "Low", desc
