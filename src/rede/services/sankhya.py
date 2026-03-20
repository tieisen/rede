import os, requests
from functools import wraps
from datetime import datetime, timedelta
from dotenv import load_dotenv
from src.rede.utils.log import set_logger
from src.rede.services.token import TokenService
from src.rede.database.database import get_session
logger = set_logger(__name__)
load_dotenv()

class AutenticacaoService:

    def __init__(self):
        self.sistema = 'sankhya'
        self.url = os.getenv('URL_AUTH_SNK')
        self.x_token = os.getenv('XTOKEN')
        self.app_id = os.getenv('APP_ID')

        if not any([self.url, self.x_token, self.app_id]):
            logger.critical("Variáveis de ambiente não configuradas corretamente para SANKHYA.")
            raise Exception("Variáveis de ambiente não configuradas corretamente para SANKHYA.")

    def salvarToken(self, dadosToken: dict) -> bool:        
        status:bool = False
        token:str = dadosToken.get('token')
        expire_date:datetime = datetime.strptime(dadosToken.get('dhExpiracaoToken',''), "%Y-%m-%dT%H:%M:%S.%f")
        expire_date_ajustado = expire_date - timedelta(seconds=60)
        
        with get_session() as session:
            token_servicedb = TokenService(db=session)
            try:                
                token_servicedb.salvarToken(
                    sistema=self.sistema,
                    accessToken=token,
                    expiresAt=expire_date_ajustado
                )
                status = True
            except Exception as e:
                logger.error(f"Erro ao salvar o token no banco de dados: {e}")
            finally:
                session.close()
        return status

    def carregarToken(self) -> dict:
        token:dict = {}
        with get_session() as session:
            token_servicedb = TokenService(db=session)
            try:
                token_db = token_servicedb.obterToken(sistema=self.sistema)
                if token_db:
                    token = token_db.__dict__
                else:
                    logger.warning("Token não encontrado no banco de dados.")                    
            except Exception as e:
                logger.error(f"Erro ao buscar o token no banco de dados: {e}")
            finally:
                session.close()
        return token

    def logar(self) -> dict:

        auth:dict=''

        # Header da requisição
        header:dict = {
            'xToken': self.x_token
        }
        
        url:str = self.url+f"/{self.app_id}"

        try:
            res = requests.post(
                url=url,
                headers=header
            )
            
            if not res.ok:
                raise Exception(f"Erro {res.status_code} ao autenticar: {res.get("mensagem")}")
            
            auth = res.json()
                
        except Exception as e:
            logger.error(str(e))
        finally:
            pass

        return auth

    def validarToken(self) -> bool:
        status:bool = False
        self.token:str = ''
        agora:datetime = datetime.now().replace(microsecond=0)
        expiracao_token:datetime = None        
        dados_token:dict = self.carregarToken()

        if not dados_token:
            logger.error(f"Dados do token não encontrado")
            return status
        
        expiracao_token = dados_token.get('expires_at').replace(microsecond=0) if dados_token.get('expires_at') else None
        self.token = dados_token.get('access_token')        
        
        if (not self.token) or (not expiracao_token):
            logger.error(f"Token não encontrado")
            return status

        if expiracao_token <= agora:
            return status
        
        status = True
        return status
    
    def atualizarToken(self) -> bool:        
        status:bool = False
        dados_token:dict = self.logar()
        if dados_token:
            self.token = dados_token.get('token', '')
            status = self.salvarToken(dados_token)            
        return status

    def autenticar(self) -> str:
        if not self.validarToken():
            self.atualizarToken()
        return self.token

    def accessToken(func):
        """
        Executa rotina de autenticacao
            :param func: função que recebe o decorador
        """        
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:        
                token = AutenticacaoService().autenticar()                
                self.token = token
                if not self.token:
                    raise ValueError("Não foi possível autenticar.")
                return func(self, *args, **kwargs)
            finally:
                self.token = None
        return wrapper  

