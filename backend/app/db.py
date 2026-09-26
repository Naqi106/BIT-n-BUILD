import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Try to load from current dir, and from backend/ if not found
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()

# Defaults to local SQLite for instant testing if PostgreSQL is not running
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./altomare.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI dependency yielding a per-request DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()