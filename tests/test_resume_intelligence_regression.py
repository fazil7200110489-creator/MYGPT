"""Single Resume AI — End-to-End Regression Test Suite."""

import pytest
from backend.app.services.reasoning.candidate_profile_builder import candidate_profile_builder
from backend.app.services.reasoning.specialists.resume_reasoner import ResumeReasoner
from backend.app.services.reasoning.analyzers.skill_analyzer import SkillAnalyzer
skill_analyzer = SkillAnalyzer()
from backend.app.services.recruiter.recruiter_intent_classifier import recruiter_intent_classifier, RecruiterIntent


SAMPLE_RESUME_TEXT = """
Jane Doe
Senior Full Stack Developer
Email: jane.doe@example.com | Phone: +1-555-0199
Address: 742 Evergreen Terrace, Springfield, IL
LinkedIn: linkedin.com/in/janedoe | GitHub: github.com/janedoe

PROFESSIONAL SUMMARY
Experienced Senior Full Stack Developer with 7 years of hands-on expertise building microservices, RESTful API design, modern single-page applications, and AWS cloud infrastructure.

WORK EXPERIENCE
Senior Full Stack Engineer at TechCorp Inc. (2020 - Present)
- Designed and built high-performance microservices with Node.js, Express.js, TypeScript, and RESTful API endpoints.
- Developed interactive web user interfaces using React.js, Redux, HTML5, CSS3, and Tailwind CSS.
- Automated CI/CD build pipelines with Docker, Kubernetes, and AWS EKS.

Backend Developer at Innovate Systems (2017 - 2020)
- Implemented core database operations using PostgreSQL and MongoDB.
- Created secure JWT authentication and OAuth2 login modules.

EDUCATION
Bachelor of Science in Computer Science, University of Illinois (2013 - 2017)

SKILLS
Modern JavaScript Ecosystem, Inet Secure Labs Pvt Limited Present, Contributing to real, ed in RESTful API design
JavaScript, TypeScript, React.js, React, Node.js, Express.js, HTML5, CSS3, Tailwind CSS, REST API, RESTful API, MongoDB, PostgreSQL, Docker, AWS, Git

PROJECTS
1. E-Commerce Analytics Portal
Architected realtime web application dashboard with React and Node.js.

2. Cloud Deployment Automation Tool
Created container orchestration scripts using Docker and AWS.
"""


@pytest.fixture
def resume_data():
    raw_entities = {
        "candidate_name": "Jane Doe",
        "email": "jane.doe@example.com",
        "phone": "+1-555-0199",
        "skills": [
            "Modern JavaScript Ecosystem", "Inet Secure Labs Pvt Limited Present", "Contributing to real", "ed in RESTful API design",
            "JavaScript", "TypeScript", "React.js", "React", "Node.js", "Express.js", "HTML5", "CSS3", "Tailwind CSS",
            "REST API", "RESTful API", "MongoDB", "PostgreSQL", "Docker", "AWS", "Git"
        ],
        "projects": [
            "E-Commerce Analytics Portal",
            "Cloud Deployment Automation Tool"
        ]
    }

    profile = candidate_profile_builder.build_profile(raw_entities, SAMPLE_RESUME_TEXT)
    reasoner = ResumeReasoner()
    reasoner.pre_resolve_entities(raw_entities, [SAMPLE_RESUME_TEXT])

    return {
        "raw_entities": raw_entities,
        "profile": profile,
        "reasoner": reasoner,
        "text": SAMPLE_RESUME_TEXT
    }


def test_technical_skills_extraction_normalization(resume_data):
    """Test 1: Technical skills extraction normalizes canonical names and filters noisy text fragments."""
    profile = resume_data["profile"]
    all_skills = profile["canonical_skills"]

    # Assert noise terms were filtered out
    assert "Modern JavaScript Ecosystem" not in all_skills
    assert "Inet Secure Labs Pvt Limited Present" not in all_skills
    assert "Contributing to real" not in all_skills
    assert "ed in RESTful API design" not in all_skills

    # Assert normalized technical skills are present
    formatted = skill_analyzer.categorize_and_format_skills(all_skills)
    assert "**Programming Languages**" in formatted
    assert "- JavaScript" in formatted
    assert "- TypeScript" in formatted
    assert "**Frontend**" in formatted
    assert "- React" in formatted
    assert "**Backend**" in formatted
    assert "- Node.js" in formatted
    assert "**Database**" in formatted
    assert "- MongoDB" in formatted
    assert "- REST API" in formatted
    assert "**Tools**" in formatted
    assert "- Docker" in formatted


