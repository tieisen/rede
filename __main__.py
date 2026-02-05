import os, uvicorn
from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":

    host = os.getenv('HOST')
    port = os.getenv('PORT')
    if not any([host,port]):
        raise ValueError("Host/Port config not found")
    
    try:
        port = int(port)
    except:
        raise ValueError(f"Port type invalid. Expected int. Found {type(port)}")

    uvicorn.run(app="app:app",
                host=host,
                port=port,
                reload=True)
