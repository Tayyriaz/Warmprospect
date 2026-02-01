"""
Database connection and session management.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/chatbot_db",
)

# Force synchronous psycopg2 driver (not asyncpg)
if DATABASE_URL.startswith("postgresql://") and "psycopg2" not in DATABASE_URL and "asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)

# Create engine
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models (SQLAlchemy 2.0+ style)
class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    """Get database session (for dependency injection)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
