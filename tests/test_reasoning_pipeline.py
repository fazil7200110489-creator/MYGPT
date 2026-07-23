import re
import pytest

from backend.app.services.reasoning.intent_classifier import IntentClassifier
from backend.app.services.reasoning.entity_relationship import EntityRelationshipResolver
from backend.app.services.reasoning.entity_extractor import EntityExtractor
from backend.app.services.reasoning.fact_extractor import FactExtractor
from backend.app.services.reasoning.context_reasoner import ContextReasoner
from backend.app.services.reasoning.answer_builder import AnswerBuilder
from backend.app.services.reasoning.validator import Validator
from backend.app.services.reasoning.formatter import Formatter

# Specialists
from backend.app.services.reasoning.specialists.resume_reasoner import ResumeReasoner
from backend.app.services.reasoning.specialists.invoice_reasoner import InvoiceReasoner
from backend.app.services.reasoning.specialists.excel_reasoner import ExcelReasoner
from backend.app.services.reasoning.specialists.policy_reasoner import PolicyReasoner
from backend.app.services.reasoning.specialists.research_reasoner import ResearchReasoner

def test_intent_classifier():
    classifier = IntentClassifier()
    # Test keywords/phrasings
    assert classifier.classify("What is his contact phone number?") == "PHONE"
    assert classifier.classify("Reach out to them on mobile") == "PHONE"
    assert classifier.classify("What is their gmail or email address?") == "EMAIL"
    assert classifier.classify("What skills does the applicant have?") == "SKILLS"
    assert classifier.classify("Give me a list of programming languages") in ["SKILLS", "PROGRAMMING_LANGUAGES"]
    assert classifier.classify("Tell me about the applications or systems built") == "PROJECTS"
    assert classifier.classify("What is the grand total due?") == "INVOICE_TOTAL"

def test_entity_relationship_resolver():
    resolver = EntityRelationshipResolver()
    
    # Mock pre-computed facts
    mock_facts = {
        "name": "Navneet Priya",
        "invoice_number": "INV-12345",
        "projects": ["ATS Resume Engine"]
    }
    from backend.app.services.knowledge_service import knowledge_store
    
    # Mock saving to knowledge store
    doc_id = "mock_test_doc_resolver"
    knowledge_store.save_knowledge(doc_id, {
        "document_type": "Resume",
        "facts": mock_facts,
        "entities": {"people": ["Navneet Priya"], "companies": []}
    })
    
    # Resolve candidate
    query = "What is his phone number?"
    resolved = resolver.resolve(query, "session_test", doc_id)
    assert "Navneet Priya" in resolved
    assert "his" not in resolved.lower()

    # Resolve project
    query = "What technologies did he use in that project?"
    resolved = resolver.resolve(query, "session_test", doc_id)
    assert "ATS Resume Engine" in resolved

def test_entity_extractor():
    extractor = EntityExtractor()
    text = "Navneet Priya, Email: navneet.priya80@gmail.com, Phone: 9263394143"
    entities = extractor.extract(text)
    assert entities["name"] == "Navneet Priya"
    assert "navneet.priya80@gmail.com" in entities["emails"]
    assert "9263394143" in entities["phones"]

def test_fact_extractor():
    extractor = FactExtractor()
    chunks = [
        {"text": "[Page 1 | Section: Content]\nNavneet is a developer. Navneet is a developer. Navneet worked at Google."},
        {"text": "Navneet worked at Google. Email is navneet@gmail.com"}
    ]
    facts = extractor.extract(chunks, "SUMMARY", query=None)
    # Verify duplicates are removed and page info is stripped
    assert "Navneet is a developer." in facts
    assert facts.count("Navneet is a developer.") == 1
    assert "Email is navneet@gmail.com" in facts

def test_context_reasoner():
    reasoner = ContextReasoner()
    facts = [
        "Joined Google in 2020",
        "Left Google in 2022",
        "Worked at Google as developer"
    ]
    synthesized = reasoner.reason(facts, "EXPERIENCE")
    # Verify merging and tenure spans computation
    assert any("career span" in f or "years" in f for f in synthesized)

