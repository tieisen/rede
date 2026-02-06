import os, base64, requests
from typing import Literal
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
from log import set_logger
logger = set_logger(__name__)
load_dotenv()

class Autenticacao():

    def __init__(self,ambiente: Literal['trn', 'prd']='',pacote: Literal['pgto', 'vendas']='',auth:str=''):
        self.ambiente = ambiente
        self.pacote = pacote
        self.auth = auth

    def converter_base64(self,texto:str) -> str:
        base64_bytes = b""
        base64_string = ""
        try:
            assert isinstance(texto,str)
            texto_bytes = texto.encode("utf-8")
            base64_bytes = base64.b64encode(texto_bytes)
            base64_string = base64_bytes.decode("utf-8")
        except Exception as e:
            logger.error(f"Erro ao converter para base64: {e}")
        finally:
            pass            
        return base64_string

    def validar_ambiente(self) -> dict:
        dados_ambiente:dict={}
        ambientes_validos = ['trn','prd']
        pacotes_validos = ['pgto','vendas']

        try:
            assert isinstance(self.ambiente,str)
            assert isinstance(self.pacote,str)
            assert isinstance(self.auth,str)

            if self.ambiente not in ambientes_validos:
                raise ValueError(f"Ambiente inválido. Escolha entre {ambientes_validos}")        
            if self.pacote not in pacotes_validos:
                raise ValueError(f"Pacote inválido. Escolha entre {pacotes_validos}")
            if not self.auth:
                raise ValueError("Parâmetro auth não informado")
            
            match (self.pacote, self.ambiente):
                case ('pgto', 'trn'):
                    dados_ambiente['authorization']=f"Basic {self.converter_base64(self.auth)}"
                    dados_ambiente['url']=os.getenv('URL_AUTH_PT')
                case ('pgto', 'prd'):
                    dados_ambiente['authorization']=f"Basic {self.converter_base64(self.auth)}"
                    dados_ambiente['url']=os.getenv('URL_AUTH_PP')
                    pass                
                case ('vendas', 'trn'):
                    dados_ambiente['authorization']=f"Basic {self.converter_base64(self.auth)}"
                    dados_ambiente['url']=os.getenv('URL_AUTH_ST')
                case ('vendas', 'prd'):
                    dados_ambiente['authorization']=f"Basic {self.converter_base64(self.auth)}"
                    dados_ambiente['url']=os.getenv('URL_AUTH_SP')
                case _:
                    raise ValueError("Erro ao validar ambiente: combinação de pacote e ambiente desconhecida")
        except Exception as e:
            logger.error(f"Erro ao validar ambiente: {e}")

        return dados_ambiente

    def calcular_expiracao(self,dados:dict) -> bool:
        try:
            assert isinstance(dados,dict)
            assert 'expires_in' in dados
            assert isinstance(dados.get('expires_in'),int)
            request_time = datetime.now()
            expire_time = request_time + timedelta(seconds=dados.get('expires_in'))
            dados['request_time'] = request_time.strftime("%Y-%m-%d %H:%M:%S")
            dados['expire_time'] = expire_time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"Erro ao calcular expiração do token: {e}")
            return False
        finally:
            pass
        return True

    def gerar_token(self) -> dict:
        
        self.dados_ambiente = self.validar_ambiente()
        res:requests.Response=None

        print(f"Gerando token para o ambiente {self.ambiente} e pacote {self.pacote}...")
        print(f"URL: {self.dados_ambiente.get('url')}")

        try:
            assert isinstance(self.dados_ambiente,dict)
            if not self.dados_ambiente:
                raise ValueError("Não foi possível validar o ambiente")

            dados:dict={}
            if not self.dados_ambiente:
                raise ValueError("Não foi possível validar o ambiente")
            
            header:dict={
                "Authorization": self.dados_ambiente.get('authorization'),
                "Content-Type": "application/x-www-form-urlencoded"
            }

            body:dict={
                "grant_type":"client_credentials"
            }

            res = requests.post(
                url=self.dados_ambiente.get('url'),
                headers=header,
                data=body
            )
        except Exception as e:
            logger.error(f"Erro na requisição do token: {e}")
        finally:
            if res.ok:
                dados = res.json()
                self.calcular_expiracao(dados=dados)
            else:
                raise ConnectionError(f"Erro {res.status_code}: {res.text}")
        return dados
    
