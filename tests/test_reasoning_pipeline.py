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
    assert classifier.classify("Give me a list of programming languages") == "SKILLS"
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
    assert "Software Engineer" in str(ans)
    assert "Total experience: 4 years" in str(ans)

    # 10. Test Certifications default fallback string
    ans, conf, used = reasoning_service.reason(context=resume_text, question="What certifications does he have?", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert ans == "No certifications were found in the resume."

    # 11. Test Summary routing
    ans, conf, used = reasoning_service.reason(context=resume_text, question="Summarize the profile", retrieved_chunks=retrieved_chunks, doc_id=doc_id)
    assert "Navneet Priya is a professional" in ans

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
    assert "The uploaded document does not mention this" in ans_no
