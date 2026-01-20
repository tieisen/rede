import os, json, base64, requests
from typing import Literal
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

class Autenticacao():

    def __init__(self, ambiente: Literal['trn', 'prd'], pacote: Literal['pgto', 'vendas']) -> None:
        self.ambiente = ambiente
        self.pacote = pacote
        self.dados_ambiente = self.validar_ambiente()

    def converter_base64(self,texto:str) -> str:
        texto_bytes = texto.encode("utf-8")
        base64_bytes = base64.b64encode(texto_bytes)
        base64_string = base64_bytes.decode("utf-8")
        return base64_string    

    def validar_ambiente(self) -> dict:
        dados_ambiente:dict={}
        ambientes_validos = ['trn','prd']
        if self.ambiente not in ambientes_validos:
            raise ValueError(f"Ambiente inválido. Escolha entre {ambientes_validos}")
        pacotes_validos = ['pgto','vendas']
        if self.pacote not in pacotes_validos:
            raise ValueError(f"Pacote inválido. Escolha entre {pacotes_validos}")
        match (self.pacote, self.ambiente):
            case ('pgto', 'trn'):
                dados_ambiente['authorization'] = f"Basic {self.converter_base64(os.getenv('BASIC_CLIENT_PT'))}"
                dados_ambiente['url']=os.getenv('URL_AUTH_PT')
                dados_ambiente['path']=os.getenv('PATH_PT')
            case ('pgto', 'prd'):
                dados_ambiente['authorization'] = f"Basic {self.converter_base64(os.getenv('BASIC_CLIENT_PP'))}"
                dados_ambiente['url']=os.getenv('URL_AUTH_PP')
                dados_ambiente['path']=os.getenv('PATH_PP')
                pass                
            case ('vendas', 'trn'):
                dados_ambiente['authorization'] = f"Basic {self.converter_base64(os.getenv('BASIC_CLIENT_ST'))}"
                dados_ambiente['url']=os.getenv('URL_AUTH_ST')
                dados_ambiente['path']=os.getenv('PATH_ST')
            case ('vendas', 'prd'):
                dados_ambiente['authorization'] = f"Basic {self.converter_base64(os.getenv('BASIC_CLIENT_SP'))}"
                dados_ambiente['url']=os.getenv('URL_AUTH_SP')
                dados_ambiente['path']=os.getenv('PATH_SP')
            case _:
                raise ValueError("Erro ao validar ambiente: combinação de pacote e ambiente desconhecida")        
        return dados_ambiente

    def calcular_expiracao(self,dados:dict) -> bool:
        request_time = datetime.now()
        expire_time = request_time + timedelta(seconds=dados.get('expires_in'))
        dados['request_time'] = request_time.strftime("%Y-%m-%d %H:%M:%S")
        dados['expire_time'] = expire_time.strftime("%Y-%m-%d %H:%M:%S")
        return True

    def salvar_token(self,dados:dict,path:str) -> bool:
        try:
            with open(path,mode="w",encoding="utf-8") as f:
                json.dump(dados,f,ensure_ascii=False,indent=4)
            return True
        except Exception as e:
            print(f"Erro ao salvar arquivo: {e}")
            return False

    def carregar_token(self,path:str) -> dict:
        dados_token:dict={}
        try:
            with open(path,mode="r",encoding="utf-8") as f:
                dados_token = json.load(f)            
        except Exception as e:
            print(f"Erro ao carregar arquivo: {e}")
        finally:
            pass
        return dados_token

    def gerar_token(self) -> dict:

        def consolidar():
            self.calcular_expiracao(dados=dados)
            self.salvar_token(dados=dados,path=self.dados_ambiente.get('path'))

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
        try:
            res = requests.post(
                url=self.dados_ambiente.get('url'),
                headers=header,
                data=body
            )
        except Exception as e:
            print(f"Erro na requisição do token: {e}")
        finally:
            if res.ok:
                dados = res.json()
                consolidar()
            else:
                raise ConnectionError(f"Erro {res.status_code}: {res.text}")
        return dados
    
    def buscar(self):  
        dados_token:dict={}
        if not self.dados_ambiente:
            raise ValueError("Não foi possível validar o ambiente")
        dados_token = self.carregar_token(self.dados_ambiente.get('path'))
        if dados_token:
            if datetime.strptime(dados_token.get('expire_time'),'%Y-%m-%d %H:%M:%S') > datetime.now():
                dados_token = self.gerar_token()
            else:
                dados_token = self.gerar_token()                            
        else:
            dados_token = self.gerar_token()
        return dados_token.get('access_token')
    
