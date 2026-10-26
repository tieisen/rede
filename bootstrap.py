import os, subprocess, sys
from src.rede.database.database import verificarCriarBanco, criarTabelas

VENV_DIR = "venv"

def venvPython():
    """
        Retorna o caminho do python do venv (Scripts no Windows, bin nos demais).
    """

    return os.path.join(
        VENV_DIR,
        "Scripts" if os.name == "nt" else "bin",
        "python",
    )

def venvPip():
    """
        Retorna o caminho do pip do venv (Scripts no Windows, bin nos demais).
    """

    return os.path.join(
        VENV_DIR,
        "Scripts" if os.name == "nt" else "bin",
        "pip",
    )

def initDb():
    """
        Cria o arquivo SQLite e as tabelas.
    """

    verificarCriarBanco()
    criarTabelas()

def main():
    """
        Prepara o ambiente: na primeira execução cria o venv e instala as dependências,
        depois inicializa o banco.
    """

    if not os.path.exists(VENV_DIR):
        print("Criando ambiente virtual...")
        subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])

        print("Atualizando pip...")
        subprocess.check_call([venvPython(), "-m", "pip", "install", "--upgrade", "pip"])

        print("Instalando dependências...")
        subprocess.check_call([venvPip(), "install", "-e", "."])

    print("Iniciando banco de dados...")
    initDb()

    print("Ambiente pronto!")

if __name__ == "__main__":
    main()