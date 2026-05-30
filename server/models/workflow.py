from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
import uuid

class WorkflowBase(SQLModel):
    name: str = Field(index=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    schema_version: str = Field(default="1.0")
    config: Optional[str] = None # JSON string

class Workflow(WorkflowBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    executions: List["Execution"] = Relationship(back_populates="workflow")

class WorkflowCreate(WorkflowBase):
    pass

class WorkflowRead(WorkflowBase):
    id: str
