import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv

load_dotenv()


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


engine = create_engine(
    os.getenv("DATABASE_URL", "sqlite:///./backend/fairgate.db"),
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def configure_sqlite(connection, _):
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")


Session = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with Session() as db:
        yield db
