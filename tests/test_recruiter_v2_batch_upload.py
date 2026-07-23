"""Version 2 Multi-Resume Batch Upload Test Suite.

Verifies:
1. POST /api/v2/recruiter/upload_batch ingests multiple resumes simultaneously.
2. Independent resume processing: if one resume fails, remaining resumes process cleanly.
3. Candidate profiles generated from batch upload are indexed into CandidatePoolStore and ready for search & ranking.
4. Version 1 single resume upload API (POST /api/documents/upload) remains 100% operational and untouched.
"""

import io
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.recruiter.candidate_pool_store import candidate_pool_store

client = TestClient(app)

# Resumes must be >=30 words to pass document_parser validation
RESUME_TEXT_A = """
ALEX RIVERS
Email: alex@example.com
Phone: +91 9988776655
Address: Chennai, Tamil Nadu, India

PROFESSIONAL SUMMARY
Senior React Developer with 6 years of professional experience building high performance web applications 
using React, TypeScript, Redux, Next.js, and TailwindCSS. Strong expertise in frontend architecture, 
component driven design patterns, and modern JavaScript ecosystem.

TECHNICAL SKILLS
React, TypeScript, Redux, TailwindCSS, JavaScript, HTML5, CSS3, Next.js, Webpack, Jest, Cypress, Git, 
Node.js, REST API, GraphQL, Figma, Storybook

WORK EXPERIENCE

Senior React Developer | CloudSystems Private Limited | Chennai
June 2021 - Present
- Led frontend architecture for a SaaS analytics platform serving 10000 daily active users.
- Designed reusable component library with Storybook documentation and automated testing.
- Reduced page load times by 40 percent through code splitting and lazy loading optimization.
- Mentored a team of 4 junior React developers and conducted code reviews daily.

UI Engineer | WebTech Solutions Private Limited | Chennai
July 2018 - May 2021
- Developed responsive user interfaces for 3 enterprise client projects using React and Redux.
- Implemented pixel-perfect designs from Figma mockups with cross-browser compatibility.
- Created custom hooks and context providers reducing boilerplate code by 30 percent across projects.
- Collaborated with UX designers and backend engineers in agile sprint cycles.

EDUCATION
Bachelor of Technology in Computer Science and Engineering
Anna University, Chennai | 2014 - 2018 | CGPA: 8.5

CERTIFICATIONS
- AWS Certified Cloud Practitioner (2023)
- Meta Frontend Developer Professional Certificate (2022)

PROJECTS
- Open Source React Component Library with 500 GitHub stars
- Real-time collaborative whiteboard application using WebSocket and Canvas API
"""

RESUME_TEXT_B = """
SARA KHAN
Email: sara@example.com
Phone: +91 9876123456
Address: Bangalore, Karnataka, India

PROFESSIONAL SUMMARY
Backend Developer with 4 years of experience designing and building scalable microservices and RESTful APIs 
using Python, FastAPI, Django, and PostgreSQL. Proficient in containerized deployments with Docker and 
Kubernetes, and experienced in CI/CD pipelines with GitHub Actions and Jenkins.

TECHNICAL SKILLS
Python, FastAPI, Django, PostgreSQL, MySQL, Docker, Kubernetes, REST API, Redis, Celery, RabbitMQ, 
Git, Linux, AWS EC2, S3, Lambda, GitHub Actions, Jenkins, Pytest, SQLAlchemy

WORK EXPERIENCE

Backend Developer | DataCorp Technologies Private Limited | Bangalore
January 2020 - Present
- Designed and maintained microservices architecture serving 5 million API requests per day.
- Built asynchronous task processing pipelines using Celery and RabbitMQ for batch data ingestion.
- Implemented database migration strategies for PostgreSQL with zero downtime deployments.
- Reduced API response latency by 60 percent through Redis caching and query optimization.
- Authored comprehensive API documentation using OpenAPI specification and Swagger UI.

Junior Software Developer | StartupHub Solutions | Bangalore
June 2019 - December 2019
- Developed RESTful APIs for an e-commerce platform handling product catalog and order management.
- Wrote unit and integration tests achieving 90 percent code coverage using Pytest framework.
- Participated in daily standup meetings and sprint planning as part of agile development team.

EDUCATION
Bachelor of Engineering in Information Technology
Visvesvaraya Technological University (VTU), Bangalore | 2016 - 2020 | CGPA: 8.2

CERTIFICATIONS
- AWS Solutions Architect Associate (2023)
- Docker Certified Associate (2022)

PROJECTS
- High throughput data pipeline processing 10 million records daily using Apache Kafka
- Automated deployment platform with Terraform and Ansible for multi-cloud infrastructure
"""


class TestVersion2BatchUpload:

    @pytest.fixture(autouse=True)
    def reset_store(self):
        candidate_pool_store.clear()

    def test_single_resume_v1_upload_untouched(self):
        """Verify Version 1 single upload endpoint POST /api/documents/upload remains 100% operational."""
        file_bytes = RESUME_TEXT_A.encode("utf-8")
        response = client.post(
            "/api/documents/upload",
            files={"file": ("Alex_Rivers_Resume.txt", io.BytesIO(file_bytes), "text/plain")},
            data={"chunk_size": "500"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["filename"] == "Alex_Rivers_Resume.txt"

    def test_version_2_multiple_resume_batch_upload(self):
        """Verify Version 2 batch upload POST /api/v2/recruiter/upload_batch handles multiple files."""
        files = [
            ("files", ("Alex_Rivers_Resume.txt", io.BytesIO(RESUME_TEXT_A.encode("utf-8")), "text/plain")),
            ("files", ("Sara_Khan_Resume.txt", io.BytesIO(RESUME_TEXT_B.encode("utf-8")), "text/plain"))
        ]

        response = client.post("/api/v2/recruiter/upload_batch", files=files)
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["total_uploaded"] == 2
        assert data["processed_count"] == 2
        assert data["failed_count"] == 0
        assert len(data["results"]) == 2

        # Verify candidates are indexed into CandidatePoolStore
        assert candidate_pool_store.count() == 2

    def test_version_2_independent_error_handling(self):
        """Verify if one resume fails in a batch, remaining resumes continue processing cleanly."""
        files = [
            ("files", ("Valid_Alex.txt", io.BytesIO(RESUME_TEXT_A.encode("utf-8")), "text/plain")),
            ("files", ("Corrupt_Empty.txt", io.BytesIO(b"broken"), "text/plain")),
            ("files", ("Valid_Sara.txt", io.BytesIO(RESUME_TEXT_B.encode("utf-8")), "text/plain"))
        ]

        response = client.post("/api/v2/recruiter/upload_batch", files=files)
        assert response.status_code == 200
        data = response.json()

        assert data["total_uploaded"] == 3
        # Even if one file is empty/invalid, valid resumes must succeed
        assert data["processed_count"] >= 2
        assert data["failed_count"] >= 1
        assert candidate_pool_store.count() >= 2
