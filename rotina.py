from datetime import date
from rede import Autenticacao as redeAuth
from rede import Vendas as redeVendas
from sankhya import Autenticacao as snkAuth
from sankhya import Financeiro as snkFinanceiro
from dotenv import load_dotenv
from log import set_logger
logger = set_logger(__name__)
load_dotenv()

class Rotina():

    def __init__(self):
        pass

    def atualizar_dados_financeiro(self,companyNumber:int,dataVendas:date,nsu:int,dados_financeiro:dict) -> dict:

        snk_auth = snkAuth()
        snk_fin = snkFinanceiro()
        rede_auth = redeAuth()
        rede_venda = redeVendas()

        payload_fin_snk:dict = {}
        upd_fin_snk:dict = {}
        dados_rede:dict = {}
        retorno:dict = {"sucesso": False, "mensagem": ""}
        tkn_snk:str = ''
        tkn_rede:str = ''

        try:
            tkn_snk = snk_auth.autenticar()
            if not tkn_snk:
                raise Exception("Falha na autenticação com a API Sankhya.")
            tkn_rede = rede_auth.autenticar()
            if not tkn_rede:
                raise Exception("Falha na autenticação com a API Rede.")
            
            dados_rede = rede_venda.consultar_vendas_parceladas(token=tkn_rede,companyNumber=companyNumber,startDate=dataVendas,endDate=dataVendas,nsu=nsu)
            if 'message' in dados_rede:
                raise Exception(dados_rede.get('message'))
            
            payload_fin_snk = snk_fin.formatar_payload(dados_rede=dados_rede,dados_financeiro=dados_financeiro)
            if not payload_fin_snk:
                raise Exception("Falha ao formatar payload financeiro.")

            upd_fin_snk = snk_fin.atualizar(token=tkn_snk, payload=payload_fin_snk)
            retorno['sucesso'] = upd_fin_snk
            if not upd_fin_snk:
                raise Exception("Falha ao atualizar dados financeiro.")
        except Exception as e:
            msg = f"Erro ao atualizar dados financeiro: {str(e)}"
            retorno['mensagem'] = msg
            logger.error(msg)
            logger.info("token_snk: %s", tkn_snk)
            logger.info("token_rede: %s", tkn_rede)
            logger.info("dados_rede: %s", dados_rede)
            logger.info("payload_fin_snk: %s", payload_fin_snk)
        finally:
            pass

        return retorno