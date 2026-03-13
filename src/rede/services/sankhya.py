import os, requests, json
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

    def salvar_token(self, token: dict) -> bool:
        
        status:bool = False
        with get_session() as session:
            token_servicedb = TokenService(db=session)
            try:                
                token_servicedb.salvar_token(
                    sistema=self.sistema,
                    access_token=token.get('token',''),
                    refresh_token='',
                    expires_at=datetime.strptime(token.get('dhExpiracaoToken',''), "%Y-%m-%dT%H:%M:%S.%f") if token.get('dhExpiracaoToken') else None
                )
                status = True
            except Exception as e:
                logger.error(f"Erro ao salvar o token no banco de dados: {e}")
            finally:
                session.close()
        return status

    def carregar_token(self) -> dict:
        token:dict = {}
        with get_session() as session:
            token_servicedb = TokenService(db=session)
            try:
                token_db = token_servicedb.obter_token(sistema=self.sistema)
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

    def autenticar(self) -> bool:

        token:dict = self.carregar_token()
        if not token or not token.get('expires_at') or token.get('expires_at') <= datetime.now():
            token = self.logar()
            if token:
                self.salvar_token(token)
                self.token = token.get('token', '')
                return True
            else:
                return False
        else:
            self.token = token.get('token', '')
            return True

