import os, requests, json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from log import set_logger
logger = set_logger(__name__)
load_dotenv()

class Autenticacao():

    def __init__(self):
        self.caminho_arquivo_token = os.getenv("PATH_TOKEN_SNK", "")
        self.x_token = os.getenv("X_TOKEN", "")
        self.client_id = os.getenv("CLIENT_ID", "")
        self.client_secret = os.getenv("CLIENT_SECRET", "")

        if not any([self.caminho_arquivo_token, self.x_token, self.client_id, self.client_secret]):
            logger.critical("Variáveis de ambiente não configuradas corretamente para SANKHYA.")
            raise Exception("Variáveis de ambiente não configuradas corretamente para SANKHYA.")


    def salvar_token_arquivo(self, token: dict) -> bool:
        
        def calcular_expiracao(segundos: int) -> str:
            try:
                expiracao = datetime.now() + timedelta(seconds=(segundos-60))
                return expiracao.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                logger.error(f"Erro ao calcular expiração do token: {e}")
                return ""

        status:bool = False
        try:
            token['expiration_datetime'] = calcular_expiracao(token.get('expires_in', 0))
            with open(self.caminho_arquivo_token, 'w') as arquivo:
                arquivo.write(json.dumps(token,ensure_ascii=False, indent=4))
            status = True
        except Exception as e:
            logger.error(f"Erro ao salvar o token no arquivo: {e}")
        finally:
            pass
        return status

    def carregar_token_arquivo(self) -> dict:

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

    def solicitar_token(self) -> dict:

        url = 'https://api.sankhya.com.br/authenticate'

        header = {
            'X-Token':self.x_token,
            'accept':'application/x-www-form-urlencoded',
            'content-type':'application/x-www-form-urlencoded'
        }

        body = {
            'grant_type':'client_credentials',
            'client_id':self.client_id,
            'client_secret':self.client_secret
        }

        res = requests.post(
            url=url,
            headers=header,
            data=body)
        
        if res.ok:
            return res.json()
        else:
            logger.error(f"Erro ao solicitar token: {res.status_code} - {res.text}")
            return {}

    def autenticar(self) -> str:

        token:dict = self.carregar_token_arquivo()
        if not token or datetime.strptime(token.get('expiration_datetime', '1970-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S') <= datetime.now():
            token = self.solicitar_token()
            if token:
                self.salvar_token_arquivo(token)
                return token.get('access_token', '')
            else:
                return ''
        else:
            return token.get('access_token', '')

class Financeiro():

    def __init__(self):
        pass

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
                    return new_res

    def buscar(self,token:str,nufin:int=None,nunota:int=None,numnota:int=None) -> dict:

        def monta_expressao(nufin:int=None,nunota:int=None,numnota:int=None):
            nonlocal criteria

            if not any([nufin,nunota,numnota]):
                return False
            
            try:
                if nufin:
                    criteria = {
                        "expression": {
                            "$": "this.NUFIN = ?"
                        },
                        "parameter": [
                            {
                                "$": f"{nufin}",
                                "type": "I"
                            }
                        ]
                    }
                elif nunota:
                    criteria = {
                        "expression": {
                            "$": "this.NUNOTA = ?"
                        },
                        "parameter": [
                            {
                                "$": f"{nunota}",
                                "type": "I"
                            }
                        ]
                    }
                elif numnota:
                    criteria = {
                        "expression": {
                            "$": "this.NUMNOTA = ?"
                        },
                        "parameter": [
                            {
                                "$": f"{numnota}",
                                "type": "I"
                            }
                        ]
                    }
                else:
                    pass
                return True
            except Exception as e:
                logger.error(f"Erro ao montar expressão: {e}")
                return False

        dados_financeiro:dict = {}
        url:str = 'https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=CRUDServiceProvider.loadRecords&outputType=json'
        fieldset_list:str = '*'
        criteria:dict={}

        try:
            nufin = int(nufin) if nufin else None
            nunota = int(nunota) if nunota else None
            numnota = int(numnota) if numnota else None
            
            if not monta_expressao(nufin=nufin,nunota=nunota,numnota=numnota):
                raise ValueError("Nenhum critério de busca fornecido.")

            res = requests.get(
                url=url,
                headers={ "Authorization":f"Bearer {token}" },
                json={
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
                })
            
            if res.ok and res.json().get('status') in ['0','1']:
                dados_financeiro = self.formatar_retorno(res.json())
            else:
                raise Exception(f"{res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Erro ao buscar dados financeiro: {e}")
        finally:
            pass

        return dados_financeiro
        
    def atualizar(self,token:str,payload:list[dict]) -> bool:
        
        sucesso:bool = False
        url:str = 'https://api.sankhya.com.br/gateway/v1/mge/service.sbr?serviceName=DatasetSP.save&outputType=json'        
        _payload = {
            "serviceName":"DatasetSP.save",
            "requestBody":{
                "entityName":"Financeiro",
                "standAlone":False,
                "fields":[
                    "AD_REDE_AMOUNT",
                    "AD_REDE_EXPIRATIONDATE",
                    "AD_REDE_INSTALLMENTNUM",
                    "AD_REDE_MDRAMOUNT",
                    "AD_REDE_MDRFEE",
                    "AD_REDE_NETAMOUNT",
                    "AD_REDE_PAYMENTDATE",
                    "AD_REDE_PAYMENTID",
                    "AD_REDE_PROCESSADO",
                    "AD_REDE_TID"
                ],
                "records": payload
            }
        }

        try:
            res = requests.post(
                url=url,
                headers={ 'Authorization' : f"Bearer {token}" },
                json=_payload
            )
            if res.ok and res.json().get('status') in ['0','1']:
                sucesso = True if res.json().get('status') == '1' else False
            else:
                raise Exception(f"{res.status_code} - {res.text}")
        except Exception as e:
            logger.error(f"Erro ao atualizar dados financeiro: {e}")
            logger.info("headers: %s", { 'Authorization' : f"Bearer {token}" })
            logger.info("payload: %s", _payload)
        finally:
            pass

        return sucesso

    def formatar_payload(self,dados_rede:dict,dados_financeiro:dict) -> list[dict]:

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
                        "5": item['amountInfo'].get("netAmount")
                    }
                }
                for i, item in enumerate(dados_rede.get("content",{}).get("installments",[]))
            ]
        except Exception as e:
            logger.error(f"Erro ao formatar payload: {e}")
            return []
