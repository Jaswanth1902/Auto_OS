import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from main import app
from db import get_session

# Setup test DB
engine = create_engine("sqlite:///./test_autoflow_execs.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

def get_session_override():
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_session] = get_session_override
client = TestClient(app)

def test_create_and_stop_execution():
    payload = {
        "task": "Test task",
        "headless": True
    }
    create_res = client.post("/executions", json=payload)
    assert create_res.status_code == 200
    execution = create_res.json()
    assert "id" in execution
    assert execution["status"] == "pending"

    stop_res = client.post(f"/executions/{execution['id']}/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] in ["stopped", "not_found"]
