from pathlib import Path
from contextlib import contextmanager
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

def verificarCriarBanco():
    """
        Cria o arquivo SQLite (db.sqlite) caso ainda não exista.
    """

    if not DB_PATH.exists():
        print("Criando banco SQLite de tokens...")
        DB_PATH.touch()


def criarTabelas():
    """
        Cria as tabelas dos models registrados (tokens) caso ainda não existam.
    """

    from . import models  # registra models
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_session():
    """
        Context manager que abre uma sessão do SQLAlchemy e garante o fechamento ao final.

        Uso:
            with get_session() as session:
                ...
    """

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()