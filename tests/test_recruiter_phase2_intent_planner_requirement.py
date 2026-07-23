"""Phase 2 Verification Test Suite — Intent Classifier, Query Planner, Job Requirement Builder & Session Memory.

Verifies:
1. IntentClassifier pre-classifies queries into 10 canonical recruiter intents.
2. QueryPlanner translates natural language into multi-filter QueryPlan objects.
3. JobRequirementBuilder generates canonical RequirementProfile objects.
4. SessionMemory maintains conversational state across sequential turns.
"""

import pytest
from backend.app.services.recruiter.recruiter_intent_classifier import RecruiterIntent, recruiter_intent_classifier
from backend.app.services.recruiter.recruiter_query_planner import recruiter_query_planner
from backend.app.services.recruiter.job_requirement_builder import job_requirement_builder
from backend.app.services.recruiter.recruiter_session_memory import recruiter_session_memory


class TestPhase2IntentPlannerRequirement:

    def test_intent_classification_all_10_intents(self):
        """Verify queries are classified into canonical recruiter intents."""
        assert recruiter_intent_classifier.classify("Find React Developers") == RecruiterIntent.CANDIDATE_SEARCH
        assert recruiter_intent_classifier.classify("Rank candidates for Frontend Developer") == RecruiterIntent.CANDIDATE_RANKING
        assert recruiter_intent_classifier.classify("Compare Mohamed Fazil and Rahul") == RecruiterIntent.CANDIDATE_COMPARISON
        assert recruiter_intent_classifier.classify("Why is candidate 1 ranked first?") == RecruiterIntent.CANDIDATE_EXPLANATION
        assert recruiter_intent_classifier.classify("Give Mohamed Fazil's complete profile") == RecruiterIntent.CANDIDATE_PROFILE
        assert recruiter_intent_classifier.classify("Show only candidates with 5+ years experience from Chennai") == RecruiterIntent.CANDIDATE_FILTERING
        assert recruiter_intent_classifier.classify("Shortlist Mohamed Fazil") == RecruiterIntent.CANDIDATE_SHORTLISTING
        assert recruiter_intent_classifier.classify("Generate interview questions for Mohamed Fazil") == RecruiterIntent.INTERVIEW_QUESTION_GENERATION
        assert recruiter_intent_classifier.classify("Export shortlisted candidates to Excel") == RecruiterIntent.EXPORT
        assert recruiter_intent_classifier.classify("Show pool analytics and metrics") == RecruiterIntent.ANALYTICS

    def test_query_planner_complex_multi_filter_parsing(self):
        """Verify QueryPlanner converts multi-filter text into structured QueryPlan."""
        query = "Find top 5 React developers from Chennai having Docker and 3+ years experience"
        plan = recruiter_query_planner.plan_query(query)

        assert plan.intent == RecruiterIntent.CANDIDATE_SEARCH
        assert plan.target_role == "Frontend Developer"
        assert plan.limit == 5
        assert plan.location == "Chennai"
        assert plan.min_experience == 3.0
        assert "React" in plan.skills
        assert "Docker" in plan.skills

    def test_job_requirement_builder_structured_profile(self):
        """Verify JobRequirementBuilder builds RequirementProfile without direct resume comparisons."""
        query = "Find Frontend Developers with React and 3+ years experience"
        plan = recruiter_query_planner.plan_query(query)
        req_profile = job_requirement_builder.build_from_plan(plan)

        assert req_profile.target_role == "Frontend Developer"
        assert req_profile.department == "Technology Services"
        assert "JavaScript" in req_profile.required_skills
        assert "React" in req_profile.preferred_skills
        assert req_profile.min_experience_years == 3.0
        assert req_profile.weights["skill_weight"] == 4.0

    def test_recruiter_session_memory_state_retention(self):
        """Verify RecruiterSessionMemory remembers query context across sequential turns."""
        sid = "test_session_100"
        recruiter_session_memory.clear_session(sid)

        # Turn 1: Search
        plan1 = recruiter_query_planner.plan_query("Find Frontend Developers")
        req1 = job_requirement_builder.build_from_plan(plan1)
        recruiter_session_memory.add_turn(sid, "Find Frontend Developers", "CANDIDATE_SEARCH", plan1, req1, candidate_ids=["c1", "c2", "c3"])

        session = recruiter_session_memory.get_session(sid)
        assert session["active_target_role"] == "Frontend Developer"
        assert recruiter_session_memory.get_last_candidate_ids(sid) == ["c1", "c2", "c3"]

        # Turn 2: Follow-up filtering
        plan2 = recruiter_query_planner.plan_query("Show top 2")
        recruiter_session_memory.add_turn(sid, "Show top 2", "CANDIDATE_FILTERING", plan2, req1, candidate_ids=["c1", "c2"])

        assert recruiter_session_memory.get_last_candidate_ids(sid) == ["c1", "c2"]
        assert len(session["turns"]) == 2
