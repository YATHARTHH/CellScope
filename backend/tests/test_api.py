import pytest
import io
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "model_version" in data
    assert "engine" in data

def test_security_headers():
    res = client.get("/api/v1/health")
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["X-Content-Type-Options"] == "nosniff"

def test_unsupported_file_extension():
    files = {"file": ("test.txt", b"hello", "text/plain")}
    res = client.post("/api/v1/segment", files=files)
    assert res.status_code == 422
