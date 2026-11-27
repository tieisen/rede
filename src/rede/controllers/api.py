from typing import Literal
from datetime import date
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Response, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, model_validator
from src.rede.services.rede import *
from src.rede.services.rotina import RotinaService
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
        """
            Valida se o companyNumber está na lista COMPANY_NUMBER_LIST do .env.
        """

        if model.companyNumber not in COMPANY_NUMBER_LIST:
            raise ValueError("Company Number inválido")
        return model  

class VendasModel(BaseModel):
    ambiente:Literal['trn', 'prd']
    companyNumber:int
    nsu:int=None
    startDate:date
    endDate:date
    
    @model_validator(mode="after")
    def validar_periodo(cls, model):
        """
            Valida se startDate não é maior que endDate.
        """

        if model.startDate > model.endDate:
            raise ValueError("startDate não pode ser maior que endDate")
        return model        
    
    @model_validator(mode="after")
    def validar_nsu(cls, model):
        """
            Valida se o NSU, quando informado, tem pelo menos 8 dígitos.
        """

        if model.nsu is not None and len(str(model.nsu)) < 8:
            raise ValueError("NSU inválido. Deve conter pelo menos 8 dígitos.")
        return model        
    
    @model_validator(mode="after")
    def validar_companynumber(cls, model):
        """
            Valida se o companyNumber está na lista COMPANY_NUMBER_LIST do .env.
        """

        if model.companyNumber not in COMPANY_NUMBER_LIST:
            raise ValueError("Company Number inválido")
        return model         

class RotinaVendaModel(BaseModel):
    companyNumber:int
    startDate:date
    endDate:date
    nsu:int=None
    
    @model_validator(mode="after")
    def validar_periodo(cls, model):
        """
            Valida se startDate não é maior que endDate.
        """

        if model.startDate > model.endDate:
            raise ValueError("startDate não pode ser maior que endDate")
        return model        
    
    @model_validator(mode="after")
    def validar_nsu(cls, model):
        """
            Valida se o NSU, quando informado, tem pelo menos 8 dígitos.
        """

        if model.nsu is not None and len(str(model.nsu)) < 8:
            raise ValueError("NSU inválido. Deve conter pelo menos 8 dígitos.")
        return model        
    
    @model_validator(mode="after")
    def validar_companynumber(cls, model):
        """
            Valida se o companyNumber está na lista COMPANY_NUMBER_LIST do .env.
        """

        if model.companyNumber not in COMPANY_NUMBER_LIST:
            raise ValueError("Company Number inválido")
        return model

class RotinaPagamentoModel(BaseModel):
    companyNumber:int
    startDate:date
    endDate:date
    
    @model_validator(mode="after")
    def validar_periodo(cls, model):
        """
            Valida se startDate não é maior que endDate.
        """

        if model.startDate > model.endDate:
            raise ValueError("startDate não pode ser maior que endDate")
        return model     
    
    @model_validator(mode="after")
    def validar_companynumber(cls, model):
        """
            Valida se o companyNumber está na lista COMPANY_NUMBER_LIST do .env.
        """

        if model.companyNumber not in COMPANY_NUMBER_LIST:
            raise ValueError("Company Number inválido")
        return model     

class VendasPgtoId(BaseModel):
    ambiente:Literal['trn', 'prd']
    companyNumber:int
    paymentId:str

router = APIRouter()
security = HTTPBearer()

def validar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
        Dependência de autenticação das rotas /vendas.

        Confere apenas se o header Authorization traz um Bearer não vazio.
        O valor do token não é validado.

        Retorno: token informado
    """

    if (credentials.scheme != "Bearer") or (credentials.credentials is None) or (credentials.credentials == ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de autenticação inválido")
    return credentials.credentials

@router.get("/info", status_code=status.HTTP_200_OK)
def info():
    """
        Health check da API.
    """

    return {
        "status": "API is running",
        "health": "API is healthy",
        "version": "1.0.0"
    }

@router.post("/auth/login", status_code=status.HTTP_200_OK)
def logar(body:AutenticacaoModel) -> dict:
    """
        Endpoint para gerar um token de acesso na API Rede.

        ambiente: 'trn' | 'prd'
        pacote: 'pgto' | 'vendas'
        auth: client_id:client_secret

        *BASIC_CLIENT_SP do .env tem prioridade sobre o auth informado*
    """

    res:dict={}
    auth = AutenticacaoService(
        ambiente=body.ambiente,
        pacote=body.pacote,
        auth=body.auth
    )
    try:
        res = auth.logar()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        pass
    return res

@router.post("/vendas/consulta-parcelas", status_code=status.HTTP_200_OK)
def consultaParcelas(body:VendasModel, token:str=Depends(validar_token)) -> dict:
    
    """
        Endpoint para consultar parcelas no Itaú
        
        companyNumber:int
        nsu:int=None
        startDate:date
        endDate:date
        
        *Não é utilizado*
    """
    
    res:dict={}
    vendas = VendasService()
    try:
        res = vendas.consultarVendasParceladas(
            ambiente=body.ambiente,
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
def consultaPagamentosPorOc(body:VendasModel, token:str=Depends(validar_token)) -> dict:
    
    """
        Endpoint para buscar um pagamento no Itaú. 
            
        companyNumber:int
        nsu:int=None
        startDate:date
        endDate:date
            
        *Não é utilizado"
    """
    
    res:dict={}
    vendas = VendasService()        
    try:
        res = vendas.consultarPagamentosOc(
            ambiente=body.ambiente,
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
def consultaPagamentosPorId(body:VendasPgtoId, token: str = Depends(validar_token)) -> dict:

    """
        Endpoint para buscar um pagamento no Itaú por paymentId. 
        
        companyNumber:int
        paymentId:str
        
        *Não é utilizado"
    """
    
    res:dict={}
    vendas = VendasService()        
    try:
        res = vendas.consultarPagamentosId(
            ambiente=body.ambiente,
            companyNumber=body.companyNumber,
            paymentId=body.paymentId
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        pass
    return res

@router.post("/rotina/registra-pagamento", status_code=status.HTTP_200_OK)
def registraPagamento(body:RotinaVendaModel) -> dict:
    
    """
        Endpoint utilizado pelo botão de ação vincular pagamento da tela Pagamentos REDE
    """
    
    res:dict={}   
    rotina = RotinaService() 
    try:        
        res = rotina.registrarDadosPagamento(
            companyNumber=body.companyNumber,
            dataVendas=body.startDate,
            nsu=body.nsu
        )
        if not res.get('sucesso'):
            raise Exception(res.get('mensagem', 'Falha ao registrar dados de pagamento.'))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    finally:
        pass
    return res

@router.post("/rotina/atualiza-pagamento", status_code=status.HTTP_200_OK)
def atualizaPagamento(body:RotinaPagamentoModel) -> dict:
    """
        Endpoint utilizado pelo botão de ação de atualizar pagamento da tela Pagamentos REDE
    """
    
    res:dict={}
    rotina = RotinaService()
    try:        
        res = rotina.atualizarDadosPagamento(
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
    