from datetime import date
from src.rede.services.rede import AutenticacaoService as redeAuth
from src.rede.services.rede import VendasService
from src.rede.services.sankhya import AutenticacaoService as snkAuth
from src.rede.services.sankhya import FinanceiroService
from dotenv import load_dotenv
from src.rede.utils.log import set_logger
logger = set_logger(__name__)
load_dotenv()

class RotinaService():

    def __init__(self):
        pass

    def atualizar_dados_financeiro(self,companyNumber:int,dataVendas:date,nsu:int,dados_financeiro:dict) -> dict:

        snk_auth = snkAuth()
        snk_fin = FinanceiroService()
        rede_auth = redeAuth()
        rede_venda = VendasService()

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
            
            payload_fin_snk = snk_fin.formatar_payload_venda(companyNumber=companyNumber, dados_rede=dados_rede,dados_financeiro=dados_financeiro)
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

    def atualizar_dados_pagamento(self,companyNumber:int,startDate:date,endDate:date) -> dict:

        snk_auth = snkAuth()
        snk_fin = FinanceiroService()
        rede_auth = redeAuth()
        rede_venda = VendasService()

        dados_pagamento_raw:list[dict] = []
        dados_pagamento:list[dict] = []
        lista_salesumnum:list[int] = []
        dados_financeiro:list[dict] = []
        payload_upd_snk:list[dict] = []
        upd_fin_snk:dict = {}
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
            
            # Busca dados de pagamento na API Rede
            dados_pagamento_raw = rede_venda.consultar_pagamentos_oc(token=tkn_rede,
                                                                     companyNumber=companyNumber,
                                                                     startDate=startDate,
                                                                     endDate=endDate)
            if 'message' in dados_pagamento_raw:
                raise Exception(dados_pagamento_raw.get('message'))
            if not dados_pagamento_raw['content'].get('paymentsCreditOrders'):
                return {"sucesso": True, "mensagem": f"Nenhum pagamento encontrado para o período especificado ({startDate.strftime('%d/%m/%Y')}-{endDate.strftime('%d/%m/%Y')})."}
            dados_pagamento = dados_pagamento_raw['content']['paymentsCreditOrders']

            # Busca dados financeiros na API Sankhya com base nos salesSummaryNumber dos pagamentos encontrados
            lista_salesumnum = [d.get('saleSummaryNumber') for d in dados_pagamento]
            if not lista_salesumnum:
                raise Exception("Nenhum saleSummaryNumber encontrado nos pagamentos")
            
            dados_financeiro = snk_fin.buscar(token=tkn_snk,lista=lista_salesumnum)                
            if not dados_financeiro:
                raise Exception("Nenhum registro financeiro encontrado para os salesSummaryNumber")

            # Formata payload de atualização para a API Sankhya com base nos dados de pagamento e financeiro encontrados
            payload_upd_snk = snk_fin.formatar_payload_pagamento(dados_pagamento=dados_pagamento, dados_financeiro=dados_financeiro)
            if not payload_upd_snk:
                raise Exception("Falha ao formatar payload financeiro.")

            upd_fin_snk = snk_fin.atualizar(token=tkn_snk, payload=payload_upd_snk)
            retorno['sucesso'] = upd_fin_snk
            if not upd_fin_snk:
                raise Exception("Falha ao atualizar dados financeiro.")
        except Exception as e:
            msg = f"Erro ao atualizar dados financeiro: {str(e)}"
            retorno['mensagem'] = msg
            logger.error(msg)
            logger.info("token_snk: %s", tkn_snk)
            logger.info("token_rede: %s", tkn_rede)
            logger.info("dados_pagamento_raw: %s", dados_pagamento_raw)
            logger.info("dados_financeiro: %s", dados_financeiro)
            logger.info("payload_upd_snk: %s", payload_upd_snk)
        finally:
            pass

        return retorno
    