class LinkPagamento():

    def __init__(self):
        pass

    def validar_ambiente(self,ambiente: Literal['trn', 'prd']) -> str:
        ambientes_validos = ['trn','prd']
        url:str=''

        try:
            assert isinstance(ambiente,str)
            assert ambiente in ambientes_validos
            match ambiente:
                case 'trn':
                    url = os.getenv('URL_PT')
                case 'prd':
                    url = os.getenv('URL_PP')
                case _:
                    url = ''
                    raise ValueError(f"Ambiente inválido:\n>>{ambiente}")
        except Exception as e:
            logger.error(f"Erro ao validar ambiente: {e}")
        finally:
            pass
        return url

    def consultar_detalhes_link(self,ambiente: Literal['trn', 'prd'],token:str,paymentLinkId:str,companyNumber:str) -> dict:

        data:dict={}
        url:str=''
        res:requests.Response=None

        url=self.validar_ambiente(ambiente=ambiente)
        url+=f'/details/{paymentLinkId}'

        header:dict={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Company-number": str(companyNumber)
        }

        try:
            res=requests.get(
                url=url,
                headers=header
            )
        except Exception as e:
            raise ConnectionError(f"Erro na consulta do link de pagamento {paymentLinkId}: {e}")
        finally:
            if res.ok:
                data = res.json()
            else:
                raise ConnectionError(f"Erro {res.status_code} na consulta do link de pagamento {paymentLinkId}: {res.text}")
        
        return data

    def criar_link(self,ambiente: Literal['trn', 'prd'],token:str,companyNumber:str,body:dict) -> dict:

        data:dict={}
        url:str=''
        res:requests.Response=None

        url = self.validar_ambiente(ambiente=ambiente)
        url+='/create'

        header:dict={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Company-number": str(companyNumber)
        }

        try:
            res = requests.post(
                url=url,
                headers=header,
                json=body
            )
        except Exception as e:
            raise ConnectionError(f"Erro na criação do link de pagamento: {e}")
        finally:
            if res.ok:
                data = res.json()
            else:
                raise ConnectionError(f"Erro {res.status_code} na criação do link de pagamento: {res.text}")
        
        return data

class Vendas():

    def __init__(self):
        pass

    def validar_ambiente(self,ambiente: Literal['trn', 'prd']) -> str:

        ambientes_validos = ['trn','prd']
        url:str=''
        if ambiente not in ambientes_validos:
            raise ValueError(f"Ambiente inválido. Escolha entre {ambientes_validos}")
        match ambiente:
            case 'trn':
                url = os.getenv('URL_ST')
            case 'prd':
                url = os.getenv('URL_SP')
            case _:
                url = ''
                raise ValueError(f"Ambiente inválido:\n>>{ambiente}")           
        return url

    def consultar_vendas_parceladas(self,ambiente:Literal['trn', 'prd'],token:str,companyNumber:int,startDate:date,endDate:date,nsu:int=None) -> dict:

        data:dict={}
        url:str=''
        res:requests.Response=None
        
        url=self.validar_ambiente(ambiente=ambiente)
        if nsu:
            url+=f'/v2/payments/installments/{companyNumber}?saleDate={startDate.strftime('%Y-%m-%d')}&nsu={nsu}'
        else:
            url+=f'/v1/sales/installments?parentCompanyNumber={companyNumber}&subsidiaries={companyNumber}&startDate={startDate.strftime('%Y-%m-%d')}&endDate={endDate.strftime('%Y-%m-%d')}'

        header:dict={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            res = requests.get(
                url=url,
                headers=header
            )
        except Exception as e:
            raise ConnectionError(f"Erro na consulta de vendas parceladas: {e}")
        finally:
            if res.ok:
                data = res.json()
            else:
                raise ConnectionError(f"Erro {res.status_code} na consulta de vendas parceladas: {res.text}")
        
        return data
    
    def consultar_pagamentos_oc(self,ambiente:Literal['trn', 'prd'],token:str,companyNumber:int,startDate:date,endDate:date) -> dict:

        data:dict={}
        url:str=''
        res:requests.Response=None    

        url=self.validar_ambiente(ambiente=ambiente)
        url+=f'/v1/payments/credit-orders?parentCompanyNumber={companyNumber}&subsidiaries={companyNumber}&startDate={startDate.strftime('%Y-%m-%d')}&endDate={endDate.strftime('%Y-%m-%d')}'

        header:dict={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            res = requests.get(
                url=url,
                headers=header
            )
        except Exception as e:
            raise ConnectionError(f"Erro na consulta de pagamentos: {e}")
        finally:
            if res.ok:
                data = res.json()
            else:
                raise ConnectionError(f"Erro {res.status_code} na consulta de pagamentos: {res.text}")
        
        return data

    def consultar_pagamentos_id(self,ambiente:Literal['trn', 'prd'],token:str,companyNumber:int,paymentId:str) -> dict:

        data:dict={}
        url:str=''
        res:requests.Response=None

        url=self.validar_ambiente(ambiente=ambiente)
        url+=f'/v1/payments/{companyNumber}/{paymentId}'

        header:dict={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        try:
            res = requests.get(
                url=url,
                headers=header
            )
        except Exception as e:
            raise ConnectionError(f"Erro na consulta de pagamentos por ID: {e}")
        finally:
            if res.ok:
                data = res.json()
            else:
                raise ConnectionError(f"Erro {res.status_code} na consulta de pagamentos por ID: {res.text}")
        
        return data
