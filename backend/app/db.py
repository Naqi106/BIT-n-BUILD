import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

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