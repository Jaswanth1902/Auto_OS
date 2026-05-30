from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
import uuid

class ExecutionBase(SQLModel):
    status: str = Field(default="pending")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    workflow_id: Optional[str] = Field(default=None, foreign_key="workflow.id")

class Execution(ExecutionBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    workflow: Optional["Workflow"] = Relationship(back_populates="executions")

class ExecutionCreate(ExecutionBase):
    pass

class ExecutionRead(ExecutionBase):
    id: str
