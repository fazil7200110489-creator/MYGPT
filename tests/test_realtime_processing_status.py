"""
Tests for Real-Time AI Processing Status Tracker and Task Event Endpoints.
Verifies stage transitions, event subscriptions, status snapshots, and error handling.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.processing_progress_tracker import (
    ProcessingProgressTracker,
    processing_progress_tracker,
)

client = TestClient(app)


def test_tracker_lifecycle_sync():
    """Verify start_task, update_stage, complete_task, and get_task_status."""
    tracker = ProcessingProgressTracker()
    task_id = "test_task_123"

    # 1. Start task
    init_data = tracker.start_task(
        task_id=task_id,
        task_type="tender_consultant",
        initial_stage="receiving_document",
        initial_message="Receiving tender document",
    )
    assert init_data["task_id"] == task_id
    assert init_data["current_stage"] == "receiving_document"
    assert init_data["status"] == "running"
    assert len(init_data["stages"]) == 1

    # 2. Update to next stages
    tracker.update_stage(
        task_id=task_id,
        stage="extracting_pdf",
        message="Extracting PDF content",
        status="running",
    )
    snap = tracker.get_task_status(task_id)
    assert snap is not None
    assert snap["current_stage"] == "extracting_pdf"
    assert len(snap["stages"]) == 2
    # Previous stage should be marked completed
    first_stage = next(s for s in snap["stages"] if s["stage"] == "receiving_document")
    assert first_stage["status"] == "completed"

    # 3. Complete task
    tracker.complete_task(
        task_id=task_id,
        final_stage="generating_response",
        message="Consultant briefing prepared",
    )
    final_snap = tracker.get_task_status(task_id)
    assert final_snap["status"] == "completed"
    assert final_snap["current_stage"] == "generating_response"


def test_tracker_failure_handling():
    """Verify task failure and error preservation."""
    tracker = ProcessingProgressTracker()
    task_id = "test_task_err"

    tracker.start_task(
        task_id=task_id,
        task_type="tender_analysis",
        initial_stage="validating_document",
        initial_message="Validating tender document",
    )

    tracker.fail_task(
        task_id=task_id,
        error_message="This document does not appear to be a tender. Tender analysis has not started.",
        stage="validating_document",
    )

    snap = tracker.get_task_status(task_id)
    assert snap["status"] == "failed"
    assert "This document does not appear to be a tender" in snap["error"]
    failed_stage = next(s for s in snap["stages"] if s["stage"] == "validating_document")
    assert failed_stage["status"] == "failed"


def test_task_status_endpoint():
    """Verify GET /api/company/tasks/{task_id}/status."""
    test_task_id = "api_task_test_999"
    processing_progress_tracker.start_task(
        task_id=test_task_id,
        task_type="chat_qa",
        initial_stage="understanding_question",
        initial_message="Understanding your question...",
    )

    response = client.get(f"/api/company/tasks/{test_task_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == test_task_id
    assert data["current_stage"] == "understanding_question"
    assert data["status"] == "running"

    # Non-existent task returns 404
    err_resp = client.get("/api/company/tasks/non_existent_random_id/status")
    assert err_resp.status_code == 404
