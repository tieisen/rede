import os, logging
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

def buscar_path() -> str:
    """ Busca o caminho do log atual ou cria um novo caso não exista """

    path_atual:str = ''
    mes_atual:str = datetime.now().strftime('%Y%m')
    try:
        if not os.path.exists(f"./logs/{mes_atual}.log"):
            os.makedirs("./logs/", exist_ok=True)
            with open(f"./logs/{mes_atual}.log", "w") as f:
                pass
        path_atual = f"./logs/{mes_atual}.log"
    except Exception as e:
        print(f"Erro ao criar log: {e}")
    finally:
        pass
    return path_atual

def set_logger(name:str) -> logging:
    """
    Configura o logger.
        :param name: nome da função que está sendo executada
    """

    logger = logging.getLogger(name)
    logging.basicConfig(filename=buscar_path(),
                        encoding='utf-8',
                        format=os.getenv('LOGGER_FORMAT'),
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)
    return logger