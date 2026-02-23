import subprocess, sys, os

VENV_DIR = "venv"

def run():
    python_exec = os.path.join(
        VENV_DIR,
        "Scripts" if os.name == "nt" else "bin",
        "python.exe",
    )

    # Se venv não existe → bootstrap
    if not os.path.exists(python_exec):
        print("Ambiente não encontrado. Preparando projeto...")
        subprocess.check_call([sys.executable, "bootstrap.py"])

    # executa aplicação dentro do venv
    subprocess.check_call([python_exec, "-m", "rede.main"])

if __name__ == "__main__":
    run()