class FinanceiroService(AutenticacaoService):

    def __init__(self):
        super().__init__()
        self.token = None
        self.fields:list = [
                    "AD_REDE_AMOUNT",
                    "AD_REDE_EXPIRATIONDATE",
                    "AD_REDE_INSTALLMENTNUM",
                    "AD_REDE_MDRAMOUNT",
                    "AD_REDE_MDRFEE",
                    "AD_REDE_NETAMOUNT",
                    "AD_REDE_PAYMENTDATE",
                    "AD_REDE_PAYMENTID",
                    "AD_REDE_PROCESSADO",
                    "AD_REDE_TID",
                    "AD_COMPANYNUMBER"
                ]

    def formatarRetorno(self, res:dict) -> list:

        # RETORNO DE CONSULTA PELO DBEXPLORER
        if res.get('serviceName') == 'DbExplorerSP.executeQuery':
            field_names = [field['name'].lower() for field in res['responseBody']['fieldsMetadata']]
            result = [dict(zip(field_names, row)) for row in res['responseBody']['rows']]
            return result
        
        # RETORNO DE CONSULTA DE VIEW
        if res.get('serviceName') == 'CRUDServiceProvider.loadView':
            result = []
            if not res['responseBody']['records']:
                return result            
            aux = res['responseBody']['records']['record']
            if isinstance(aux, list):
                for item in res['responseBody']['records']['record']:
                    novo_dict = {str.lower(chave): valor['$'] for chave, valor in item.items()}
                    result.append(novo_dict)
            if isinstance(aux, dict):
                result.append({str.lower(chave): valor['$'] for chave, valor in aux.items()})
            return result

        # RETORNO VAZIO DE CONSULTA DE ENTIDADES
        if res['responseBody']['entities']['total'] == '0':
            return []

        # RETORNO DE CONSULTA DE ENTIDADES
        res_formatted = {}

        # Extrai as colunas
        columns = res['responseBody']['entities']['metadata']['fields']['field']
        if isinstance(columns, dict):
            columns = [columns]

        # Extrai retorno de 1 linha (dicionario)
        if res['responseBody']['entities']['total'] == '1':
            rows = [res['responseBody']['entities']['entity']]
            try:            
                for row in rows:
                    for i, column in enumerate(columns):                        
                        res_formatted[str.lower(column['name'])] = row.get(f'f{i}').get('$',None)
            except Exception as e:
                logger.error("Erro ao formatar dados da resposta. %s",e)
            finally:
                pass
            return [res_formatted]
        else:
        # Extrai retorno de várias linhas (lista de dicionarios)
            new_res = []
            rows = res['responseBody']['entities']['entity']

            # Se columns for uma lista, extrai no formato chave:valor
            if isinstance(columns, list):
                try:
                    for row in rows:
                        for i, column in enumerate(columns):
                            res_formatted[str.lower(column['name'])] = row.get(f'f{i}').get('$',None)  
                        new_res.append(res_formatted)
                        res_formatted = {}                        
                except Exception as e:
                    logger.error("Erro ao formatar dados da resposta. %s",e)
                finally:
                    pass
                return new_res

            # Se columns for um dicionario, extrai no formato chave:[valores]
            if isinstance(columns, dict):
                values = []
                try:            
                    for row in rows:
                        values.append(row.get('f0').get('$',None)) 
                    new_res = [{str.lower(columns['name']) : values}]
                except Exception as e:
                    logger.error("Erro ao formatar dados da resposta. %s",e)
                finally:
                    pass
                return new_res

    @AutenticacaoService.accessToken
    def buscar(self,saleSummaryNumber:int=None,lista:list=None) -> dict:

        def montaExpressao(saleSummaryNumber:int=None,lista:list=None):
            nonlocal criteria

            if not any([saleSummaryNumber,lista]):
                return False
            
            try:
                if saleSummaryNumber:
                    criteria = {
                        "expression": {
                            "$": "this.AD_REDE_SALESUMNUM = ?"
                        },
                        "parameter": [
                            {
                                "$": f"{saleSummaryNumber}",
                                "type": "I"
                            }
                        ]
                    }
                elif lista:
                    criteria = {
                        "expression": {
                            "$": "this.AD_REDE_SALESUMNUM IN ("+','.join('?' for _ in lista)+")"
                        },
                        "parameter": [ { "$": str(i), "type": "I" } for i in lista ]
                    }
                else:
                    pass
                return True
            except Exception as e:
                logger.error(f"Erro ao montar expressão: {e}")
                return False

        dados_financeiro:dict = {}
        url:str = 'https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=CRUDServiceProvider.loadRecords&outputType=json'
        fieldset_list:str = 'AD_REDE_AMOUNT,AD_REDE_EXPIRATIONDATE,AD_REDE_INSTALLMENTNUM,AD_REDE_MDRAMOUNT,AD_REDE_MDRFEE,AD_REDE_NETAMOUNT,AD_REDE_PAYMENTDATE,AD_REDE_PAYMENTID,AD_REDE_PROCESSADO,AD_REDE_TID,AD_REDE_SALESUMNUM,NUFIN'
        criteria:dict={}
        payload:dict={}

        try:
            saleSummaryNumber = int(saleSummaryNumber) if saleSummaryNumber else None
            lista = [int(i) for i in lista] if lista else None
            
            if not montaExpressao(saleSummaryNumber=saleSummaryNumber,lista=lista):
                raise ValueError("Nenhum critério de busca fornecido.")

            payload = {
                    "serviceName": "CRUDServiceProvider.loadRecords",
                    "requestBody": {
                        "dataSet": {
                            "rootEntity": "Financeiro",
                            "includePresentationFields": "N",
                            "offsetPage": "0",
                            "criteria": criteria,
                            "entity": {
                                "fieldset": {
                                    "list": fieldset_list
                                }
                            }
                        }
                    }
                }

            res = requests.get(
                url=url,
                headers={ "Authorization":f"Bearer {self.token}" },
                json=payload
            )
            
            if res.ok and res.json().get('status') in ['0','1']:
                dados_financeiro = self.formatar_retorno(res.json())
            else:
                raise Exception(f"{res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Erro ao buscar dados financeiro: {e}")
        finally:
            pass

        return dados_financeiro

    @AutenticacaoService.accessToken
    def atualizar(self,payload:list[dict]) -> bool:
        
        sucesso:bool = False
        url:str = 'https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=DatasetSP.save&outputType=json'        
        payload_send = {
            "serviceName":"DatasetSP.save",
            "requestBody":{
                "entityName":"Financeiro",
                "standAlone":False,
                "fields":self.fields,
                "records": payload
            }
        }
        headers = { "Authorization":f"Bearer {self.token}" }

        logger.info(f"Enviando headers de atualização para a API Sankhya: {headers}")
        logger.info(f"Enviando payload de atualização para a API Sankhya: {payload_send}")        

        try:
            res = requests.post(
                url=url,
                headers=headers,
                json=payload_send
            )
            if res.ok and res.json().get('status') in ['0','1']:
                sucesso = True if res.json().get('status') == '1' else False
            else:
                raise Exception(f"{res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Erro ao atualizar dados financeiro: {e}")
            logger.info("headers: %s", { "Authorization":f"Bearer {self.token}" })
            logger.info("payload: %s", payload_send)
        finally:
            pass

        return sucesso

    def formatarPayloadVenda(self,companyNumber:int,dadosRede:dict,dadosFinanceiro:dict) -> list[dict]:

        try:
            return [
                {
                    "pk":{
                            "NUFIN": dadosFinanceiro[i].get("nufin")
                        },
                    "values": {
                        "0": item['amountInfo'].get("amount"),
                        "1": datetime.strptime(item.get("expirationDate"), '%Y-%m-%d').strftime('%d/%m/%Y'),
                        "2": item.get("installmentNumber"),
                        "3": item.get("mdrAmount"),
                        "4": item.get("mdrFee"),
                        "5": item['amountInfo'].get("netAmount"),
                        "10": companyNumber
                    }
                }
                for i, item in enumerate(dadosRede.get("content",{}).get("installments",[]))
            ]
        except Exception as e:
            logger.error(f"Erro ao formatar payload: {e}")
            return []

    def formatarPayloadPagamento(self,dadosPagamento:dict,dadosFinanceiro:dict) -> list[dict]:

        pagamento:dict = {}
        matching_financeiro:dict = {}
        payload_upd_snk:list[dict] = []
        update:dict = {}       

        try:
            # Formata payload de atualização para a API Sankhya
            for i, pagamento in enumerate(dadosPagamento):
                matching_financeiro = next((f for f in dadosFinanceiro if int(f.get("ad_rede_salesumnum")) == pagamento.get("saleSummaryNumber") and datetime.strptime(f.get('ad_rede_expirationdate'),'%d/%m/%Y').strftime('%Y-%m-%d') == pagamento.get("paymentDate")), None)
                if matching_financeiro:
                    update = {
                        "pk": {
                            "NUFIN": matching_financeiro.get("nufin")
                        },
                        "values": {
                            "6": datetime.strptime(pagamento.get("paymentDate"), '%Y-%m-%d').strftime('%d/%m/%Y'),
                            "7": pagamento.get("paymentId")
                        }
                    }
                    payload_upd_snk.append(update)
            return payload_upd_snk
        except Exception as e:
            logger.error(f"Erro ao formatar payload: {e}")
            return []

