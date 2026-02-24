from typing import Literal
from datetime import date
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Response, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, model_validator
from src.rede.services.rede import *
from src.rede.services.rotina import Rotina
load_dotenv()

COMPANY_NUMBER_LIST = [int(x) for x in os.getenv("COMPANY_NUMBER_LIST", "").split(",") if x.isdigit()]

class AutenticacaoModel(BaseModel):
    ambiente: Literal['trn', 'prd']
    pacote: Literal['pgto', 'vendas']
    auth:str

class LinkPagamentoModel(BaseModel):
    ambiente: Literal['trn', 'prd']
    paymentLinkId:str
    companyNumber:str
    body:dict

    @model_validator(mode="after")
    def validar_companynumber(cls, model):
        if model.companyNumber not in COMPANY_NUMBER_LIST:
            raise ValueError("companyNumber inválido")
        return model

class VendasModel(BaseModel):
    ambiente:Literal['trn', 'prd']
    companyNumber:int
    nsu:int=None
    startDate:date
    endDate:date
    
    @model_validator(mode="after")
    def validar_periodo(cls, model):
        if model.startDate > model.endDate:
            raise ValueError("startDate não pode ser maior que endDate")
        return model        
    
    @model_validator(mode="after")
    def validar_nsu(cls, model):
        if model.nsu is not None and len(str(model.nsu)) < 9:
            raise ValueError("nsu inválido")
        return model        
    
    @model_validator(mode="after")
    def validar_companynumber(cls, model):
        if model.companyNumber not in COMPANY_NUMBER_LIST:
            raise ValueError("companyNumber inválido")
        return model        

class RotinaVendaModel(BaseModel):
    companyNumber:int
    startDate:date
    endDate:date
    financeiro:list[dict]
    nsu:int=None
    
    @model_validator(mode="after")
    def validar_periodo(cls, model):
        if model.startDate > model.endDate:
            raise ValueError("startDate não pode ser maior que endDate")
        return model        
    
    @model_validator(mode="after")
    def validar_nsu(cls, model):
        if model.nsu is not None and len(str(model.nsu)) < 9:
            raise ValueError("nsu inválido")
        return model        
    
    @model_validator(mode="after")
    def validar_companynumber(cls, model):
        if model.companyNumber not in COMPANY_NUMBER_LIST:
            raise ValueError("companyNumber inválido")
        return model        
    
    @model_validator(mode="after")
    def validar_financeiro(cls, model):
        if ("nufin" not in model.financeiro[0]) or ("desdobramento" not in model.financeiro[0]):
            raise ValueError("dicionário financeiro inválido")
        return model        

class RotinaPagamentoModel(BaseModel):
    companyNumber:int
    startDate:date
    endDate:date
    
    @model_validator(mode="after")
    def validar_periodo(cls, model):
        if model.startDate > model.endDate:
            raise ValueError("startDate não pode ser maior que endDate")
        return model     
    
    @model_validator(mode="after")
    def validar_companynumber(cls, model):
        if model.companyNumber not in COMPANY_NUMBER_LIST:
            raise ValueError("companyNumber inválido")
        return model     

class VendasPgtoId(BaseModel):
    ambiente:Literal['trn', 'prd']
    companyNumber:int
    paymentId:str

router = APIRouter()
security = HTTPBearer()

def validar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if (credentials.scheme != "Bearer") or (credentials.credentials is None) or (credentials.credentials == ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de autenticação inválido")
    return credentials.credentials

@router.get("/info", status_code=status.HTTP_200_OK)
def info():
    return {
        "status": "API is running",
        "health": "API is healthy",
        "version": "1.0.0"
    }

@router.post("/auth/generate-token", status_code=status.HTTP_200_OK)
def gerar_token(body:AutenticacaoModel) -> dict:
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
        pass
    return res

@router.post("/vendas/consulta-parcelas", status_code=status.HTTP_200_OK)
def consulta_parcelas(body:VendasModel, token:str=Depends(validar_token)) -> dict:
    res:dict={}
    vendas = Vendas()
    try:
        res = vendas.consultar_vendas_parceladas(
            ambiente=body.ambiente,
            token=token,
            companyNumber=body.companyNumber,
            nsu=body.nsu,
            startDate=body.startDate,
            endDate=body.endDate
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        pass
    return res

@router.post("/vendas/consulta-pgto-oc", status_code=status.HTTP_200_OK)
def consulta_pagamentos_oc(body:VendasModel, token:str=Depends(validar_token)) -> dict:
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
        pass
    return res

@router.post("/vendas/consulta-pgto-id", status_code=status.HTTP_200_OK)
def consulta_pagamentos_id(body:VendasPgtoId, token: str = Depends(validar_token)) -> dict:
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
        pass
    return res

@router.post("/rotina/atualiza-financeiro", status_code=status.HTTP_200_OK)
def atualiza_financeiro(body:RotinaVendaModel) -> dict:
    res:dict={}
    rotina = Rotina()
    try:        
        res = rotina.atualizar_dados_financeiro(
            companyNumber=body.companyNumber,
            dataVendas=body.startDate,
            nsu=body.nsu,
            dados_financeiro=body.financeiro
        )
        if not res.get('sucesso'):
            raise Exception(res.get('mensagem', 'Falha ao atualizar dados financeiro.'))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        pass
    return res

@router.post("/rotina/atualiza-pagamento", status_code=status.HTTP_200_OK)
def atualiza_pagamento(body:RotinaPagamentoModel) -> dict:
    res:dict={}
    rotina = Rotina()
    try:        
        res = rotina.atualizar_dados_pagamento(
            companyNumber=body.companyNumber,
            startDate=body.startDate,
            endDate=body.endDate
        )
        if res.get('sucesso') and res.get('mensagem'):
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        if not res.get('sucesso'):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=res.get('mensagem', 'Falha ao atualizar dados financeiro.'))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        pass
    return res
    