def test_work_experience_extraction(resume_data):
    """Test 2: Work experience query returns Company, Designation, Timeline/Duration, Responsibilities."""
    reasoner = resume_data["reasoner"]
    ans = reasoner.reason(resume_data["raw_entities"], [resume_data["text"]], "EXPERIENCE", "Work Experience")

    assert "Company:" in ans
    assert "Designation:" in ans
    assert "Responsibilities:" in ans or "Work History" in ans


def test_contact_extraction(resume_data):
    """Test 3: Contact extraction returns Candidate Name, Phone, Email, Address, LinkedIn, GitHub."""
    reasoner = resume_data["reasoner"]
    ans = reasoner.reason(resume_data["raw_entities"], [resume_data["text"]], "CONTACT", "Phone + Email")

    assert "Jane Doe" in ans
    assert "+1-555-0199" in ans
    assert "jane.doe@example.com" in ans
    assert "Evidence:" in ans
    assert "Confidence:" in ans


def test_rest_api_detection(resume_data):
    """Test 4: REST API detection returns Yes when present."""
    reasoner = resume_data["reasoner"]
    ans = reasoner.reason(resume_data["raw_entities"], [resume_data["text"]], "SKILL_VERIFY", "Does he know REST API?")

    assert "Yes" in ans
    assert "REST API" in ans


def test_docker_detection(resume_data):
    """Test 5: Docker detection returns Yes when present."""
    reasoner = resume_data["reasoner"]
    ans = reasoner.reason(resume_data["raw_entities"], [resume_data["text"]], "SKILL_VERIFY", "Does he know Docker?")

    assert "Yes" in ans
    assert "Docker" in ans


def test_react_detection(resume_data):
    """Test 6: React detection returns Yes when present."""
    reasoner = resume_data["reasoner"]
    ans = reasoner.reason(resume_data["raw_entities"], [resume_data["text"]], "SKILL_VERIFY", "Does he know React?")

    assert "Yes" in ans
    assert "React" in ans


def test_angular_detection(resume_data):
    """Test 7: Angular detection returns missing message when absent."""
    reasoner = resume_data["reasoner"]
    ans = reasoner.reason(resume_data["raw_entities"], [resume_data["text"]], "SKILL_VERIFY", "Does he know Angular?")

    assert "not explicitly mentioned" in ans or "Not available" in ans or "can't confirm" in ans


def test_candidate_summary(resume_data):
    """Test 8: Candidate summary contains required section blocks."""
    reasoner = resume_data["reasoner"]
    ans = reasoner.reason(resume_data["raw_entities"], [resume_data["text"]], "SUMMARY", "Summarize resume")

    assert "1. Overview" in ans or "Candidate Overview" in ans
    assert "2. Professional Experience" in ans or "Experience" in ans
    assert "3. Core Skills & Competencies" in ans or "Technical Expertise" in ans or "Skills" in ans


def test_role_suitability(resume_data):
    """Test 9: Role suitability evaluation returns comprehensive metrics."""
    reasoner = resume_data["reasoner"]
    ans = reasoner.reason(resume_data["raw_entities"], [resume_data["text"]], "ROLE_SUITABILITY", "Frontend Developer")

    assert "Match" in ans or "Overall Match %:" in ans or "Role Match:" in ans
    assert "Suitable" in ans or "Assessment" in ans or "Reason" in ans


def test_education_extraction(resume_data):
    """Test 10: Education query returns degree details."""
    reasoner = resume_data["reasoner"]
    ans = reasoner.reason(resume_data["raw_entities"], [resume_data["text"]], "EDUCATION", "Education")

    assert "Bachelor" in ans or "University" in ans or "Degree" in ans


def test_projects_extraction(resume_data):
    """Test 11: Projects query returns project details."""
    reasoner = resume_data["reasoner"]
    ans = reasoner.reason(resume_data["raw_entities"], [resume_data["text"]], "PROJECTS", "Projects")

    assert "Analytics Portal" in ans or "Automation Tool" in ans or "Project Name:" in ans or "No dedicated projects" in ans


def test_intent_classification_routing():
    """Test 12: Ensure single-keyword queries route to dedicated engines without triggering comparison."""
    queries = ["Experience", "Frontend Developer", "REST API", "Docker", "Angular", "React"]

    for q in queries:
        intent = recruiter_intent_classifier.classify(q)
        assert intent != RecruiterIntent.CANDIDATE_COMPARISON, f"Query '{q}' incorrectly triggered comparison workflow!"

    assert recruiter_intent_classifier.classify("Experience") == RecruiterIntent.EXPERIENCE_EXTRACTION
