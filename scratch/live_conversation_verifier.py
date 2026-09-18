"""Executes live verification across the 15 required conversational turns
against the active running backend http://127.0.0.1:8000/api/company/chat.
Prints detailed metrics: turn, message, department, intent, files, latency.
"""

import time
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def run_live_script():
    # 1. Check AI Status
    try:
        status_resp = requests.get(f"{BASE_URL}/api/company/ai/status", timeout=5)
        print("=== AI STATUS ===")
        print(json.dumps(status_resp.json(), indent=2))
    except Exception as e:
        print(f"Status check failed: {e}")
        return

    # Reset session first
    session_id = f"live_test_{int(time.time())}"
    requests.post(f"{BASE_URL}/api/company/chat/reset", json={"session_id": session_id}, timeout=5)

    turns = [
        # (turn_num, msg, role, custom_session)
        (1, "I'm from tech department", "EMPLOYEE", session_id),
        (2, "i have issue in my project", "EMPLOYEE", session_id),
        (3, "yes", "EMPLOYEE", session_id),
        (4, "node.js express app TypeError: Cannot read property 'map' of undefined in userController.js:42", "EMPLOYEE", session_id),
        (5, "where should I fix it", "EMPLOYEE", session_id),
        (6, "show me the corrected code", "EMPLOYEE", session_id),
        (7, "What is our casual leave policy?", "EMPLOYEE", session_id),
        (8, "can u give me more detailed", "EMPLOYEE", session_id),
        (9, "make me an excel document", "EMPLOYEE", session_id),
        (10, "add employee acknowledgement section", "EMPLOYEE", session_id),
        (11, "calculate 1200 + 800 + 250", "EMPLOYEE", session_id),
        (12, "add 500 more", "EMPLOYEE", session_id),
        (13, "compare these two excel files", "EMPLOYEE", session_id),
        (14, "make me an excel document", "EMPLOYEE", f"fresh_ambig_{int(time.time())}"),
        (15, "download server log stream and analyze errors", "HR_MANAGER", session_id),
    ]

    print("\n=== STARTING 15-TURN LIVE CONVERSATION SCRIPT ===")
    results = []

    for turn_num, msg, role, sess in turns:
        payload = {
            "message": msg,
            "session_id": sess,
            "user_role": role,
            "user_id": f"user_{role.lower()}"
        }
        t0 = time.time()
        resp = requests.post(f"{BASE_URL}/api/company/chat", json=payload, timeout=30)
        elapsed = time.time() - t0

        data = resp.json()
        dept = data.get("department")
        intent = data.get("intent")
        status = data.get("status")
        files = [f.get("filename") for f in data.get("files", [])]
        answer_preview = (data.get("answer") or "")[:120].replace("\n", " ")

        print(f"\n[TURN {turn_num:02d}] {elapsed:.3f}s | Dept={dept} | Intent={intent} | Status={status}")
        print(f"  User:   \"{msg}\" (Role={role})")
        print(f"  Answer: \"{answer_preview}...\"")
        if files:
            print(f"  Files:  {files}")

        results.append({
            "turn": turn_num,
            "message": msg,
            "role": role,
            "session": sess,
            "dept": dept,
            "intent": intent,
            "status": status,
            "elapsed_seconds": round(elapsed, 3),
            "files": files,
            "answer_preview": answer_preview
        })

    print("\n=== ALL 15 TURNS COMPLETE ===")
    with open("scratch/live_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_live_script()
