from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List
from models.workflow import Workflow, WorkflowCreate, WorkflowRead
from db import get_session
from utils.logger import api_logger as logger

router = APIRouter(prefix="/workflows", tags=["Workflows"])

@router.get("", response_model=List[WorkflowRead])
async def list_workflows(session: Session = Depends(get_session)):
    try:
        workflows = session.exec(select(Workflow)).all()
        return workflows
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch workflows")

@router.post("", response_model=WorkflowRead)
async def create_workflow(workflow: WorkflowCreate, session: Session = Depends(get_session)):
    try:
        db_workflow = Workflow.model_validate(workflow)
        session.add(db_workflow)
        session.commit()
        session.refresh(db_workflow)
        return db_workflow
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create workflow: {e}")
        raise HTTPException(status_code=500, detail="Failed to create workflow")

@router.get("/{workflow_id}", response_model=WorkflowRead)
async def get_workflow(workflow_id: str, session: Session = Depends(get_session)):
    workflow = session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow

@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, session: Session = Depends(get_session)):
    workflow = session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    try:
        session.delete(workflow)
        session.commit()
        return {"status": "success", "message": "Workflow deleted"}
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete workflow")
