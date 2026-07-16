import pytest
from fastapi.testclient import TestClient
import os
from backend.app.main import app
from backend.app.core.config import settings

client = TestClient(app)


def test_model_config_endpoints():
    # Ensure any existing model_config.json is backed up or removed for the test
    config_path = os.path.join(settings.CHECKPOINT_DIR, "model_config.json")
    original_content = None
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            original_content = f.read()
        os.remove(config_path)

    try:
        # Test GET default config (should return 16, 16)
        response = client.get("/api/model/config")
        assert response.status_code == 200
        data = response.json()
        assert data["max_sequence_length"] == 16
        assert data["embedding_dimension"] == 16

        # Test POST config updates
        payload = {
            "max_sequence_length": 128,
            "embedding_dimension": 64
        }
        response = client.post("/api/model/config", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["config"]["max_sequence_length"] == 128
        assert data["config"]["embedding_dimension"] == 64

        # Test GET updated config (should return 128, 64)
        response = client.get("/api/model/config")
        assert response.status_code == 200
        data = response.json()
        assert data["max_sequence_length"] == 128
        assert data["embedding_dimension"] == 64

        # Test POST validation errors
        invalid_payload = {
            "max_sequence_length": 15,  # too low (min 16)
            "embedding_dimension": 64
        }
        response = client.post("/api/model/config", json=invalid_payload)
        assert response.status_code == 422

    finally:
        # Restore original config file
        if original_content is not None:
            os.makedirs(settings.CHECKPOINT_DIR, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(original_content)
        elif os.path.exists(config_path):
            os.remove(config_path)
