"""Role Requirement Analyzer — Dynamic Role Inference & Requirement Profile Generator.

Extracts:
- Role Name & Department
- Required & Preferred Skills
- Experience & Education Requirements
- Frameworks, Languages, Cloud, Databases, Soft Skills, Certifications
- Dynamic inferencing for unregistered/arbitrary tech & non-tech roles
"""

import re
from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.recruiter.job_requirement_builder import RequirementProfile


# Comprehensive Role Taxonomy Database for Dynamic Inference
DYNAMIC_ROLE_PATTERNS: Dict[str, Dict[str, Any]] = {
    "frontend": {
        "department": "Engineering",
        "required_skills": ["React", "JavaScript", "TypeScript", "HTML", "CSS", "REST API", "Git", "Responsive Design"],
        "preferred_skills": ["Next.js", "Tailwind", "Material UI", "Redux", "Webpack", "Vite", "GraphQL"],
        "tools": ["Git", "VS Code", "Figma", "npm/yarn"],
        "technology_stack": ["Frontend Web Development", "Client-Side Rendering", "Single Page Applications"],
        "min_experience_years": 2.0,
        "education_requirements": ["B.Tech", "B.E.", "BCA", "BS Computer Science"]
    },
    "backend": {
        "department": "Engineering",
        "required_skills": ["Python", "Java", "Node.js", "SQL", "REST API", "PostgreSQL", "Git", "Data Structures"],
        "preferred_skills": ["FastAPI", "Django", "Spring Boot", "Docker", "Kubernetes", "Redis", "Microservices", "Kafka"],
        "tools": ["Docker", "Postman", "Git", "Linux", "CI/CD"],
        "technology_stack": ["Backend Server Architecture", "Database Design", "API Development"],
        "min_experience_years": 3.0,
        "education_requirements": ["B.Tech", "B.E.", "MCA", "BS Computer Science"]
    },
    "fullstack": {
        "department": "Engineering",
        "required_skills": ["React", "Node.js", "JavaScript", "Python", "SQL", "HTML", "CSS", "REST API", "Git"],
        "preferred_skills": ["TypeScript", "Next.js", "Docker", "PostgreSQL", "MongoDB", "AWS", "Tailwind"],
        "tools": ["Git", "Docker", "VS Code", "Postman"],
        "technology_stack": ["Full Stack Engineering", "Web Applications", "End-to-End Development"],
        "min_experience_years": 3.0,
        "education_requirements": ["B.Tech", "B.E.", "BCA", "MCA"]
    },
    "devops": {
        "department": "Infrastructure & Operations",
        "required_skills": ["Docker", "Kubernetes", "AWS", "Linux", "CI/CD", "Terraform", "Git", "Bash/Shell Scripting"],
        "preferred_skills": ["Ansible", "Prometheus", "Grafana", "Python", "Azure", "GCP", "Jenkins", "Helm"],
        "tools": ["Docker", "Kubernetes", "Terraform", "Jenkins", "GitLab CI"],
        "technology_stack": ["Cloud Infrastructure", "DevOps & Automation", "Site Reliability"],
        "min_experience_years": 3.0,
        "education_requirements": ["B.Tech", "B.E.", "BS Computer Science"]
    },
    "ai": {
        "department": "Data & Artificial Intelligence",
        "required_skills": ["Python", "Machine Learning", "Deep Learning", "PyTorch", "TensorFlow", "Scikit-Learn", "SQL", "NLP"],
        "preferred_skills": ["LLMs", "LangChain", "Transformers", "RAG", "Computer Vision", "MLOps", "Pandas", "NumPy"],
        "tools": ["Jupyter", "PyTorch", "Git", "Docker", "Hugging Face"],
        "technology_stack": ["Artificial Intelligence", "Machine Learning Models", "Generative AI"],
        "min_experience_years": 2.0,
        "education_requirements": ["B.Tech", "M.Tech", "M.Sc Computer Science", "Ph.D."]
    },
    "data": {
        "department": "Data & Analytics",
        "required_skills": ["Python", "SQL", "Pandas", "NumPy", "Data Analysis", "ETL", "Data Visualization", "Git"],
        "preferred_skills": ["Tableau", "Power BI", "Spark", "Airflow", "Snowflake", "BigQuery", "Scikit-Learn"],
        "tools": ["Jupyter", "SQL Workbench", "PowerBI", "Git"],
        "technology_stack": ["Data Engineering", "Data Analytics", "Business Intelligence"],
        "min_experience_years": 2.0,
        "education_requirements": ["B.Tech", "B.Sc Statistics", "MCA", "M.Sc"]
    },
    "hr": {
        "department": "Human Resources",
        "required_skills": ["Recruitment", "Talent Acquisition", "HRMS", "Employee Relations", "Screening", "Interviewing", "Communication"],
        "preferred_skills": ["Payroll Management", "Onboarding", "HR Analytics", "Compliance", "Performance Management", "LinkedIn Recruiter"],
        "tools": ["Workday", "BambooHR", "Excel", "LinkedIn Recruiter"],
        "technology_stack": ["Human Resource Operations", "Talent Management"],
        "min_experience_years": 2.0,
        "education_requirements": ["MBA HR", "BBA", "Bachelor's Degree"]
    },
    "finance": {
        "department": "Finance & Accounting",
        "required_skills": ["Accounting", "Financial Analysis", "Tally", "GST", "Excel", "Taxation", "Bookkeeping"],
        "preferred_skills": ["SAP", "Auditing", "Financial Reporting", "Budgeting", "Forecasting", "ERP"],
        "tools": ["Tally Prime", "MS Excel", "SAP ERP", "QuickBooks"],
        "technology_stack": ["Corporate Finance", "Accounting & Taxation"],
        "min_experience_years": 2.0,
        "education_requirements": ["B.Com", "M.Com", "MBA Finance", "CA", "CMA"]
    },
    "qa": {
        "department": "Quality Assurance",
        "required_skills": ["Software Testing", "Manual Testing", "Test Automation", "Selenium", "Test Cases", "Bug Tracking", "Jira"],
        "preferred_skills": ["Cypress", "Playwright", "Postman API Testing", "Python/Java", "JMeter", "Performance Testing"],
        "tools": ["Jira", "Selenium", "Postman", "TestRail"],
        "technology_stack": ["Quality Assurance", "Test Engineering"],
        "min_experience_years": 2.0,
        "education_requirements": ["B.Tech", "B.E.", "BCA", "MCA"]
    },
    "mobile": {
        "department": "Engineering",
        "required_skills": ["Mobile App Development", "Flutter/React Native", "iOS/Android", "Dart/JavaScript/Kotlin/Swift", "REST API", "Git"],
        "preferred_skills": ["State Management (Bloc/Redux)", "Firebase", "App Store Publishing", "UI/UX Design"],
        "tools": ["Android Studio", "Xcode", "VS Code", "Git"],
        "technology_stack": ["Cross-Platform Mobile Development", "Native Mobile Apps"],
        "min_experience_years": 2.0,
        "education_requirements": ["B.Tech", "B.E.", "BCA"]
    }
}


