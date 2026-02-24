import os, base64, requests, json
from typing import Literal
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
from src.rede.utils.log import set_logger
from src.rede.services.token import TokenService
from src.rede.database.database import get_session
logger = set_logger(__name__)
load_dotenv()

class Autenticacao():

    def __init__(self,ambiente: Literal['trn', 'prd']='prd',pacote: Literal['pgto', 'vendas']='vendas',auth:str=''):
        self.sistema = 'rede'
        self.ambiente = ambiente
        self.pacote = pacote
        self.auth = os.getenv('BASIC_CLIENT_SP',auth)
        self.caminho_arquivo_token = os.getenv("PATH_TOKEN_REDE", "")

        if not all([self.caminho_arquivo_token, self.auth]):
            logger.critical("Variáveis de ambiente não configuradas corretamente para REDE.")
            raise Exception("Variáveis de ambiente não configuradas corretamente para REDE.")

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

    def salvar_token_arquivo(self, token: dict) -> bool:
        """
        Salva o token em um arquivo de texto.
            :param caminho_arquivo: caminho do arquivo de texto onde o token será salvo.
            :param token: token a ser salvo no arquivo.
        """

        status:bool = False
        try:
            with open(self.caminho_arquivo_token, 'w') as arquivo:
                arquivo.write(json.dumps(token,ensure_ascii=False, indent=4))
            status = True
        except Exception as e:
            logger.error(f"Erro ao salvar o token no arquivo: {e}")
        finally:
            pass
        return status

    def salvar_token(self, token: dict) -> bool:
        """
        Salva o token no banco de dados.            
            :param token: token a ser salvo.
        """

        status:bool = False
        session = next(get_session())
        token_servicedb = TokenService(db=session)
        try:            
            token_servicedb.salvar_token(
                sistema=self.sistema,
                access_token=token.get('access_token', ''),
                refresh_token=token.get('refresh_token', ''),
                expires_at=datetime.strptime(token['expire_time'], '%Y-%m-%d %H:%M:%S') if token.get('expire_time') else None
            )
            status = True
        except Exception as e:
            logger.error(f"Erro ao salvar o token no banco de dados: {e}")
        finally:
            pass
        return status

    def carregar_token_arquivo(self) -> dict:
        """
        Carrega o token de um arquivo de texto.
            :param caminho_arquivo: caminho do arquivo de texto onde o token está salvo.
            :return dict: token carregado do arquivo.
        """
        try:
            if os.path.exists(self.caminho_arquivo_token):
                with open(self.caminho_arquivo_token, 'r') as arquivo:
                    token = json.loads(arquivo.read())
                    return token
            else:
                logger.warning("Arquivo de token não encontrado.")
                return {}
        except Exception as e:
            logger.error(f"Erro ao carregar o token do arquivo: {e}")
            return {}

    def carregar_token(self) -> dict:
        """
        Carrega o token do banco de dados.
            :return dict: token carregado.
        """
        session = next(get_session())
        token_servicedb = TokenService(db=session)
        try:
            token = token_servicedb.obter_token(sistema=self.sistema)
            if token:
                return token.__dict__
            else:
                logger.warning("Token não encontrado no banco de dados.")
                return {}
        except Exception as e:
            logger.error(f"Erro ao buscar o token no banco de dados: {e}")
            return {}

    def autenticar_arquivo(self) -> str:
        """
        Realiza o processo de autenticação, verificando se o token existente é válido ou se é necessário solicitar um novo token.
            :return str: token de acesso válido para uso nas requisições à API.
        """
        token:dict = self.carregar_token_arquivo()
        if not token or datetime.strptime(token.get('expire_time', '1970-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S') <= datetime.now():
            token = self.gerar_token()
            if token:
                self.salvar_token_arquivo(token)
                return token.get('access_token', '')
            else:
                return ''
        else:
            return token.get('access_token', '')

    def autenticar(self) -> str:
        """
        Realiza o processo de autenticação, verificando se o token existente é válido ou se é necessário solicitar um novo token.
            :return str: token de acesso válido para uso nas requisições à API.
        """
        token:dict = self.carregar_token()
        if not token or not token.get('expires_at') or token.get('expires_at') <= datetime.now():
            token = self.gerar_token()
            if token:
                self.salvar_token(token)
                return token.get('access_token', '')
            else:
                return ''
        else:
            return token.get('access_token', '')

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

    def consultar_vendas_parceladas(self,token:str,companyNumber:int,startDate:date,endDate:date,nsu:int=None,ambiente:Literal['trn', 'prd']='prd') -> dict:

        data:dict={}
        url:str=''
        res:requests.Response=None

        url=self.validar_ambiente(ambiente=ambiente)
        if nsu:
            url+=f"/v2/payments/installments/{companyNumber}?saleDate={startDate.strftime('%Y-%m-%d')}&nsu={nsu}"
        else:
            url+=f"/v1/sales/installments?parentCompanyNumber={companyNumber}&subsidiaries={companyNumber}&startDate={startDate.strftime('%Y-%m-%d')}&endDate={endDate.strftime('%Y-%m-%d')}"

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
            match res.status_code:
                case 200:
                    data = res.json()
                case 204:
                    data = {
                        "message": f"A consulta não retornou dados. NSU: {nsu}. Data: {startDate.strftime('%d/%m/%Y')}"
                        }
                case _:
                    raise ConnectionError(f"Erro {res.status_code} na consulta de vendas parceladas: {res.text}")
        return data
    
    def consultar_pagamentos_oc(self,token:str,companyNumber:int,startDate:date,endDate:date,ambiente:Literal['trn', 'prd']='prd') -> dict:

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
            if res.ok and res.text:
                data = res.json()
            elif res.ok and not res.text:
                data = {
                    "message": f"A consulta não retornou dados. Período: {startDate.strftime('%d/%m/%Y')} - {endDate.strftime('%d/%m/%Y')}"
                }
            else:
                raise ConnectionError(f"Erro {res.status_code} na consulta de pagamentos: {res.text}")
        
        return data

    def consultar_pagamentos_id(self,token:str,companyNumber:int,paymentId:str,ambiente:Literal['trn', 'prd']='prd') -> dict:

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
            if res.ok and res.text:
                data = res.json()
            elif res.ok and not res.text:
                data = {
                    "message": f"A consulta não retornou dados. ID Pagamento: {paymentId}"
                }
            else:
                raise ConnectionError(f"Erro {res.status_code} na consulta de pagamentos por ID: {res.text}")
        
        return data
