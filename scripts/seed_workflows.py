import sys
import os

# Add server to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "server"))

from db import create_db_and_tables, engine
from sqlmodel import Session, select
from models.workflow import Workflow

def seed_workflows():
    create_db_and_tables()

    workflows = [
        Workflow(name="Daily Standup Prep", description="Gathers recent Jira tickets and formats them into a daily summary", config="{}"),
        Workflow(name="Clear Temp Files", description="Removes system temporary files and cache folders to free up disk space", config="{}"),
    ]

    with Session(engine) as session:
        for wf in workflows:
            existing = session.exec(select(Workflow).where(Workflow.name == wf.name)).first()
            if not existing:
                session.add(wf)

        try:
            session.commit()
            print("Successfully seeded workflows.")
        except Exception as e:
            session.rollback()
            print(f"Failed to seed workflows: {e}")
            raise

if __name__ == "__main__":
    seed_workflows()
