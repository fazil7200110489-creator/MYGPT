"""Unit tests for the FastAPI API server endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from src.server import app

client = TestClient(app)


def test_dashboard_endpoint():
    """Tests the dashboard statistics endpoint."""
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "model_name" in data
    assert "device" in data
    assert "vocab_size" in data


def test_tokenize_endpoint():
    """Tests the tokenization endpoint."""
    response = client.post("/api/tokenize", json={"text": "hello world"})
    assert response.status_code == 200
    data = response.json()
    assert "tokens" in data
    assert "ids" in data
    assert len(data["tokens"]) == len(data["ids"])


def test_vocabulary_endpoint():
    """Tests the vocabulary endpoint."""
    response = client.get("/api/vocabulary")
    assert response.status_code == 200
    data = response.json()
    assert "vocabulary" in data
    assert len(data["vocabulary"]) > 0


def test_dataset_endpoint():
    """Tests the dataset layout endpoint."""
    response = client.post("/api/dataset", json={"text": "the cat sat on the mat", "seq_len": 4})
    assert response.status_code == 200
    data = response.json()
    assert "samples" in data
    assert len(data["samples"]) > 0


def test_embedding_endpoint():
    """Tests the embedding inspector endpoint."""
    response = client.post("/api/embedding", json={"text": "hello"})
    assert response.status_code == 200
    data = response.json()
    assert "shape" in data
    assert "embeddings" in data


def test_attention_endpoint():
    """Tests the attention weights generator endpoint."""
    response = client.post("/api/attention", json={"text": "hello world"})
    assert response.status_code == 200
    data = response.json()
    assert "attention_weights" in data
    assert "tokens" in data
