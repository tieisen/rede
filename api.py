from typing import Literal
from datetime import date
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, model_validator
from rede import *
load_dotenv()

class AutenticacaoModel(BaseModel):
    ambiente: Literal['trn', 'prd']
    pacote: Literal['pgto', 'vendas']
    auth:str

class LinkPagamentoModel(BaseModel):
    ambiente: Literal['trn', 'prd']
    paymentLinkId:str
    companyNumber:str
    body:dict

class VendasModel(BaseModel):
    ambiente:Literal['trn', 'prd']
    companyNumber:int
    startDate:date
    endDate:date
    
    @model_validator(mode="after")
    def validar_periodo(cls, model):
        if model.startDate > model.endDate:
            raise ValueError("startDate não pode ser maior que endDate")
        return model        

class VendasPgtoId(BaseModel):
    ambiente:Literal['trn', 'prd']
    token:str
    companyNumber:int
    paymentId:str

router = APIRouter()
security = HTTPBearer()

def validar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if (credentials.scheme != "Bearer") or (credentials.credentials is None) or (credentials.credentials == ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de autenticação inválido")
    return credentials.credentials

@router.get("/info", status_code=status.HTTP_200_OK)
async def info():
    return {
        "status": "API is running",
        "health": "API is healthy",
        "version": "1.0.0"
    }

@router.post("/auth/generate-token", status_code=status.HTTP_200_OK)
async def gerar_token(body:AutenticacaoModel) -> dict:
    res:dict={}
    auth = Autenticacao(
        ambiente=body.ambiente,
        pacote=body.pacote,
        auth=body.auth
    )
    try:
        res = auth.gerar_token()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        return res

@router.post("/vendas/consulta-parcelas", status_code=status.HTTP_200_OK)
async def consulta_parcelas(body:VendasModel, token:str=Depends(validar_token)) -> dict:
    res:dict={}
    vendas = Vendas()
    try:
        res = vendas.consultar_vendas_parceladas(
            ambiente=body.ambiente,
            token=token,
            companyNumber=body.companyNumber,
            startDate=body.startDate,
            endDate=body.endDate
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        return res

@router.post("/vendas/consulta-pgto-oc", status_code=status.HTTP_200_OK)
async def consulta_pagamentos_oc(body:VendasModel, token:str=Depends(validar_token)) -> dict:
    res:dict={}
    vendas = Vendas()        
    try:
        res = vendas.consultar_pagamentos_oc(
            ambiente=body.ambiente,
            token=token,
            companyNumber=body.companyNumber,
            startDate=body.startDate,
            endDate=body.endDate
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        return res

@router.post("/vendas/consulta-pgto-id", status_code=status.HTTP_200_OK)
async def consulta_pagamentos_id(body:VendasPgtoId, token: str = Depends(validar_token)) -> dict:
    res:dict={}
    vendas = Vendas()        
    try:
        res = vendas.consultar_pagamentos_id(
            ambiente=body.ambiente,
            token=token,
            companyNumber=body.companyNumber,
            paymentId=body.paymentId
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        return res
    