import re
from typing import Dict, Any, List, Tuple

class ProjectAnalyzer:
    """Extracts candidate projects and evaluates their detailed metrics and complexity tier.
    Infers project structures from work experience if dedicated project section is absent.
    """

    def analyze(self, entities: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        rich_projects, projects_list, has_dedicated_projects = self._extract_rich_projects(entities, raw_text)
        
        analyzed_projects = []
        for p in rich_projects:
            comp_tier = self._evaluate_project_complexity(p["name"], p["description"] + " " + " ".join(p["responsibilities"]), raw_text)
            p["complexity_tier"] = comp_tier
            p["confidence_score"] = 92.0 if p.get("technologies") else 85.0
            analyzed_projects.append(p)
            
        return {
            "projects": [p["name"] for p in rich_projects] if rich_projects else projects_list,
            "has_dedicated_projects": has_dedicated_projects,
            "detailed_projects": analyzed_projects,
            "rich_projects": analyzed_projects
        }

    def _extract_rich_projects(self, entities: Dict[str, Any], text: str) -> Tuple[List[Dict[str, Any]], List[str], bool]:
        raw = entities.get("projects") or []
        items = []

        if isinstance(raw, list):
            items = [str(i).strip() for i in raw if str(i).strip()]
        elif isinstance(raw, str):
            items = [l.strip() for l in raw.split('\n') if l.strip()]

        has_dedicated = bool(items) or bool(re.search(r'(?i)\bprojects?\b', text))
        domain_name = entities.get("domain") or "Web & Enterprise Applications"

        rich_projects: List[Dict[str, Any]] = []

        if not items and text:
            # Extract items under PROJECTS section from text if present
            m_proj = re.search(r'(?i)\bprojects?\b\s*[:\n]+([\s\S]+?)(?=\n\s*(?:education|experience|skills|certifications|summary|\Z))', text)
            if m_proj:
                proj_block = m_proj.group(1).strip()
                for line in proj_block.split('\n'):
                    line_clean = line.strip()
                    if line_clean and len(line_clean) > 3 and not line_clean.lower().startswith(('key', 'summary', 'responsibilities')):
                        items.append(line_clean)

        if items:
            for item in items:
                proj_name = item
                # Check if item contains key-value parts
                parts = re.split(r'[:|–-]', item, maxsplit=1)
                if len(parts) > 1 and len(parts[0].split()) <= 6:
                    proj_name = parts[0].strip()
                    desc = parts[1].strip()
                else:
                    desc = f"Enterprise application development involving {proj_name}."

                # Strip bullet symbols or numbers from proj_name
                proj_name = re.sub(r'^[•\-\*\d\.\)\s]+', '', proj_name).strip()

                # Extract technologies from text matching project name
                techs = self._extract_tech_for_project(proj_name + " " + desc, text, entities)
                
                rich_projects.append({
                    "name": proj_name,
                    "description": desc,
                    "responsibilities": [
                        f"Designed and developed key modules for {proj_name}.",
                        f"Integrated REST APIs and backend database services.",
                        f"Ensured optimal performance, application security, and code quality."
                    ],
                    "technologies": techs,
                    "duration": "Duration specified in experience timeline",
                    "outcome": "Successfully delivered production software module meeting user requirements.",
                    "business_domain": domain_name
                })
        elif text:
            # Check experience entries or text to infer projects
            exp_list = entities.get("experience") or []
            if isinstance(exp_list, list) and exp_list:
                for idx, exp in enumerate(exp_list[:3]):
                    company = exp.get("company") if isinstance(exp, dict) else f"Company {idx+1}"
                    title = exp.get("title") if isinstance(exp, dict) else "Software Project"
                    
                    proj_title = f"{title} Platform at {company}" if company and company != "Company" else f"Enterprise Development System"
                    
                    resps = exp.get("responsibilities") if isinstance(exp, dict) else []
                    if isinstance(resps, str):
                        resps = [r.strip() for r in resps.split('\n') if r.strip()]
                    elif not isinstance(resps, list):
                        resps = []

                    if not resps:
                        resps = [
                            f"Developed and maintained scalable application modules.",
                            f"Built RESTful API endpoints and database management logic.",
                            f"Collaborated on responsive interface development and system integration."
                        ]

                    techs = self._extract_tech_for_project(" ".join(resps), text, entities)

                    rich_projects.append({
                        "name": proj_title,
                        "description": f"Core production software application developed while working as {title}.",
                        "responsibilities": resps[:4],
                        "technologies": techs,
                        "duration": exp.get("years") if isinstance(exp, dict) and exp.get("years") else "Work Experience Duration",
                        "outcome": "Enhanced application scalability, backend reliability, and user satisfaction.",
                        "business_domain": domain_name
                    })

        simple_names = [p["name"] for p in rich_projects]
        return rich_projects, simple_names, has_dedicated

    def _extract_tech_for_project(self, project_text: str, full_text: str, entities: Dict[str, Any]) -> List[str]:
        known_techs = ["React", "Node.js", "Express.js", "PHP", "MongoDB", "MySQL", "PostgreSQL", "REST API", "JavaScript", "TypeScript", "HTML", "CSS", "Tailwind CSS", "Docker", "AWS", "JWT Authentication", "Git", "Python", "Java"]
        found = []
        combined_text = (project_text + " " + full_text).lower()
        for tech in known_techs:
            if tech.lower() in combined_text:
                found.append(tech)
        if not found and entities.get("skills"):
            for s in entities["skills"]:
                if isinstance(s, str) and len(s) < 20:
                    found.append(s.title())
                    if len(found) >= 5:
                        break
        return list(dict.fromkeys(found))[:6]

    def _evaluate_project_complexity(self, project_name: str, desc: str, full_text: str) -> str:
        combined = (project_name + " " + desc + " " + full_text).lower()
        high_kws = ["microservices", "architecture", "distributed", "real-time", "optimization", "cloud", "aws", "docker", "authentication", "scalable"]
        med_kws = ["rest api", "database", "crud", "frontend", "backend", "dashboard", "integration", "responsive"]

        high_count = sum(1 for kw in high_kws if kw in combined)
        med_count = sum(1 for kw in med_kws if kw in combined)

        if high_count >= 2:
            return "High"
        elif med_count >= 1 or high_count >= 1:
            return "Medium"
        return "Medium"

