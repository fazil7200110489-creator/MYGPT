"""Interview Question Generator — Dynamic Tailored Candidate Interview Scripts.

Generates custom interview questions across 4 categories:
1. Technical Deep-Dive (matching candidate's primary skills)
2. Architecture & Design (project experience & system architecture)
3. Skill Gap Verification (probing missing role skills)
4. Behavioral & Scenario-Based (problem-solving & teamwork)
"""

from typing import Dict, Any, List, Optional
from loguru import logger
from backend.app.services.recruiter.job_requirement_builder import RequirementProfile


class InterviewQuestionGenerator:
    """Generates tailored interview questions for candidate evaluation."""

    def generate_questions(
        self,
        candidate_record: Dict[str, Any],
        requirement_profile: RequirementProfile
    ) -> Dict[str, Any]:
        """Generate structured interview questions report."""
        candidate_record = candidate_record or {}
        profile = candidate_record.get("candidate_profile") or candidate_record
        cname = candidate_record.get("name") or profile.get("name", "Candidate")
        role = requirement_profile.target_role

        skills = profile.get("skills", [])
        matched_skills = [s for s in skills if any(req.lower() in s.lower() for req in requirement_profile.required_skills + requirement_profile.preferred_skills)]
        missing_skills = [req for req in requirement_profile.required_skills if not any(req.lower() in s.lower() for s in skills)]

        # 1. Technical Deep-Dive Questions
        tech_qs = []
        for sk in matched_skills[:3]:
            tech_qs.append({
                "question": f"Can you walk us through a complex project where you leveraged {sk}? What were the main performance optimizations or architectural decisions you made?",
                "evaluated_skill": sk,
                "expected_answer_guide": f"Candidate should explain hands-on implementation details, state management, or optimizations specific to {sk}."
            })

        if not tech_qs:
            tech_qs.append({
                "question": f"Describe your core technical workflow for {role} deliverables.",
                "evaluated_skill": "General Technical Proficiency",
                "expected_answer_guide": "Candidate should detail tools, frameworks, and testing methodologies used."
            })

        # 2. Architecture & Design Questions
        arch_qs = [
            {
                "question": f"How do you design scalable applications for high availability and clean modularity in a {role} environment?",
                "evaluated_topic": "System Design & Architecture",
                "expected_answer_guide": "Look for modular components, clear API abstractions, error handling, and scalable design patterns."
            },
            {
                "question": "Can you give an example of a difficult technical trade-off you had to make in a past project?",
                "evaluated_topic": "Technical Trade-offs",
                "expected_answer_guide": "Candidate should discuss evaluation criteria, trade-offs (e.g. speed vs complexity), and post-launch outcomes."
            }
        ]

        # 3. Skill Gap Verification Questions
        gap_qs = []
        for msk in missing_skills[:2]:
            gap_qs.append({
                "question": f"Our team makes heavy use of {msk}. Although it isn't explicitly highlighted on your resume, what experience or exposure do you have with {msk} or similar paradigms?",
                "evaluated_gap": msk,
                "expected_answer_guide": f"Assess candidate's adaptability and capability to quickly ramp up on {msk}."
            })

        if not gap_qs:
            gap_qs.append({
                "question": f"What new technologies or practices have you learned in the last 6 months to enhance your effectiveness as a {role}?",
                "evaluated_gap": "Continuous Learning",
                "expected_answer_guide": "Look for active self-improvement, side projects, or online learning."
            })

        # 4. Behavioral & Scenario Questions
        behavioral_qs = [
            {
                "question": "Describe a scenario where project requirements changed midway through execution. How did you adapt your plan and communicate with stakeholders?",
                "evaluated_trait": "Adaptability & Stakeholder Management",
                "expected_answer_guide": "Candidate should describe clear communication, prioritization, and agile response."
            },
            {
                "question": "How do you handle code reviews, construct feedback, and resolve technical disagreements within your engineering team?",
                "evaluated_trait": "Collaboration & Teamwork",
                "expected_answer_guide": "Look for empathy, emphasis on code quality standards, and constructive peer discussions."
            }
        ]

        report = {
            "candidate_name": cname,
            "target_role": role,
            "department": requirement_profile.department,
            "total_questions": len(tech_qs) + len(arch_qs) + len(gap_qs) + len(behavioral_qs),
            "question_categories": {
                "technical_deep_dive": tech_qs,
                "architecture_and_design": arch_qs,
                "skill_gap_verification": gap_qs,
                "behavioral_and_scenario": behavioral_qs
            }
        }

        logger.info(f"InterviewQuestionGenerator generated {report['total_questions']} interview questions for {cname}")
        return report


# Singleton Instance
interview_question_generator = InterviewQuestionGenerator()
