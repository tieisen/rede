from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import router
from log import set_logger
logger = set_logger(__name__)
load_dotenv()

api_title:str = 'API_TITLE'
api_description:str = 'API_DESCRIPTION'
api_version:str = 'API_VERSION'

app = FastAPI(title=api_title,
                description=api_description,
                version=api_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite qualquer origem
    allow_credentials=True,
    allow_methods=["GET","POST"],  # Permite todos os métodos HTTP
    allow_headers=["*"],  # Permite todos os headers
)

app.include_router(router, tags=["API"])

@app.get("/",include_in_schema=False)
def read_root():
    return {"message": f"{api_title}. Version {api_version}."}

print(f"\n====================================")
print(f"===> START AT: {datetime.now().strftime("%d/%m/%Y, %H:%M:%S")}")
print(f"====================================\n")
logger.info(f"===>>API Boot@{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")