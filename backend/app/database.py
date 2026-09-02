import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Overridable so a container can point the DB file at a mounted volume
# (see docker-compose.yml) instead of the ephemeral container filesystem.
DATABASE_URL = os.environ.get("LM_DATABASE_URL", "sqlite:///./legal_metrology.db")

if DATABASE_URL.startswith("sqlite:///"):
    # SQLite creates the file itself but not missing parent directories —
    # matters when LM_DATABASE_URL points into a freshly mounted volume
    # (e.g. Render's /data disk) that doesn't have the subfolder yet.
    _db_path = DATABASE_URL.removeprefix("sqlite:///")
    _db_dir = os.path.dirname(_db_path)
    if _db_dir:
        os.makedirs(_db_dir, exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
