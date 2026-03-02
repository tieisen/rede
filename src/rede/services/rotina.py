from datetime import date
from src.rede.services.rede import VendasService
from src.rede.services.sankhya import PagamentoService
from dotenv import load_dotenv
from src.rede.utils.log import set_logger
logger = set_logger(__name__)
load_dotenv()

class RotinaService():

    def __init__(self):
        self.snk_pgto = PagamentoService()
        self.rede_venda = VendasService()

    def registrar_dados_pagamento(self,companyNumber:int,dataVendas:date,nsu:int) -> dict:

        payload_pgto:dict = {}
        dados_rede:dict = {}
        retorno:dict = {"sucesso": False, "dados": [], "mensagem": ""}

        logger.info(f"Registrando dados de pagamento para companyNumber={companyNumber}, dataVendas={dataVendas}, nsu={nsu}")
        try:
            logger.info("- Autenticando com as APIs...")
            if not self.snk_pgto.autenticar():
                raise Exception("Falha na autenticação com a API Sankhya.")
            if not self.rede_venda.autenticar():
                raise Exception("Falha na autenticação com a API Rede.")
            
            logger.info("- Consultando dados de pagamento na API Rede...")
            dados_rede = self.rede_venda.consultar_vendas_parceladas(companyNumber=companyNumber,startDate=dataVendas,endDate=dataVendas,nsu=nsu)
            if 'message' in dados_rede:
                raise Exception(dados_rede.get('message'))
            
            logger.info("- Formatando payload de retorno...")
            payload_pgto = self.rede_venda.formatar_payload_consulta_vendas_parceladas()
            if not payload_pgto:
                raise Exception("Falha ao formatar payload de registro.")
            retorno['dados'] = payload_pgto
            retorno['sucesso'] = True
            
            logger.info("- pass")
        except Exception as e:
            msg = f"Erro ao registrar dados de pagamento: {str(e)}"
            retorno['mensagem'] = msg
            logger.error(msg)
            logger.info("dados_rede: %s", dados_rede)
            logger.info("payload_pgto: %s", payload_pgto)
        finally:
            pass

        return retorno

    def atualizar_dados_pagamento(self,companyNumber:int,startDate:date,endDate:date) -> dict:

        dados_pagamento_raw:list[dict] = []
        dados_pagamento:list[dict] = []
        lista_salesumnum:list[int] = []
        dados_financeiro:list[dict] = []
        upd_pgto_snk:dict = {}
        retorno:dict = {"sucesso": False, "mensagem": ""}

        try:
            logger.info("- Autenticando com as APIs...")
            if not self.rede_venda.autenticar():
                raise Exception("Falha na autenticação com a API Sankhya.")
            if not self.snk_pgto.autenticar():
                raise Exception("Falha na autenticação com a API Rede.")
            
            logger.info("- Buscando dados de pagamento na API Rede...")
            # Busca dados de pagamento na API Rede
            dados_pagamento_raw = self.rede_venda.consultar_pagamentos_oc(companyNumber=companyNumber,
                                                                          startDate=startDate,
                                                                          endDate=endDate)
            if 'message' in dados_pagamento_raw:
                raise Exception(dados_pagamento_raw.get('message'))
            if not dados_pagamento_raw['content'].get('paymentsCreditOrders'):
                return {"sucesso": True, "mensagem": f"Nenhum pagamento encontrado para o período especificado ({startDate.strftime('%d/%m/%Y')}-{endDate.strftime('%d/%m/%Y')})."}
            dados_pagamento = dados_pagamento_raw['content']['paymentsCreditOrders']

            logger.info("- Buscando dados financeiros na API Sankhya...")
            # Busca dados financeiros na API Sankhya com base nos salesSummaryNumber dos pagamentos encontrados
            lista_salesumnum = [d.get('saleSummaryNumber') for d in dados_pagamento]
            if not lista_salesumnum:
                raise Exception("Nenhum saleSummaryNumber encontrado nos pagamentos")
            
            dados_financeiro = self.snk_pgto.buscar(lista_saleSummaryNumber=lista_salesumnum)                
            if not dados_financeiro:
                raise Exception("Nenhum registro financeiro encontrado para os salesSummaryNumber")

            logger.info("- Formatando payload de atualização para a API Sankhya...")
            # Formata payload de atualização para a API Sankhya com base nos dados de pagamento e financeiro encontrados
            if not self.snk_pgto.formatar_payload_pagamento(dados_pagamento=dados_pagamento, dados_financeiro=dados_financeiro):
                raise Exception("Falha ao formatar payload financeiro.")

            logger.info("- Atualizando dados financeiros na API Sankhya...")
            upd_pgto_snk = self.snk_pgto.atualizar()
            retorno['sucesso'] = upd_pgto_snk
            if not upd_pgto_snk:
                raise Exception("Falha ao atualizar dados financeiro.")
            logger.info("- pass")
        except Exception as e:
            msg = f"Erro ao atualizar dados financeiro: {str(e)}"
            retorno['mensagem'] = msg
            logger.error(msg)
            logger.info("dados_pagamento_raw: %s", dados_pagamento_raw)
            logger.info("dados_financeiro: %s", dados_financeiro)
            logger.info("payload: %s", self.snk_pgto.payload_pagamento)
        finally:
            pass

        return retorno
    