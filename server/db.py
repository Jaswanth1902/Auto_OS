import os
from sqlmodel import create_engine, Session, SQLModel

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./autoflow.db")
# By default, sqlite only allows one thread to access it at a time.
# But FastAPI runs concurrent requests. We must disable this check to avoid exceptions.
connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