def test_excel_specialist():
    specialist = ExcelReasoner()
    entities = {
        "tables": [{
            "headers": ["Transaction ID", "Amount", "Status"],
            "rows": [
                {"Transaction ID": "TXN001", "Amount": "100", "Status": "Success"},
                {"Transaction ID": "TXN002", "Amount": "250.50", "Status": "Success"},
                {"Transaction ID": "TXN003", "Amount": "50", "Status": "Failed"}
            ],
            "stats": {
                "Amount": {
                    "sum": 400.50,
                    "avg": 133.50,
                    "min": 50.0,
                    "max": 250.50,
                    "count": 3
                }
            }
        }]
    }

    # Verify len calculation
    assert specialist.reason(entities, [], "COUNT") == "3"
    # Verify sum calculation
    assert float(specialist.reason(entities, [], "TOTAL")) == 400.5
    # Verify avg calculation
    assert float(specialist.reason(entities, [], "AVERAGE")) == 133.5
    # Verify max calculation
    assert float(specialist.reason(entities, [], "HIGHEST")) == 250.5
    # Verify min calculation
    assert float(specialist.reason(entities, [], "LOWEST")) == 50.0

def test_answer_builder():
    builder = AnswerBuilder()
    
    # Phone format
    assert builder.build("9263394143", "PHONE", "Resume") == "9263394143"
    # Email format
    assert builder.build("navneet.priya80@gmail.com", "EMAIL", "Resume") == "navneet.priya80@gmail.com"
    # Skills format
    skills = ["Python", "JavaScript", "C++"]
    assert builder.build(skills, "SKILLS", "Resume") == "• Python\n• JavaScript\n• C++"
    # Projects format
    projects = ["ATS Engine", "LangMaster"]
    assert builder.build(projects, "PROJECTS", "Resume") == "1. ATS Engine\n2. LangMaster"
    # Summary format
    facts = ["He is a developer.", "He knows python."]
    assert builder.build(facts, "SUMMARY", "Resume") == "He is a developer. He knows python."

def test_validator_and_formatter():
    validator = Validator()
    formatter = Formatter()

    # Formatter word deduplication
    assert formatter.clean("SummarySummary ofof PythonPython DeveloperDeveloper") == "Summary of Python Developer"
    # Formatter preserves numbers, email, currency
    assert formatter.clean("Phone number is 9263394143 9263394143") == "Phone number is 9263394143 9263394143"
    assert formatter.clean("Email: navneet@gmail.com") == "Email: navneet@gmail.com"
    
    # Validator checks
    assert validator.validate("9263394143", "PHONE") is True
    assert validator.validate("invalid_phone", "PHONE") is False
    assert validator.validate("navneet@gmail.com", "EMAIL") is True
    assert validator.validate("• Skill", "SKILLS") is True

