import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(
    prefix="fairgate-tests-", suffix=".db"
)
os.environ["APP_MODE"] = "demo"
from fastapi.testclient import TestClient
import pytest
from backend.app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        yield c