class RoleRequirementAnalyzer:
    """Analyzes and infers dynamic requirement profiles from any role query."""

    def analyze_role(self, role_name: str, explicit_skills: Optional[List[str]] = None) -> RequirementProfile:
        """Infer canonical RequirementProfile dynamically for any given target role name."""
        r_lower = role_name.lower().strip()
        matched_key: Optional[str] = None

        # 1. Pattern matching against taxonomy keys
        if "front" in r_lower or "react" in r_lower or "angular" in r_lower or "vue" in r_lower or "ui" in r_lower:
            matched_key = "frontend"
        elif "back" in r_lower or "api" in r_lower or "server" in r_lower or "node" in r_lower:
            matched_key = "backend"
        elif "full" in r_lower or "stack" in r_lower:
            matched_key = "fullstack"
        elif "devops" in r_lower or "cloud" in r_lower or "site reliability" in r_lower or "sre" in r_lower or "aws" in r_lower:
            matched_key = "devops"
        elif "ai" in r_lower or "machine learning" in r_lower or "ml" in r_lower or "nlp" in r_lower or "llm" in r_lower or "deep learning" in r_lower:
            matched_key = "ai"
        elif "data" in r_lower or "analytic" in r_lower or "bi" in r_lower or "sql" in r_lower:
            matched_key = "data"
        elif "hr" in r_lower or "recruiter" in r_lower or "human resource" in r_lower or "talent" in r_lower:
            matched_key = "hr"
        elif "finance" in r_lower or "account" in r_lower or "tax" in r_lower or "tally" in r_lower or "audit" in r_lower:
            matched_key = "finance"
        elif "qa" in r_lower or "test" in r_lower or "quality" in r_lower or "automation" in r_lower:
            matched_key = "qa"
        elif "mobile" in r_lower or "android" in r_lower or "ios" in r_lower or "flutter" in r_lower:
            matched_key = "mobile"

        if matched_key and matched_key in DYNAMIC_ROLE_PATTERNS:
            p = DYNAMIC_ROLE_PATTERNS[matched_key]
            dept = p["department"]
            req_skills = list(p["required_skills"])
            pref_skills = list(p["preferred_skills"])
            tools = list(p["tools"])
            tech_stack = list(p["technology_stack"])
            min_exp = p["min_experience_years"]
            edu_reqs = list(p["education_requirements"])
        else:
            # Fallback for unrecognized custom role name
            dept = "General Industry"
            words = [w.capitalize() for w in re.findall(r'\b[a-zA-Z]{3,}\b', role_name) if w.lower() not in ("developer", "engineer", "specialist", "manager", "executive", "lead")]
            req_skills = words if words else [role_name.title()]
            pref_skills = ["Domain Knowledge", "Communication", "Problem Solving"]
            tools = ["Git", "MS Office"]
            tech_stack = [role_name.title()]
            min_exp = 1.0
            edu_reqs = ["Bachelor's Degree"]

        # Merge explicit query skills
        if explicit_skills:
            for sk in explicit_skills:
                if sk not in req_skills and sk not in pref_skills:
                    pref_skills.append(sk)

        profile = RequirementProfile(
            target_role=role_name.title(),
            department=dept,
            required_skills=req_skills,
            preferred_skills=pref_skills,
            nice_to_have_skills=["Git", "Agile", "Communication"],
            min_experience_years=min_exp,
            education_requirements=edu_reqs,
            certification_requirements=[],
            tools=tools,
            technology_stack=tech_stack,
            weights={
                "skill_weight": 4.0,       # 40%
                "experience_weight": 2.0,  # 20%
                "project_weight": 1.5,     # 15%
                "education_weight": 1.0,   # 10%
                "certification_weight": 0.5,# 5%
                "resume_quality_weight": 0.5, # 5%
                "domain_weight": 0.5       # 5%
            }
        )

        logger.info(f"RoleRequirementAnalyzer inferred profile for '{role_name}': Dept={dept}, ReqSkills={len(req_skills)}, PrefSkills={len(pref_skills)}")
        return profile


# Singleton Instance
role_requirement_analyzer = RoleRequirementAnalyzer()