class LinkPagamento():

    def __init__(self, ambiente: Literal['trn', 'prd'], companyNumber:int=int(os.getenv('COMPANY_NUMBER')), body:dict={}, **kwargs) -> None:
        self.auth = Autenticacao(ambiente=ambiente,pacote='pgto')
        self.companyNumber = companyNumber
        self.body = body
        self.paymentLinkId = kwargs.get('paymentLinkId')
        match ambiente:
            case 'trn':
                self.url = os.getenv('URL_PT')
            case 'prd':
                self.url = os.getenv('URL_PP')
            case _:
                self.url = ''
                raise ValueError(f"Ambiente inválido:\n>>{ambiente}")        

    def consultar_detalhes_link(self) -> dict:

        data:dict={}
        url:str=''
        token:str=''
        res:requests.Response=None

        token = self.auth.buscar()
        if not token:
            raise ValueError("Token não gerado")

        if not self.paymentLinkId:
            raise ValueError("Parâmetro ID do link de pagamento (paymentLinkId) não informado")

        url=self.url+f'/details/{self.paymentLinkId}'

        header:dict={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/application/json",
            "Company-number": str(self.companyNumber)
        }

        try:
            res = requests.get(
                url=url,
                headers=header
            )
        except Exception as e:
            print(f"Erro na requisição: {e}")
        finally:
            if res.ok:
                data = res.json()
            else:
                raise ConnectionError(f"Erro {res.status_code}: {res.text}")
        
        return data

    def criar_link(self) -> dict:

        data:dict={}
        url:str=''
        token:str=''
        res:requests.Response=None

        token = self.auth.buscar()
        if not token:
            raise ValueError("Token não gerado")

        url=self.url+'/create'

        header:dict={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Company-number": str(self.companyNumber)
        }

        try:
            res = requests.post(
                url=url,
                headers=header,
                json=self.body
            )
        except Exception as e:
            print(f"Erro na requisição: {e}")
        finally:
            if res.ok:
                data = res.json()
            else:
                raise ConnectionError(f"Erro {res.status_code}: {res.text}")
        
        return data

class Vendas():

    def __init__(self, ambiente: Literal['trn', 'prd'], companyNumber:int=int(os.getenv('COMPANY_NUMBER')), body:dict={}, **kwargs) -> None:
        self.auth = Autenticacao(ambiente=ambiente,pacote='vendas')
        self.companyNumber = companyNumber
        self.body = body
        self.startDate = kwargs.get('startDate')
        self.endDate = kwargs.get('endDate')
        self.paymentId = kwargs.get('paymentId')
        match ambiente:
            case 'trn':
                self.url = os.getenv('URL_ST')
            case 'prd':
                self.url = os.getenv('URL_SP')
            case _:
                self.url = ''
                raise ValueError(f"Ambiente inválido:\n>>{ambiente}")  

    def consultar_vendas_parceladas(self) -> dict:

        data:dict={}
        token:str=''
        url:str=''
        res:requests.Response=None

        if not all([self.startDate,self.endDate]):
            raise ValueError("Parâmetros data de início (startDate) e/ou data de fim (endDate) não informados")

        token = self.auth.buscar()
        if not token:
            raise ValueError("Token não gerado")
        
        url = self.url+f'/sales/installments?parentCompanyNumber={self.companyNumber}&subsidiaries={self.companyNumber}&startDate={self.startDate}&endDate={self.endDate}'

        header:dict={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/application/json"
        }

        try:
            res = requests.get(
                url=url,
                headers=header
            )
        except Exception as e:
            print(f"Erro na requisição do token: {e}")
        finally:
            if res.ok:
                data = res.json()
            else:
                raise ConnectionError(f"Erro {res.status_code}: {res.text}")
        
        return data
    
    def consultar_pagamentos_oc(self) -> dict:

        data:dict={}
        token:str=''
        url:str=''
        res:requests.Response=None    

        if not all([self.startDate,self.endDate]):
            raise ValueError("Parâmetros data de início (startDate) e/ou data de fim (endDate) não informados")

        token = self.auth.buscar()
        if not token:
            raise ValueError("Token não gerado")

        url = self.url+f'/payments/credit-orders?parentCompanyNumber={self.companyNumber}&subsidiaries={self.companyNumber}&startDate={self.startDate}&endDate={self.endDate}'

        header:dict={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/application/json"
        }

        try:
            res = requests.get(
                url=url,
                headers=header
            )
        except Exception as e:
            print(f"Erro na requisição do token: {e}")
        finally:
            if res.ok:
                data = res.json()
            else:
                raise ConnectionError(f"Erro {res.status_code}: {res.text}")
        
        return data

    def consultar_pagamentos_id(self) -> dict:

        data:dict={}
        token:str=''
        url:str=''
        res:requests.Response=None

        if not self.paymentId:
            raise ValueError("Parâmetro ID do pagamento (paymentId) não informado")        

        token = self.auth.buscar()
        if not token:
            raise ValueError("Token não gerado")

        url=self.url+f'/payments/{self.companyNumber}/{self.paymentId}'

        header:dict={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/application/json"
        }

        try:
            res = requests.get(
                url=url,
                headers=header
            )
        except Exception as e:
            print(f"Erro na requisição do token: {e}")
        finally:
            if res.ok:
                data = res.json()
            else:
                raise ConnectionError(f"Erro {res.status_code}: {res.text}")
        
        return data    