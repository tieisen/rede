import os, uvicorn
from dotenv import load_dotenv
load_dotenv()

def main():
    """
        Inicia o servidor uvicorn com a aplicação rede.app:app em HOST/PORT do .env.

        Gera ValueError se HOST/PORT não estiverem configurados ou se PORT não for um número.
    """

    host = os.getenv('HOST')
    port = os.getenv('PORT')
    if not any([host,port]):
        raise ValueError("Host/Port config not found")
    
    try:
        port = int(port)
    except:
        raise ValueError(f"Port type invalid. Expected int. Found {type(port)}")

    uvicorn.run(app="rede.app:app",
                host=host,
                port=port)
    
if __name__ == "__main__":
    main()