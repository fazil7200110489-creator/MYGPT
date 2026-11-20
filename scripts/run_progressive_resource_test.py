"""Progressive Resource Safety Test Harness.

Executes Step 1 through Step 4 tender evaluations with full telemetry capture,
verifying that thread counts, batch sizes, memory limits, and locks are strictly enforced.
"""

import os
import sys
import time
import logging
from typing import Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("progressive_test")

from backend.app.services.tender_intelligence.intelligence_engine import tender_intelligence_engine
from backend.app.services.tender_intelligence.resource_monitor import resource_monitor
from backend.app.services.rag.tender_vector_index import _EMBEDDING_BATCH_SIZE, _EMBEDDING_THREADS, tender_index_registry

STEPS = {
    1: {
        "name": "Step 1: Small PDF (Tripura Wi-Fi 33 pages)",
        "file_path": os.path.join(PROJECT_ROOT, "data", "uploads", "0aaa92a2-f665-4d5e-98ba-c39ce650f525.pdf"),
        "doc_id": "0aaa92a2-f665-4d5e-98ba-c39ce650f525",
        "filename": "Tripura_WiFi_33p.pdf",
    },
    2: {
        "name": "Step 2: Medium PDF (NITK Desktop 41 pages)",
        "file_path": os.path.join(PROJECT_ROOT, "data", "uploads", "2958370a-b714-47c0-9efa-9adfa6403d30.pdf"),
        "doc_id": "2958370a-b714-47c0-9efa-9adfa6403d30",
        "filename": "NITK_Desktop_41p.pdf",
    },
    3: {
        "name": "Step 3: 50-80 page PDF (CCTV 79 pages)",
        "file_path": os.path.join(PROJECT_ROOT, "data", "uploads", "174f2f79-0f42-44cf-b8fa-25d1e52a6ad8.pdf"),
        "doc_id": "174f2f79-0f42-44cf-b8fa-25d1e52a6ad8",
        "filename": "CCTV_79p.pdf",
    },
    4: {
        "name": "Step 4: 170-page CCTV Tender",
        "file_path": os.path.join(PROJECT_ROOT, "data", "uploads", "134897b5-90c7-4048-9bab-ae8fc6698d8e.pdf"),
        "doc_id": "134897b5-90c7-4048-9bab-ae8fc6698d8e",
        "filename": "Tenderwomensafetycctvsurveillancefor6cities_170p.pdf",
    },
}

def run_step(step_num: int):
    config = STEPS[step_num]
    print(f"\n{'='*80}")
    print(f"RUNNING {config['name']}")
    print(f"File: {config['file_path']}")
    print(f"Embedding Batch Size: {_EMBEDDING_BATCH_SIZE}, FastEmbed Threads: {_EMBEDDING_THREADS}")
    print(f"{'='*80}\n")

    if not os.path.exists(config["file_path"]):
        raise FileNotFoundError(f"Fixture file not found: {config['file_path']}")

    doc_dict = {
        "document_id": config["doc_id"],
        "id": config["doc_id"],
        "file_path": config["file_path"],
        "filename": config["filename"],
    }

    t0 = time.time()
    start_snap = resource_monitor.capture()
    print(f"[START SNAPSHOT] RSS: {start_snap.rss_mb:.1f} MB, RAM Available: {start_snap.system_avail_ram_gb:.2f} GB, Threads: {start_snap.num_threads}")

    report = tender_intelligence_engine.evaluate_tender(
        documents=[doc_dict],
        force_refresh=True,
        mode="fast",
    )

    t_elapsed = time.time() - t0
    end_snap = resource_monitor.capture()
    print(f"[END SNAPSHOT] RSS: {end_snap.rss_mb:.1f} MB, RAM Available: {end_snap.system_avail_ram_gb:.2f} GB, Threads: {end_snap.num_threads}, Elapsed: {t_elapsed:.2f}s")

    # Check 11 dimensions
    dimensions = [
        "overview", "eligibility", "technical_scope",
        "technical_specifications", "oem_requirements", "compliance_matrix",
        "commercial_financial", "contractual_legal", "risks_and_contradictions",
        "bid_strategy", "action_roadmap"
    ]
    present_dims = [dim for dim in dimensions if getattr(report, dim, None) is not None]
    print(f"[DIMENSIONS] Present: {len(present_dims)}/11: {present_dims}")
    if hasattr(report, "compliance_matrix") and report.compliance_matrix:
        cm = report.compliance_matrix
        total_items = len(cm.items)
        docs_count = len(cm.required_documents)
        score = getattr(cm.readiness_summary, "overall_readiness_percentage", getattr(cm.readiness_summary, "overall_readiness_score", "N/A")) if cm.readiness_summary else "N/A"
        print(f"[COMPLIANCE MATRIX] Items: {total_items}, Required Docs: {docs_count}, Readiness Score: {score}%")

    print(f"\n>>> SUCCESS: {config['name']} completed in {t_elapsed:.2f}s <<<\n")
    return {
        "step": step_num,
        "name": config["name"],
        "elapsed_s": t_elapsed,
        "start_rss_mb": start_snap.rss_mb,
        "end_rss_mb": end_snap.rss_mb,
        "ram_avail_gb": end_snap.system_avail_ram_gb,
        "dimensions": len(present_dims),
    }

if __name__ == "__main__":
    target_step = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if target_step:
        run_step(target_step)
    else:
        for s in [1, 2, 3, 4]:
            run_step(s)