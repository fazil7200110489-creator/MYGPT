import os
import sys

# Add project root directory to path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from backend.app.services.reasoning_service import reasoning_service
from backend.app.services.answer_formatter import answer_formatter

def test_list_to_prose():
    print("Testing List-to-Prose conversion...")
    context = "• React\n• Node.js\n• PHP"
    # Test reasoning
    ans, conf = reasoning_service.reason(context, "What are the technologies?", intent="Technologies")
    print(f"Generated Ans:\n{ans}\n")
    assert "the document lists the following technologies: react, node.js, and php" in ans.lower()
    
    # Test formatting
    formatted = answer_formatter.format_response(ans, conf, [], intent="Technologies")
    print(f"Formatted Ans:\n{formatted['answer']}\n")
    assert "## Details" in formatted["answer"]
    assert "• React" in formatted["answer"]
    assert "• Node.js" in formatted["answer"]
    assert "• PHP" in formatted["answer"]
    print("[OK] List-to-Prose and list formatting checks passed.")

def test_dedup_words():
    print("Testing duplicate word elimination...")
    ans, conf = reasoning_service.reason("Here here is the policy details. probation probationary rules", "Explain probationary policy", intent="Policies")
    print(f"Generated Ans:\n{ans}\n")
    assert "here here" not in ans.lower()
    print("[OK] Duplicate word removal checks passed.")

def test_summary_intent():
    print("Testing Summary intent styling...")
    context = "This is sentence one. This is sentence two. This is sentence three."
    ans, conf = reasoning_service.reason(context, "Summarize this document.", intent="Summary")
    print(f"Generated Ans:\n{ans}\n")
    
    formatted = answer_formatter.format_response(ans, conf, [], intent="Summary")
    print(f"Formatted Ans:\n{formatted['answer']}\n")
    assert "## Summary" in formatted["answer"]
    print("[OK] Summary intent styling checks passed.")

if __name__ == "__main__":
    test_list_to_prose()
    test_dedup_words()
    test_summary_intent()
    print("All verify_reasoning tests passed!")