def test_resume_name_filtering_and_suggestions():
    from backend.app.services.knowledge_service import knowledge_builder, knowledge_store
    from backend.app.services.answer_formatter import answer_formatter
    from backend.app.services.reasoning_service import reasoning_service
    from backend.app.services.conversation_memory import conversation_memory

    # Text containing all key fields
    resume_text = (
        "Father's Name: Late Ram Sanehi\n"
        "Mother's Name: Sita Devi\n"
        "Navneet Priya\n"
        "Email: navneet@gmail.com\n"
        "Phone: 9263394143\n"
        "Address: 123 Main Street, Bangalore, Karnataka, 560001\n"
        "Technical Skills: Python, Java, Hardware Knowledge: Assembly\n"
        "Education: Bachelor of Computer Applications\n"
        "Experience: Software Engineer 2020-2024\n"
        "Projects: ATS Resume Engine, LangMaster\n"
    )
    knowledge = knowledge_builder.build_knowledge(resume_text, ".txt")
    
    # Assert candidate name, father/mother name, and address are extracted
    assert knowledge["candidate_name"] == "Navneet Priya"
    assert knowledge["father_name"] == "Late Ram Sanehi"
    assert knowledge["mother_name"] == "Sita Devi"
    assert "123 Main Street" in knowledge["address"]

    # Assert skills contains Assembly
    assert "Assembly" in knowledge["skills"]

    # Assert dynamic summary uses facts and is not a chunk copy
    assert "Navneet Priya is a professional" in knowledge["profile_summary"]
    assert "Bachelor of Computer Applications" in knowledge["profile_summary"]

    # Cache it in the mock store to verify suggested questions
    doc_id = "test_ref_doc_suggestions"
    knowledge_store.save_knowledge(doc_id, knowledge)

    retrieved_chunks = [{"doc_id": doc_id, "page_number": 1, "section": "Content", "text": resume_text}]
    response = answer_formatter.format_response("Navneet Priya details", 90.0, retrieved_chunks, "General")
    
    suggested = response["suggested_questions"]
    assert len(suggested) == 4
    assert any("Navneet Priya's work experience" in q for q in suggested)
    assert any("skills" in q.lower() for q in suggested)

    # 1. Test Candidate Name routing
    ans, conf, used = reasoning_service.reason(context=resume_text, question="What is the candidate's name?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert ans == "Navneet Priya"

    # 2. Test Father Name routing
    ans, conf, used = reasoning_service.reason(context=resume_text, question="What is the father's name?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Ram Sanehi" in ans

    # 3. Test Phone routing
    ans, conf, used = reasoning_service.reason(context=resume_text, question="What is the phone number?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "9263394143" in ans

    # 4. Test Email routing
    ans, conf, used = reasoning_service.reason(context=resume_text, question="What is the email address?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "navneet@gmail.com" in ans

    # 5. Test Address routing
    ans, conf, used = reasoning_service.reason(context=resume_text, question="What is the candidate address?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "123 Main Street" in ans

    # 6. Test Skills routing
    ans, conf, used = reasoning_service.reason(context=resume_text, question="What skills do they have?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Python" in str(ans)

    # 7. Test Education routing
    ans, conf, used = reasoning_service.reason(context=resume_text, question="What is their education?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Bachelor of Computer Applications" in str(ans)

    # 8. Test Projects routing
    ans, conf, used = reasoning_service.reason(context=resume_text, question="What projects have they done?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "ATS Resume Engine" in str(ans)

    # 9. Test Experience routing
    ans, conf, used = reasoning_service.reason(context=resume_text, question="What is their experience?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Software Engineer" in str(ans) or "Experience" in str(ans)

    # 10. Test Certifications default fallback string
    ans, conf, used = reasoning_service.reason(context=resume_text, question="What certifications does he have?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "certifications" in ans.lower() or "not mention" in ans.lower()

    # 11. Test Summary routing
    ans, conf, used = reasoning_service.reason(context=resume_text, question="Summarize the profile", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Navneet Priya" in ans

    # Test Formatter conversion to bullets instruction
    session_id = "test_format_conversion_session"
    conversation_memory.add_message(session_id, "user", "What is the candidate name?")
    conversation_memory.add_message(session_id, "assistant", "Navneet Priya")
    
    ans, conf, used = reasoning_service.reason(
        context=resume_text,
        question="Give me in points",
        retrieved_chunks=retrieved_chunks,
        doc_id=doc_id,
        session_id=session_id
    )
    assert ans == "• Navneet Priya"

    # Test Yes/No Question routing
    ans_yes, _, _ = reasoning_service.reason(
        context=resume_text,
        question="Did she study Python?",
        retrieved_chunks=retrieved_chunks,
        doc_id=doc_id
    )
    assert "Yes" in ans_yes

    # Test Absent Yes/No Question routing
    ans_no, _, _ = reasoning_service.reason(
        context=resume_text,
        question="Did she study at Honeywell?",
        retrieved_chunks=retrieved_chunks,
        doc_id=doc_id
    )
    assert "does not mention" in ans_no.lower() or "no" in ans_no.lower()


def test_conversational_reasoning_v2_3():
    from backend.app.services.knowledge_service import knowledge_builder, knowledge_store
    from backend.app.services.reasoning_service import reasoning_service

    resume_text = (
        "Name: Navneet Priya\n"
        "Email: navneet@gmail.com\n"
        "Phone: 9263394143\n"
        "Address: 123 Main Street, Bangalore, Karnataka, 560001\n"
        "Designation: Software Engineer\n"
        "Languages Known: English, Tamil, Hindi\n"
        "Skills: Python, Yii2, Angular 4, Flask, PostgreSQL, Git\n"
        "Education: Bachelor of Computer Applications from ABC College (2020-2023)\n"
        "Experience: Software Engineer at Google (2023-2026)\n"
        "Projects: ATS Resume Engine, LangMaster\n"
    )
    knowledge = knowledge_builder.build_knowledge(resume_text, ".txt")
    doc_id = "test_doc_v2_3"
    knowledge_store.save_knowledge(doc_id, knowledge)
    retrieved_chunks = [{"doc_id": doc_id, "page_number": 1, "section": "Content", "text": resume_text}]

    # 1. Test Basic Details
    ans, _, _ = reasoning_service.reason(context=resume_text, question="Basic details", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Navneet Priya" in ans
    assert "Software Engineer" in ans
    assert any(yr in ans for yr in ["3 Year", "3 years", "Years"])
    assert "navneet@gmail.com" in ans

    # 2. Test Frameworks extract (via SKILLS intent with frameworks query)
    ans, _, _ = reasoning_service.reason(context=resume_text, question="What frameworks does he know?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Yii2" in ans
    assert "Angular 4" in ans
    assert "Flask" in ans
    assert "Python" not in ans

    # 3. Test Human Languages
    ans, _, _ = reasoning_service.reason(context=resume_text, question="What languages does she speak?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "English" in ans
    assert "Tamil" in ans
    assert "Hindi" in ans
    assert "Python" not in ans

    # 4. Test Programming Languages
    ans, _, _ = reasoning_service.reason(context=resume_text, question="What programming languages does he know?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Python" in ans
    assert "English" not in ans

    # 5. Test Current Company & Designation
    ans, _, _ = reasoning_service.reason(context=resume_text, question="What is his current company?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Google" in ans

    ans, _, _ = reasoning_service.reason(context=resume_text, question="What is his job role?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Software Engineer" in ans

    # 6. Test Unknown / Personal Inference Zero-tolerance
    ans_gender, _, _ = reasoning_service.reason(context=resume_text, question="Is he male or female?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "does not mention this information" in ans_gender

    ans_salary, _, _ = reasoning_service.reason(context=resume_text, question="What is his salary?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "does not mention this information" in ans_salary

    ans_notice, _, _ = reasoning_service.reason(context=resume_text, question="What is his notice period?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "does not mention this information" in ans_notice

    # 7. Test Inferable / Derived Questions without thresholds
    ans_exp, _, _ = reasoning_service.reason(context=resume_text, question="Is he experienced?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "3 years" in ans_exp

    ans_grad, _, _ = reasoning_service.reason(context=resume_text, question="Is he graduated?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Yes" in ans_grad and "Bachelor of Computer Applications" in ans_grad


def test_composite_questions():
    from backend.app.services.knowledge_service import knowledge_builder, knowledge_store
    from backend.app.services.reasoning_service import reasoning_service

    resume_text = (
        "Name: Navneet Priya\n"
        "Email: navneet@gmail.com\n"
        "Phone: 9263394143\n"
        "Address: 123 Main Street, Bangalore, Karnataka, 560001\n"
        "Designation: Software Engineer\n"
        "Skills: Python, Yii2, Angular 4\n"
        "Education: Bachelor of Computer Applications from ABC College (2020-2023)\n"
        "Experience: Software Engineer at Google (2023-2026)\n"
        "Projects: ATS Resume Engine, LangMaster\n"
    )
    knowledge = knowledge_builder.build_knowledge(resume_text, ".txt")
    doc_id = "test_doc_composite"
    knowledge_store.save_knowledge(doc_id, knowledge)
    retrieved_chunks = [{"doc_id": doc_id, "page_number": 1, "section": "Content", "text": resume_text}]

    # 1. Test Name + Email + Phone (ordered)
    ans, _, _ = reasoning_service.reason(context=resume_text, question="Name, email and phone", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Candidate Name\nNavneet Priya" in ans
    assert "Email\nnavneet@gmail.com" in ans
    assert "Phone\n9263394143" in ans
    name_pos = ans.find("Candidate Name")
    email_pos = ans.find("Email")
    phone_pos = ans.find("Phone")
    assert name_pos < email_pos < phone_pos

    # 2. Test User-specified ordering: Phone, name, email
    ans_order, _, _ = reasoning_service.reason(context=resume_text, question="Phone, name, email", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    name_pos2 = ans_order.find("Candidate Name")
    email_pos2 = ans_order.find("Email")
    phone_pos2 = ans_order.find("Phone")
    assert phone_pos2 < name_pos2 < email_pos2

    # 3. Test Experience + Education
    ans_exp_edu, _, _ = reasoning_service.reason(context=resume_text, question="Experience and education", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Experience\n" in ans_exp_edu
    assert "Education\n" in ans_exp_edu
    assert "Software Engineer" in ans_exp_edu
    assert "Bachelor of Computer Applications" in ans_exp_edu

    # 4. Test Projects + Skills + Certifications (where Certifications is fallback)
    ans_proj_skills_cert, _, _ = reasoning_service.reason(context=resume_text, question="Projects, skills and certifications", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Key Projects (2)\n" in ans_proj_skills_cert
    assert "Skills\n" in ans_proj_skills_cert
    assert "Certifications\n" in ans_proj_skills_cert
    assert "ATS Resume Engine" in ans_proj_skills_cert
    assert "Python" in ans_proj_skills_cert
    assert "certifications" in ans_proj_skills_cert.lower() and ("not mention" in ans_proj_skills_cert.lower() or "found" in ans_proj_skills_cert.lower())

    # 5. Test Basic Details (single intent, remains unchanged)
    ans_basic, _, _ = reasoning_service.reason(context=resume_text, question="Basic details", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Name:\nNavneet Priya" in ans_basic

    # 6. Test Partial failures (Name, email and salary where salary has fallback)
    ans_fail, _, _ = reasoning_service.reason(context=resume_text, question="Name, email and salary", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Candidate Name\nNavneet Priya" in ans_fail
    assert "Email\nnavneet@gmail.com" in ans_fail
    assert "does not mention this information" in ans_fail

    # 7. Test Duplicate requested entities: Name + Email + Name
    ans_dup, _, _ = reasoning_service.reason(context=resume_text, question="What is his name and email and name?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert ans_dup.count("Candidate Name") == 1
    assert ans_dup.count("Email") == 1


def test_reasoning_consistency_v2_4():
    from backend.app.services.knowledge_service import knowledge_builder, knowledge_store
    from backend.app.services.reasoning_service import reasoning_service

    resume_text = (
        "Name: Navneet Priya\n"
        "Email: navneet@gmail.com\n"
        "Phone: 9263394143\n"
        "Address: 123 Main Street, Bangalore, Karnataka, 560001\n"
        "Designation: Software Engineer\n"
        "Skills: Python, Yii2, Angular 4\n"
        "Education: Bachelor of Computer Applications from ABC College (2020-2023)\n"
        "Experience: Software Engineer at Google (2023-2026)\n"
        "Projects: ATS Resume Engine, LangMaster\n"
    )
    knowledge = knowledge_builder.build_knowledge(resume_text, ".txt")
    doc_id = "test_doc_consistency_v2_4"
    knowledge_store.save_knowledge(doc_id, knowledge)
    retrieved_chunks = [{"doc_id": doc_id, "page_number": 1, "section": "Content", "text": resume_text}]

    # 1. Verify dynamic confidence calculations
    ans_composite, conf_composite, _ = reasoning_service.reason(context=resume_text, question="Projects, skills and certifications", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert 25.0 <= conf_composite <= 99.0
    ans_single, conf_single, _ = reasoning_service.reason(context=resume_text, question="What is his name?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert 25.0 <= conf_single <= 99.0

    # 2. Verify section list counts
    assert "Key Projects (2)\n" in ans_composite

    # 3. Verify single source of truth entity store consistency
    ans_summary, _, _ = reasoning_service.reason(context=resume_text, question="Summarize the profile", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    ans_basic_detail, _, _ = reasoning_service.reason(context=resume_text, question="Basic details", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    
    assert "Software Engineer" in ans_summary
    assert "Software Engineer" in ans_basic_detail
    assert any(yr in ans_summary for yr in ["3 Year", "3 years", "Years"])
    assert any(yr in ans_basic_detail for yr in ["3 Year", "3 years", "Years"])


def test_conversational_entity_aggregation_v2_6():
    from backend.app.services.knowledge_service import knowledge_builder, knowledge_store
    from backend.app.services.reasoning_service import reasoning_service

    resume_text = (
        "Name: Navneet Priya\n"
        "Email: navneet@gmail.com\n"
        "Phone: 9263394143\n"
        "Address: 123 Main Street, Bangalore, Karnataka, 560001\n"
        "Designation: Software Engineer\n"
        "Skills: Python, Yii2, Angular 4\n"
        "Languages: English, Hindi\n"
        "Education: Bachelor of Computer Applications from ABC College (2020-2023)\n"
        "Experience: Software Engineer at Google (2023-2026)\n"
        "Projects: ATS Resume Engine, LangMaster\n"
    )
    knowledge = knowledge_builder.build_knowledge(resume_text, ".txt")
    doc_id = "test_doc_conversational_v2_6"
    knowledge_store.save_knowledge(doc_id, knowledge)
    retrieved_chunks = [{"doc_id": doc_id, "page_number": 1, "section": "Content", "text": resume_text}]

    # 1. Name + Email + Phone
    ans, _, _ = reasoning_service.reason(context=resume_text, question="Name, email and phone", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Candidate Name\nNavneet Priya" in ans
    assert "Email\nnavneet@gmail.com" in ans
    assert "Phone\n9263394143" in ans

    # 2. Education + Languages
    ans, _, _ = reasoning_service.reason(context=resume_text, question="Education and languages", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Education\n" in ans
    assert "Languages\n" in ans
    assert "English" in ans

    # 3. Projects + Skills
    ans, _, _ = reasoning_service.reason(context=resume_text, question="Projects and skills", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Key Projects (2)\n" in ans
    assert "Skills\n" in ans
    assert "Python" in ans

    # 4. Basic Details (composite/legacy hybrid)
    ans, _, _ = reasoning_service.reason(context=resume_text, question="Basic details", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Name:\nNavneet Priya" in ans or "Candidate Name\nNavneet Priya" in ans
    assert "Designation\nSoftware Engineer" in ans or "Designation:\nSoftware Engineer" in ans
    assert "Address\n123 Main Street" in ans or "Location:\n123 Main Street" in ans
    assert "Experience" in ans
    assert "Education" in ans

    # 5. Contact Details (grouped)
    ans, _, _ = reasoning_service.reason(context=resume_text, question="Contact details", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Candidate Information" in ans or "Navneet Priya" in ans
    assert "Email: navneet@gmail.com" in ans or "navneet@gmail.com" in ans
    assert "Phone: 9263394143" in ans or "9263394143" in ans

    # 6. Academic Details (grouped)
    ans, _, _ = reasoning_service.reason(context=resume_text, question="Academic details", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Education\n" in ans
    assert "Certifications\n" in ans

    # 7. Technical Profile (grouped)
    ans, _, _ = reasoning_service.reason(context=resume_text, question="Technical profile", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Skills\n" in ans
    assert "Programming Languages\n" in ans
    assert "Key Projects (2)\n" in ans

    # 8. Mixed existing and missing entities
    ans, _, _ = reasoning_service.reason(context=resume_text, question="Name, email and salary", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Candidate Name\nNavneet Priya" in ans
    assert "Email\nnavneet@gmail.com" in ans
    assert "Salary" in ans and "does not mention" in ans

    # 9. Repeated entities
    ans, _, _ = reasoning_service.reason(context=resume_text, question="What is his name and email and name?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert ans.count("Candidate Name") == 1
    assert ans.count("Email") == 1

    # 10. Natural language grouped requests
    ans, _, _ = reasoning_service.reason(context=resume_text, question="Give me technical profile and contact details", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Skills" in ans
    assert "Candidate Information" in ans or "Candidate Name" in ans
    skills_pos = ans.find("Skills")
    contact_pos = ans.find("Candidate Information") if "Candidate Information" in ans else ans.find("Candidate Name")
    assert skills_pos < contact_pos


def test_conversational_query_understanding_v2_7():
    """v2.7 – Conversational Query Understanding regression tests."""
    from backend.app.services.reasoning.intent_classifier import IntentClassifier
    from backend.app.services.reasoning.entity_extractor import EntityExtractor
    from backend.app.services.reasoning.specialists.resume_reasoner import ResumeReasoner
    from backend.app.services.reasoning_service import ReasoningService

    classifier = IntentClassifier()
    extractor  = EntityExtractor()
    reasoner   = ResumeReasoner()

    # ── 1. Spell correction: "ksills" → "skills" ─────────────────────────────
    assert "SKILLS" in classifier.classify_multi("ksills"), \
        "'ksills' should be spell-corrected to 'skills' and resolve to SKILLS"

    # ── 2. Phrase normalization: "phone no" → PHONE ──────────────────────────
    assert "PHONE" in classifier.classify_multi("phone no"), \
        "'phone no' should normalize to 'phone number' and resolve to PHONE"

    # ── 3. Phrase normalization: "mail id" → EMAIL ───────────────────────────
    assert "EMAIL" in classifier.classify_multi("mail id"), \
        "'mail id' should normalize to 'email' and resolve to EMAIL"

    # ── 4. Phrase normalization: "linked inn" → not classified as random intent
    intents_li = classifier.classify_multi("linked inn")
    # Should NOT return an obviously wrong intent (e.g. it normalizes to linkedin)
    assert "UNKNOWN_QUERY" not in intents_li or len(intents_li) == 1, \
        "'linked inn' should normalize cleanly"

    # ── 5. Spell correction: "pthon" → "python" before tech detection ────────
    preprocessed = classifier._preprocess_query("pthon")
    assert "python" in preprocessed, \
        "'pthon' should be corrected to 'python' by _preprocess_query"

    # ── 6. Phrase normalization: "qualification" → EDUCATION ─────────────────
    assert "EDUCATION" in classifier.classify_multi("what are her qualifications"), \
        "'qualifications' should normalize to 'education' and resolve to EDUCATION"

    # ── 7. Technology yes/no – "did she know python" (Python in skills) ──────
    resume_text_py = (
        "Name: Priya\n"
        "Skills: Python, React, Django\n"
        "Projects: PriceTracker, InventoryApp\n"
        "Experience: Software Developer at TechCorp (2022-2025)\n"
    )
    from backend.app.services.knowledge_service import knowledge_builder, knowledge_store
    knowledge_py = knowledge_builder.build_knowledge(resume_text_py, ".txt")
    doc_py = "test_v2_7_py"
    knowledge_store.save_knowledge(doc_py, knowledge_py)
    entities_py = extractor.extract(resume_text_py, knowledge_py)
    facts_py = ["Skills: Python, React, Django", "Experience: Software Developer at TechCorp (2022-2025)"]
    ans_py = reasoner.reason(entities_py, facts_py, "SKILLS", question="did she know python")
    assert "yes" in ans_py.lower(), \
        f"Expected 'Yes' answer for 'did she know python', got: {ans_py}"
    assert "python" in ans_py.lower(), \
        f"Expected Python to be mentioned in yes/no answer, got: {ans_py}"

    # ── 8. Technology yes/no – "did she got IBM" (IBM as cert, not a skill) ──
    resume_text_ibm = (
        "Name: Priya\n"
        "Skills: Python, React\n"
        "Certifications: IBM Data Science Professional Certificate\n"
        "Experience: Software Developer at TechCorp (2022-2025)\n"
    )
    knowledge_ibm = knowledge_builder.build_knowledge(resume_text_ibm, ".txt")
    doc_ibm = "test_v2_7_ibm"
    knowledge_store.save_knowledge(doc_ibm, knowledge_ibm)
    entities_ibm = extractor.extract(resume_text_ibm, knowledge_ibm)
    facts_ibm = ["Certifications: IBM Data Science Professional Certificate"]
    ans_ibm = reasoner.reason(entities_ibm, facts_ibm, "CERTIFICATIONS", question="did she got IBM")
    # IBM should be found (it's in certifications corpus) but NOT assumed a technology
    assert "yes" in ans_ibm.lower(), \
        f"Expected 'Yes' for IBM (it's in resume), got: {ans_ibm}"
    # Should NOT say "experience with" for a cert
    assert "certification" in ans_ibm.lower() or "ibm" in ans_ibm.lower(), \
        f"Expected IBM to be mentioned correctly, got: {ans_ibm}"

    # ── 9. Unknown query: "love" → fallback message ───────────────────────────
    reasoning_svc = ReasoningService()
    resume_text_gen = (
        "Name: Navneet Priya\n"
        "Email: navneet@gmail.com\n"
        "Phone: 9263394143\n"
        "Skills: Python, Yii2\n"
        "Education: BCA from ABC College (2020-2023)\n"
        "Experience: Software Engineer at Google (2023-2026)\n"
    )
    knowledge_gen = knowledge_builder.build_knowledge(resume_text_gen, ".txt")
    doc_gen = "test_v2_7_gen"
    knowledge_store.save_knowledge(doc_gen, knowledge_gen)
    retrieved_gen = [{"text": resume_text_gen, "doc_id": doc_gen}]
    ans_love, conf_love, _ = reasoning_svc.reason(
        context=resume_text_gen,
        question="love",
        retrieved_chunks=retrieved_gen,
        doc_id=doc_gen
    )
    assert "does not mention" in ans_love.lower() or "not contain" in ans_love.lower(), \
        f"'love' should trigger graceful missing info fallback, got: {ans_love}"
    assert conf_love in [0.0, 99.0], \
        f"Confidence for unknown query should be 0.0 or 99.0, got: {conf_love}"

    # ── 10. Contact extraction – LinkedIn and GitHub OCR tolerance ────────────
    text_contacts = (
        "Name: Dev Sharma\n"
        "LinkedIn: linkedin.com/in/devsharma\n"
        "GitHub: github.com/devsharma\n"
        "Phone: +91 98765 43210\n"
        "Email: dev.sharma@example.com\n"
    )
    entities_c = extractor.extract(text_contacts)
    assert entities_c.get("linkedin") == "devsharma", \
        f"Expected LinkedIn handle 'devsharma', got: {entities_c.get('linkedin')}"
    assert entities_c.get("github") == "devsharma", \
        f"Expected GitHub handle 'devsharma', got: {entities_c.get('github')}"
    # Phone should be normalized (digits only + optional +)
    phones_c = entities_c.get("phones", [])
    assert any(re.search(r'9876543210', p) for p in phones_c), \
        f"Expected normalized phone, got: {phones_c}"
