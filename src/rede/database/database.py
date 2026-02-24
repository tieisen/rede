from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

BASE_DIR = Path(__file__).resolve().parents[3]
DB_PATH = BASE_DIR / "src\\rede\\database\\db.sqlite"

DATABASE_URL = f"sqlite:///{DB_PATH}"

class Base(DeclarativeBase):
    pass

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)

def verificar_criar_banco():
    if not DB_PATH.exists():
        print("Criando banco SQLite de tokens...")
        DB_PATH.touch()


def criar_tabelas():
    from . import models  # registra models
    Base.metadata.create_all(bind=engine)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()