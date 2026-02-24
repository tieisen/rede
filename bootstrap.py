import os, subprocess, sys
from src.rede.database.database import verificar_criar_banco,criar_tabelas

VENV_DIR = "venv"

def venv_python():
    return os.path.join(
        VENV_DIR,
        "Scripts" if os.name == "nt" else "bin",
        "python",
    )

def venv_pip():
    return os.path.join(
        VENV_DIR,
        "Scripts" if os.name == "nt" else "bin",
        "pip",
    )

def init_db():
    verificar_criar_banco()
    criar_tabelas()

def main():
    if not os.path.exists(VENV_DIR):
        print("Criando ambiente virtual...")
        subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])

        print("Atualizando pip...")
        subprocess.check_call([venv_python(), "-m", "pip", "install", "--upgrade", "pip"])

        print("Instalando dependências...")
        subprocess.check_call([venv_pip(), "install", "-e", "."])

    print("Iniciando banco de dados...")
    init_db()

    print("Ambiente pronto!")

if __name__ == "__main__":
    main()