import os, subprocess, venv

VENV_DIR = "venv"
REQ_FILE = "requirements.txt"

def criar_venv():
    print("Criando virtualenv...")
    venv.create(VENV_DIR, with_pip=True)

def pip_path():
    if os.name == "nt":  # Windows
        return os.path.join(VENV_DIR, "Scripts", "pip")
    return os.path.join(VENV_DIR, "bin", "pip")

def ler_requirements():
    if not os.path.isfile(REQ_FILE):
        return set()

    with open(REQ_FILE, "r", encoding="utf-8") as f:
        return {
            linha.strip()
            for linha in f
            if linha.strip() and not linha.startswith("#")
        }

def pacotes_instalados():
    resultado = subprocess.check_output(
        [pip_path(), "freeze"],
        text=True
    )
    return {linha.strip() for linha in resultado.splitlines()}

def dependencias_ok():
    reqs = ler_requirements()
    if not reqs:
        return True

    instalados = pacotes_instalados()
    faltando = reqs - instalados

    if faltando:
        print("Dependências faltando:")
        for pkg in faltando:
            print(f"  - {pkg}")
        return False

    return True

def instalar_dependencias():
    print("Instalando dependências...")
    subprocess.check_call([
        pip_path(),
        "install",
        "-r",
        REQ_FILE
    ])

def rodar_verificacao():
    if not venv_existe():
        criar_venv()
        instalar_dependencias()
    else:
        if not dependencias_ok():
            instalar_dependencias()

    print("Ambiente pronto!")

if __name__ == "__main__":
    rodar_verificacao()