class PagamentoService(AutenticacaoService):

    def __init__(self):
        self.token = None        
        super().__init__()
        self.fields:list = [
                    "AMOUNT",
                    "BANDEIRA",
                    "EXPIRATIONDATE",
                    "MDRAMOUNT",
                    "MDRFEE",
                    "NETAMOUNT",
                    "PAYMENTDATE",
                    "PAYMENTID"
                ]
        self.payload_registro:list[dict] = []
        self.payload_pagamento:list[dict] = []

    def formatarRetorno(self, res:dict) -> list:

        # RETORNO DE CONSULTA PELO DBEXPLORER
        if res.get('serviceName') == 'DbExplorerSP.executeQuery':
            field_names = [field['name'].lower() for field in res['responseBody']['fieldsMetadata']]
            result = [dict(zip(field_names, row)) for row in res['responseBody']['rows']]
            return result
        
        # RETORNO DE CONSULTA DE VIEW
        if res.get('serviceName') == 'CRUDServiceProvider.loadView':
            result = []
            if not res['responseBody']['records']:
                return result            
            aux = res['responseBody']['records']['record']
            if isinstance(aux, list):
                for item in res['responseBody']['records']['record']:
                    novo_dict = {str.lower(chave): valor['$'] for chave, valor in item.items()}
                    result.append(novo_dict)
            if isinstance(aux, dict):
                result.append({str.lower(chave): valor['$'] for chave, valor in aux.items()})
            return result

        # RETORNO VAZIO DE CONSULTA DE ENTIDADES
        if res['responseBody']['entities']['total'] == '0':
            return []

        # RETORNO DE CONSULTA DE ENTIDADES
        res_formatted = {}

        # Extrai as colunas
        columns = res['responseBody']['entities']['metadata']['fields']['field']
        if isinstance(columns, dict):
            columns = [columns]

        # Extrai retorno de 1 linha (dicionario)
        if res['responseBody']['entities']['total'] == '1':
            rows = [res['responseBody']['entities']['entity']]
            try:            
                for row in rows:
                    for i, column in enumerate(columns):                        
                        res_formatted[str.lower(column['name'])] = row.get(f'f{i}').get('$',None)
            except Exception as e:
                logger.error("Erro ao formatar dados da resposta. %s",e)
            finally:
                pass
            return [res_formatted]
        else:
        # Extrai retorno de várias linhas (lista de dicionarios)
            new_res = []
            rows = res['responseBody']['entities']['entity']

            # Se columns for uma lista, extrai no formato chave:valor
            if isinstance(columns, list):
                try:
                    for row in rows:
                        for i, column in enumerate(columns):
                            res_formatted[str.lower(column['name'])] = row.get(f'f{i}').get('$',None)  
                        new_res.append(res_formatted)
                        res_formatted = {}                        
                except Exception as e:
                    logger.error("Erro ao formatar dados da resposta. %s",e)
                finally:
                    pass
                return new_res

            # Se columns for um dicionario, extrai no formato chave:[valores]
            if isinstance(columns, dict):
                values = []
                try:            
                    for row in rows:
                        values.append(row.get('f0').get('$',None)) 
                    new_res = [{str.lower(columns['name']) : values}]
                except Exception as e:
                    logger.error("Erro ao formatar dados da resposta. %s",e)
                finally:
                    pass
                return new_res

    def formatarPayloadRegistro(self,dadosRede:dict,dadosSankhya:dict) -> bool:

        matching:dict = {}
        payload_upd_snk:list[dict] = []
        update:dict = {}       

        try:
            # Formata payload de atualização para a API Sankhya
            for i, item in enumerate(dadosSankhya):
                matching = next((f for f in dadosRede.get("content",{}).get("installments",[]) if int(f.get("installmentNumber")) == int(item.get("desdobramento"))), None)
                if matching:
                    update = {
                        "pk":{
                                "ID": str(item.get('idPgto'))
                            },
                        "values": {
                            "0": matching['amountInfo'].get("amount"),
                            "1": matching.get("brand"),
                            "2": datetime.strptime(matching.get("expirationDate"), '%Y-%m-%d').strftime('%d/%m/%Y'),
                            "3": matching.get("mdrAmount"),
                            "4": matching.get("mdrFee"),
                            "5": matching['amountInfo'].get("netAmount")
                        }
                    }
                    payload_upd_snk.append(update)
            self.payload_registro = payload_upd_snk
            return True
        except Exception as e:
            logger.error(f"Erro ao formatar payload de registro: {e}")
            return False

    def formatarPayloadPagamento(self,dadosPagamento:dict,dadosFinanceiro:dict) -> bool:

        pagamento:dict = {}
        matching_financeiro:dict = {}
        payload_upd_snk:list[dict] = []
        update:dict = {}       

        try:
            # Formata payload de atualização para a API Sankhya
            for i, pagamento in enumerate(dadosPagamento):
                matching_financeiro = next((f for f in dadosFinanceiro if int(f.get("salesumnum")) == pagamento.get("saleSummaryNumber") and datetime.strptime(f.get('expirationdate'),'%d/%m/%Y').strftime('%Y-%m-%d') == pagamento.get("paymentDate")), None)
                if matching_financeiro:
                    update = {
                        "pk": {
                            "ID": matching_financeiro.get("id")
                        },
                        "values": {
                            "6": datetime.strptime(pagamento.get("paymentDate"), '%Y-%m-%d').strftime('%d/%m/%Y'),
                            "7": pagamento.get("paymentId")
                        }
                    }
                    payload_upd_snk.append(update)
            self.payload_pagamento = payload_upd_snk
            return True
        except Exception as e:
            logger.error(f"Erro ao formatar payload de pagamento: {e}")
            return False

    @AutenticacaoService.accessToken
    def buscar(self,saleSummaryNumber:int=None,nsu:int=None,lista_saleSummaryNumber:list=None,lista_nsu:list=None) -> dict:

        def validaParametros(saleSummaryNumber,nsu,lista_saleSummaryNumber,lista_nsu):
            saleSummaryNumber = int(saleSummaryNumber) if saleSummaryNumber else None
            nsu = int(nsu) if nsu else None
            lista_saleSummaryNumber = [int(i) for i in lista_saleSummaryNumber] if lista_saleSummaryNumber else None
            lista_nsu = [int(i) for i in lista_nsu] if lista_nsu else None
            
            if not any([saleSummaryNumber,nsu,lista_saleSummaryNumber,lista_nsu]):
                raise ValueError("Nenhum critério de busca fornecido.")                

        def montaExpressao(saleSummaryNumber,nsu,lista_saleSummaryNumber,lista_nsu):
            nonlocal criteria
            
            try:
                if saleSummaryNumber:
                    criteria = {
                        "expression": {
                            "$": "this.SALESUMNUM = ?"
                        },
                        "parameter": [
                            {
                                "$": f"{saleSummaryNumber}",
                                "type": "I"
                            }
                        ]
                    }
                elif nsu:
                    criteria = {
                        "expression": {
                            "$": "this.NSU = ?"
                        },
                        "parameter": [
                            {
                                "$": f"{nsu}",
                                "type": "I"
                            }
                        ]
                    }
                elif lista_saleSummaryNumber:
                    criteria = {
                        "expression": {
                            "$": "this.SALESUMNUM IN ("+','.join('?' for _ in lista_saleSummaryNumber)+")"
                        },
                        "parameter": [ { "$": str(i), "type": "I" } for i in lista_saleSummaryNumber ]
                    }
                elif lista_nsu:
                    criteria = {
                        "expression": {
                            "$": "this.NSU IN ("+','.join('?' for _ in lista_nsu)+")"
                        },
                        "parameter": [ { "$": str(i), "type": "I" } for i in lista_nsu ]
                    }
                else:
                    pass
                return True
            except Exception as e:
                logger.error(f"Erro ao montar expressão: {e}")
                return False

        dados_pagamento:dict = {}
        url:str = 'https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=CRUDServiceProvider.loadRecords&outputType=json'
        fieldset_list:str = '*'
        criteria:dict={}
        payload:dict={}

        validaParametros(saleSummaryNumber,nsu,lista_saleSummaryNumber,lista_nsu)
        montaExpressao(saleSummaryNumber,nsu,lista_saleSummaryNumber,lista_nsu)

        try:
            payload = {
                    "serviceName": "CRUDServiceProvider.loadRecords",
                    "requestBody": {
                        "dataSet": {
                            "rootEntity": "AD_REDEPAGAMENTO",
                            "includePresentationFields": "N",
                            "offsetPage": "0",
                            "criteria": criteria,
                            "entity": {
                                "fieldset": {
                                    "list": fieldset_list
                                }
                            }
                        }
                    }
                }

            res = requests.get(
                url=url,
                headers={ "Authorization":f"Bearer {self.token}" },
                json=payload
            )
            
            if res.ok and res.json().get('status') in ['0','1']:
                dados_pagamento = self.formatarRetorno(res.json())
            else:
                raise Exception(f"{res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Erro ao buscar dados do pagamento: {e}")
        finally:
            pass

        return dados_pagamento

    @AutenticacaoService.accessToken
    def enviar(self,payload:list[dict]=None) -> bool:
        
        sucesso:bool = False
        url:str = 'https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=DatasetSP.save&outputType=json'       
        if not payload:
            payload = self.payload_registro
            if not payload:
                return False

        payload_send = {
            "serviceName":"DatasetSP.save",
            "requestBody":{
                "entityName":"AD_REDEPAGAMENTO",
                "standAlone":False,
                "fields":self.fields,
                "records": payload
            }
        }
        headers = { "Authorization":f"Bearer {self.token}" }

        logger.info(f"Enviando headers de registro para a API Sankhya: {headers}")
        logger.info(f"Enviando payload de registro para a API Sankhya: {payload_send}")        

        try:
            res = requests.post(
                url=url,
                headers=headers,
                json=payload_send
            )
            if res.ok and res.json().get('status') in ['0','1']:
                sucesso = True if res.json().get('status') == '1' else False
            else:
                raise Exception(f"{res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Erro ao enviar dados pagamento: {e}")
            logger.info("headers: %s", { "Authorization":f"Bearer {self.token}" })
            logger.info("payload: %s", payload_send)
        finally:
            pass

        return sucesso
    
    @AutenticacaoService.accessToken
    def atualizar(self,payload:list[dict]=None) -> bool:
        
        sucesso:bool = False
        url:str = 'https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=DatasetSP.save&outputType=json'        
        if not payload:
            payload = self.payload_pagamento
            if not payload:
                return False
                    
        payload_send = {
            "serviceName":"DatasetSP.save",
            "requestBody":{
                "entityName":"AD_REDEPAGAMENTO",
                "standAlone":False,
                "fields":self.fields,
                "records": payload
            }
        }
        headers = { "Authorization":f"Bearer {self.token}" }

        logger.info(f"Enviando payload de atualização para a API Sankhya: {payload_send}")
        try:
            res = requests.post(
                url=url,
                headers=headers,
                json=payload_send
            )
            if res.ok and res.json().get('status') in ['0','1']:
                sucesso = True if res.json().get('status') == '1' else False
            else:
                raise Exception(f"{res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Erro ao atualizar dados do pagamento: {e}")
            logger.info("headers: %s", { "Authorization":f"Bearer {self.token}" })
            logger.info("payload: %s", payload_send)
        finally:
            pass

        return sucesso    