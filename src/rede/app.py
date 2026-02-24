import os
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.rede.controllers.api import router
from src.rede.services.scheduler import SchedulerService
from contextlib import asynccontextmanager
from src.rede.utils.log import set_logger
logger = set_logger(__name__)
load_dotenv()

api_title:str = os.getenv('API_TITLE')
api_description:str = os.getenv('API_DESCRIPTION')
api_version:str = os.getenv('API_VERSION')

if not any([api_title,api_description,api_version]):
    raise ValueError("API config not found.")

sch = SchedulerService()
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    sch.start_scheduler()
    yield
    # Shutdown code
    sch.stop_scheduler()

app = FastAPI(title=api_title,
              description=api_description,
              version=api_version,
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET","POST"],
    allow_headers=["*"],
)

app.include_router(router, tags=["API"])

@app.get("/",include_in_schema=False)
def read_root():
    return {"message": f"{api_title}. Version {api_version}."}

print(f"===>>API Boot@{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info(f"===>>API Boot@{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")