class FinanceiroService(AutenticacaoService):

    def __init__(self):
        super().__init__()
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

    def formatar_retorno(self, res:dict) -> list:

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

    def buscar(self,token:str=None,saleSummaryNumber:int=None,lista:list=None) -> dict:

        def monta_expressao(saleSummaryNumber:int=None,lista:list=None):
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

        if not token:
            token = self.token

        try:
            saleSummaryNumber = int(saleSummaryNumber) if saleSummaryNumber else None
            lista = [int(i) for i in lista] if lista else None
            
            if not monta_expressao(saleSummaryNumber=saleSummaryNumber,lista=lista):
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
                headers={ "Authorization":f"Bearer {token}" },
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
        
    def atualizar(self,payload:list[dict],token:str=None) -> bool:
        
        sucesso:bool = False
        url:str = 'https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=DatasetSP.save&outputType=json'        
        if not token:
            token = self.token        
        payload_send = {
            "serviceName":"DatasetSP.save",
            "requestBody":{
                "entityName":"Financeiro",
                "standAlone":False,
                "fields":self.fields,
                "records": payload
            }
        }
        headers = { "Authorization":f"Bearer {token}" }

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
            logger.info("headers: %s", { "Authorization":f"Bearer {token}" })
            logger.info("payload: %s", payload_send)
        finally:
            pass

        return sucesso

    def formatar_payload_venda(self,companyNumber:int,dados_rede:dict,dados_financeiro:dict) -> list[dict]:

        try:
            return [
                {
                    "pk":{
                            "NUFIN": dados_financeiro[i].get("nufin")
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
                for i, item in enumerate(dados_rede.get("content",{}).get("installments",[]))
            ]
        except Exception as e:
            logger.error(f"Erro ao formatar payload: {e}")
            return []

    def formatar_payload_pagamento(self,dados_pagamento:dict,dados_financeiro:dict) -> list[dict]:

        pagamento:dict = {}
        matching_financeiro:dict = {}
        payload_upd_snk:list[dict] = []
        update:dict = {}       

        try:
            # Formata payload de atualização para a API Sankhya
            for i, pagamento in enumerate(dados_pagamento):
                matching_financeiro = next((f for f in dados_financeiro if int(f.get("ad_rede_salesumnum")) == pagamento.get("saleSummaryNumber") and datetime.strptime(f.get('ad_rede_expirationdate'),'%d/%m/%Y').strftime('%Y-%m-%d') == pagamento.get("paymentDate")), None)
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

    def formatar_retorno(self, res:dict) -> list:

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

    def formatar_payload_registro(self,dados_rede:dict,dados_sankhya:dict) -> bool:

        matching:dict = {}
        payload_upd_snk:list[dict] = []
        update:dict = {}       

        try:
            # Formata payload de atualização para a API Sankhya
            for i, item in enumerate(dados_sankhya):
                matching = next((f for f in dados_rede.get("content",{}).get("installments",[]) if int(f.get("installmentNumber")) == int(item.get("desdobramento"))), None)
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

    def formatar_payload_pagamento(self,dados_pagamento:dict,dados_financeiro:dict) -> bool:

        pagamento:dict = {}
        matching_financeiro:dict = {}
        payload_upd_snk:list[dict] = []
        update:dict = {}       

        try:
            # Formata payload de atualização para a API Sankhya
            for i, pagamento in enumerate(dados_pagamento):
                matching_financeiro = next((f for f in dados_financeiro if int(f.get("salesumnum")) == pagamento.get("saleSummaryNumber") and datetime.strptime(f.get('expirationdate'),'%d/%m/%Y').strftime('%Y-%m-%d') == pagamento.get("paymentDate")), None)
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

    def buscar(self,token:str=None,saleSummaryNumber:int=None,nsu:int=None,lista_saleSummaryNumber:list=None,lista_nsu:list=None) -> dict:

        def valida_parametros(saleSummaryNumber,nsu,lista_saleSummaryNumber,lista_nsu):
            saleSummaryNumber = int(saleSummaryNumber) if saleSummaryNumber else None
            nsu = int(nsu) if nsu else None
            lista_saleSummaryNumber = [int(i) for i in lista_saleSummaryNumber] if lista_saleSummaryNumber else None
            lista_nsu = [int(i) for i in lista_nsu] if lista_nsu else None
            
            if not any([saleSummaryNumber,nsu,lista_saleSummaryNumber,lista_nsu]):
                raise ValueError("Nenhum critério de busca fornecido.")                

        def monta_expressao(saleSummaryNumber,nsu,lista_saleSummaryNumber,lista_nsu):
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

        if not token:
            token = self.token

        valida_parametros(saleSummaryNumber,nsu,lista_saleSummaryNumber,lista_nsu)
        monta_expressao(saleSummaryNumber,nsu,lista_saleSummaryNumber,lista_nsu)

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
                headers={ "Authorization":f"Bearer {token}" },
                json=payload
            )
            
            if res.ok and res.json().get('status') in ['0','1']:
                dados_pagamento = self.formatar_retorno(res.json())
            else:
                raise Exception(f"{res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Erro ao buscar dados do pagamento: {e}")
        finally:
            pass

        return dados_pagamento

    def enviar(self,token:str=None,payload:list[dict]=None) -> bool:
        
        sucesso:bool = False
        url:str = 'https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=DatasetSP.save&outputType=json'       
        if not payload:
            payload = self.payload_registro
            if not payload:
                return False

        if not token:
            token = self.token

        payload_send = {
            "serviceName":"DatasetSP.save",
            "requestBody":{
                "entityName":"AD_REDEPAGAMENTO",
                "standAlone":False,
                "fields":self.fields,
                "records": payload
            }
        }
        headers = { "Authorization":f"Bearer {token}" }

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
            logger.info("headers: %s", { "Authorization":f"Bearer {token}" })
            logger.info("payload: %s", payload_send)
        finally:
            pass

        return sucesso
    
    def atualizar(self,token:str=None,payload:list[dict]=None) -> bool:
        
        sucesso:bool = False
        url:str = 'https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=DatasetSP.save&outputType=json'        
        if not payload:
            payload = self.payload_pagamento
            if not payload:
                return False

        if not token:
            token = self.token
                    
        payload_send = {
            "serviceName":"DatasetSP.save",
            "requestBody":{
                "entityName":"AD_REDEPAGAMENTO",
                "standAlone":False,
                "fields":self.fields,
                "records": payload
            }
        }
        headers = { "Authorization":f"Bearer {token}" }

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
            logger.error(f"Erro ao atualizar dados do pagamento: {e}")
            logger.info("headers: %s", { "Authorization":f"Bearer {token}" })
            logger.info("payload: %s", payload_send)
        finally:
            pass

        return sucesso    