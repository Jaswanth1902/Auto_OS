import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from main import app
from db import get_session

# Setup test DB
engine = create_engine("sqlite:///./test_autoflow.db", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

def get_session_override():
    with Session(engine) as session:
        yield session

app.dependency_overrides[get_session] = get_session_override
client = TestClient(app)

def test_create_and_list_workflow():
    payload = {
        "name": "Test Workflow",
        "description": "A workflow for tests"
    }
    create_res = client.post("/workflows", json=payload)
    assert create_res.status_code == 200
    workflow = create_res.json()
    assert workflow["name"] == "Test Workflow"

    list_res = client.get("/workflows")
    assert list_res.status_code == 200
    workflows = list_res.json()
    assert len(workflows) > 0
    assert any(wf["id"] == workflow["id"] for wf in workflows)
