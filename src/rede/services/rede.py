import os, base64, requests
from typing import Literal
from functools import wraps
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
from src.rede.utils.log import set_logger
from src.rede.services.token import TokenService
from src.rede.database.database import get_session
logger = set_logger(__name__)
load_dotenv()

class AutenticacaoService:

    def __init__(self,ambiente: Literal['trn', 'prd']='prd',pacote: Literal['pgto', 'vendas']='vendas',auth:str=''):
        """
            Parametros:
                ambiente: 'trn' (sandbox) | 'prd'
                pacote: 'pgto' (link de pagamento) | 'vendas' (extrato)
                auth: client_id:client_secret. BASIC_CLIENT_SP do .env tem prioridade

            Gera Exception se PATH_TOKEN_REDE ou a credencial não estiverem configurados.
        """

        self.sistema = 'rede'
        self.ambiente = ambiente
        self.pacote = pacote
        self.auth = os.getenv('BASIC_CLIENT_SP',auth)
        self.caminho_arquivo_token = os.getenv("PATH_TOKEN_REDE", "")
        self.token = None

        if not all([self.caminho_arquivo_token, self.auth]):
            logger.critical("Variáveis de ambiente não configuradas corretamente para REDE.")
            raise Exception("Variáveis de ambiente não configuradas corretamente para REDE.")

    def converterBase64(self,texto:str) -> str:
        """
            Converte um texto para base64 (usado no header Basic da autenticação).

            Parametros:
                texto: str

            Retorno: texto em base64 ou '' em caso de erro
        """

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

    def validarAmbienteAuth(self) -> dict:
        """
            Monta o header Authorization e a URL de autenticação conforme pacote e ambiente.

            Retorno:
                {"authorization": "Basic ...", "url": URL_AUTH_*}
                {} em caso de erro
        """

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
                    dados_ambiente['authorization']=f"Basic {self.converterBase64(self.auth)}"
                    dados_ambiente['url']=os.getenv('URL_AUTH_PT')
                case ('pgto', 'prd'):
                    dados_ambiente['authorization']=f"Basic {self.converterBase64(self.auth)}"
                    dados_ambiente['url']=os.getenv('URL_AUTH_PP')
                    pass                
                case ('vendas', 'trn'):
                    dados_ambiente['authorization']=f"Basic {self.converterBase64(self.auth)}"
                    dados_ambiente['url']=os.getenv('URL_AUTH_ST')
                case ('vendas', 'prd'):
                    dados_ambiente['authorization']=f"Basic {self.converterBase64(self.auth)}"
                    dados_ambiente['url']=os.getenv('URL_AUTH_SP')
                case _:
                    raise ValueError("Erro ao validar ambiente: combinação de pacote e ambiente desconhecida")
        except Exception as e:
            logger.error(f"Erro ao validar ambiente: {e}")

        return dados_ambiente

    def calcularExpiracao(self,dados:dict) -> bool:
        """
            Acrescenta ao retorno da autenticação os campos request_time e expire_time
            (AAAA-MM-DD HH:MM:SS), calculados a partir de expires_in.

            Parametros:
                dados: retorno da autenticação (alterado no próprio dict)

            Retorno: True se calculou, False em caso de erro
        """

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

    def logar(self) -> dict:
        """
            Solicita um novo token na API Rede (OAuth2 client_credentials).

            Retorno:
                access_token, expires_in, ... + request_time e expire_time

            Gera ConnectionError se a API retornar erro.
        """
        
        self.dados_ambiente = self.validarAmbienteAuth()
        res:requests.Response=None
        dados:dict={}
        header:dict={}
        body:dict={}

        try:
            assert isinstance(self.dados_ambiente,dict)
            if not self.dados_ambiente:
                raise ValueError("Não foi possível validar o ambiente")
            
            if not self.dados_ambiente:
                raise ValueError("Não foi possível validar o ambiente")
            
            header={
                "Authorization": self.dados_ambiente.get('authorization'),
                "Content-Type": "application/x-www-form-urlencoded"
            }

            body={
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
            if res and res.ok:
                dados = res.json()
                self.calcularExpiracao(dados=dados)
            else:           
                raise ConnectionError(f"Erro {res.status_code}: {res.text}")
        return dados

    def salvarToken(self, dadosToken: dict) -> bool:
        """
        Salva o token no banco de dados.            
            :param token: token a ser salvo.
        """

        status:bool = False
        token:str = dadosToken.get('access_token')
        expire_date:datetime = datetime.strptime(dadosToken.get('expire_time',''), "%Y-%m-%d %H:%M:%S")
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
        """
        Carrega o token do banco de dados.
            :return dict: token carregado.
        """
        token:dict = {}
        with get_session() as session:
            token_servicedb = TokenService(db=session)
            try:
                token = token_servicedb.obterToken(sistema=self.sistema)
                if token:
                    return token.__dict__
                else:
                    logger.warning("Token não encontrado no banco de dados.")                    
            except Exception as e:
                logger.error(f"Erro ao buscar o token no banco de dados: {e}")
            finally:
                session.close()
        return token
    
    def validarToken(self) -> bool:
        """
            Carrega o token salvo no banco e verifica se ainda é válido.
            Preenche self.token com o token encontrado.

            Retorno: True se o token existe e não expirou
        """

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
        """
            Gera um novo token na API Rede e salva no banco.

            Retorno: True se salvou
        """

        status:bool = False
        dados_token:dict = self.logar()
        if dados_token:
            self.token = dados_token.get('access_token', '')
            status = self.salvarToken(dados_token)            
        return status    

    def autenticar(self) -> str:
        """
            Retorna um token válido: usa o salvo no banco ou gera um novo se expirou.

            Retorno: access_token
        """

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

class LinkPagamentoService(AutenticacaoService):

    def __init__(self):
        """
            Inicializa o serviço com os padrões de AutenticacaoService (ambiente 'prd').
        """

        super().__init__()
        self.token = None

    def validarAmbienteLink(self,ambiente: Literal['trn', 'prd']=None) -> str:
        """
            Retorna a URL base da API de link de pagamento para o ambiente.

            Parametros:
                ambiente?: 'trn' | 'prd'. Se não informado, usa self.ambiente

            Retorno: URL_PT ou URL_PP do .env
        """

        ambientes_validos = ['trn','prd']
        url:str=''
        if not ambiente:
            ambiente = self.ambiente
            if not ambiente:
                raise ValueError("Ambiente não informado")        

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

    @AutenticacaoService.accessToken
    def consultarDetalhesLink(self,paymentLinkId:str,companyNumber:str,ambiente: Literal['trn', 'prd']=None) -> dict:
        """
            Consulta os detalhes de um link de pagamento na API Rede.

            Request:
                paymentLinkId: str
                companyNumber: str (enviado no header Company-number)
                ambiente?: 'trn' | 'prd'

            Response: JSON da API Rede

            *Não é utilizado*
        """

        data:dict={}
        url:str=''
        header:dict={}
        res:requests.Response=None

        url=self.validarAmbienteLink(ambiente=ambiente)
        url+=f'/details/{paymentLinkId}'

        header={
            "Authorization": f"Bearer {self.token}",
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

    @AutenticacaoService.accessToken
    def criarLink(self,companyNumber:str,body:dict,ambiente: Literal['trn', 'prd']=None) -> dict:
        """
            Cria um link de pagamento na API Rede.

            Request:
                companyNumber: str (enviado no header Company-number)
                body: payload do link conforme a documentação da Rede
                ambiente?: 'trn' | 'prd'

            Response: JSON da API Rede

            *Não é utilizado*
        """

        data:dict={}
        url:str=''
        header:dict={}
        res:requests.Response=None

        url = self.validarAmbienteLink(ambiente=ambiente)
        url+='/create'            

        header={
            "Authorization": f"Bearer {self.token}",
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

class VendasService(AutenticacaoService):

    def __init__(self):
        """
            Inicializa o serviço com os padrões de AutenticacaoService (ambiente 'prd', pacote 'vendas').
        """

        super().__init__()
        self.token = None        

    def validarAmbienteVendas(self,ambiente: Literal['trn', 'prd']=None) -> str:
        """
            Retorna a URL base da API de extrato (merchant-statement) para o ambiente.

            Parametros:
                ambiente?: 'trn' | 'prd'. Se não informado, usa self.ambiente

            Retorno: URL_ST ou URL_SP do .env

            Gera ValueError se o ambiente não for informado ou for inválido.
        """

        ambientes_validos = ['trn','prd']
        url:str=''
        if not ambiente:
            ambiente = self.ambiente
            if not ambiente:
                raise ValueError("Ambiente não informado")
            
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

    @AutenticacaoService.accessToken
    def consultarVendasParceladas(self,companyNumber:int,startDate:date,endDate:date,nsu:int=None,ambiente:Literal['trn', 'prd']=None) -> dict:

        """
            Consulta a API do Itaú para buscar vendas parceladas
            
            Parametros:
                companyNumber: int
                startDate: date que vira string
                endDate: date que vira string
                nsu?: int
            
            Response: 
                content.installments[]:
                    merchantId, centralMerchantId   str     PV do estabelecimento / central
                    cardNumber                      str     mascarado: 999999******9999
                    authorizationCode               str     código de autorização
                    brand / brandCode               str/int VISA, MASTERCARD / 1, 2...
                    saleAmount                      float   valor total da venda
                    installmentNumber               int     nº desta parcela
                    installmentQuantity             int     total de parcelas
                    expirationDate                  str     AAAA-MM-DD (vencimento da parcela)
                    status                          str     visto: "SCHEDULLED" (agendada)
                    mdrFee / mdrAmount              float   taxa MDR (%) / valor da taxa
                    feeTotal                        float   total de taxas
                    flex / flexFee / flexAmount     bool/float  antecipação (Flex)
                    amountInfo:
                        amount, netAmount                       bruto / líquido da parcela
                        discountAmount                          desconto (taxa)
                        originalAmount, originalNetAmount,
                        originalDiscountAmount, valueChange     valores originais e se houve ajuste
        """

        data:dict={}
        url:str=''
        header:dict={}
        res:requests.Response=None

        url=self.validarAmbienteVendas(ambiente=ambiente)
        if nsu:
            url+=f"/v2/payments/installments/{companyNumber}?saleDate={startDate.strftime('%Y-%m-%d')}&nsu={nsu}"
        else:
            url+=f"/v1/sales/installments?parentCompanyNumber={companyNumber}&subsidiaries={companyNumber}&startDate={startDate.strftime('%Y-%m-%d')}&endDate={endDate.strftime('%Y-%m-%d')}"

        header={
            "Authorization": f"Bearer {self.token}",
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
                    self.dados_vendas_parceladas = data.get("content",{}).get("installments",[])
                case 204:
                    data = {
                        "message": f"A consulta não retornou dados. NSU: {nsu}. Data: {startDate.strftime('%d/%m/%Y')}"
                        }
                case _:
                    raise ConnectionError(f"Erro {res.status_code} na consulta de vendas parceladas: {res.text}")
        return data
    
    @AutenticacaoService.accessToken
    def consultarPagamentosOc(self,companyNumber:int,startDate:date,endDate:date,ambiente:Literal['trn', 'prd']=None) -> dict:
        
        """
            Consulta pagamentos na API do Itaú por ordem de crédito
            
            Request:
                companyNumber: int
                startDate: date que vira string
                endDate: date que vira string
                nsu?: int
            
            Response: 
                content.paymentsCreditOrders[]:
                    companyNumber        str     PV
                    saleSummaryNumber    int     RV  ← chave do cruzamento com o Sankhya
                    paymentId            str     20 dígitos numéricos
                    creditOrderNumber    int     nº da ordem de crédito (≠ paymentId)
                    paymentDate          str     AAAA-MM-DD
                    type / typeCode      str     visto: "CREDIT" / "CRE"
                    brandCode            int
                    amount               float   bruto
                    discountAmount       float   descontos/taxas
                    netAmount            float   líquido creditado
                cursor.hasNextKey      bool    paginação
        """
        
        data:dict={}
        url:str=''
        header:dict={}
        res:requests.Response=None    

        url=self.validarAmbienteVendas(ambiente=ambiente)
        url+=f'/v1/payments/credit-orders?parentCompanyNumber={companyNumber}&subsidiaries={companyNumber}&startDate={startDate.strftime('%Y-%m-%d')}&endDate={endDate.strftime('%Y-%m-%d')}'

        header={
            "Authorization": f"Bearer {self.token}",
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

    @AutenticacaoService.accessToken
    def consultarPagamentosId(self,companyNumber:int,paymentId:str,ambiente:Literal['trn', 'prd']=None) -> dict:

        """
            Consulta pagamentos por ID na API Rede
            
            Request:
                companyNumber: int
                paymentId: int
                        
            Response: 
                merchantId, centralMerchantId   str     PV do estabelecimento / central
                cardNumber                      str     mascarado: 999999******9999
                authorizationCode               str     código de autorização
                brand / brandCode               str/int VISA, MASTERCARD / 1, 2...
                saleAmount                      float   valor total da venda
                installmentNumber               int     nº desta parcela
                installmentQuantity             int     total de parcelas
                expirationDate                  str     AAAA-MM-DD (vencimento da parcela)
                status                          str     visto: "SCHEDULLED" (agendada)
                mdrFee / mdrAmount              float   taxa MDR (%) / valor da taxa
                feeTotal                        float   total de taxas
                flex / flexFee / flexAmount     bool/float  antecipação (Flex)
                amountInfo:
                    amount, netAmount                       bruto / líquido da parcela
                    discountAmount                          desconto (taxa)
                    originalAmount, originalNetAmount,
                    originalDiscountAmount, valueChange     valores originais e se houve ajuste
        """

        data:dict={}
        url:str=''
        header:dict={}
        res:requests.Response=None

        url=self.validarAmbienteVendas(ambiente=ambiente)
        url+=f'/v1/payments/{companyNumber}/{paymentId}'

        header={
            "Authorization": f"Bearer {self.token}",
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
    
    def formatarPayloadConsultaVendasParceladas(self,dadosVendas:dict=None) -> list[dict]:
        """
            Simplifica as parcelas retornadas por consultarVendasParceladas.

            Parametros:
                dadosVendas?: retorno da API. Se não informado, usa as parcelas da
                              última consulta (self.dados_vendas_parceladas)

            Retorno:
                list[dict] com amount, brand, expirationDate (DD/MM/AAAA),
                installmentNumber, mdrAmount, mdrFee, netAmount
                [] em caso de erro
        """
        
        vendas:list[dict] = dadosVendas.get("content",{}).get("installments",[]) if dadosVendas else self.dados_vendas_parceladas
        try:            
            return [
                {
                    "amount": item['amountInfo'].get("amount"),
                    "brand": item.get("brand"),
                    "expirationDate": datetime.strptime(item.get("expirationDate"), '%Y-%m-%d').strftime('%d/%m/%Y'),
                    "installmentNumber": item.get("installmentNumber"),
                    "mdrAmount": item.get("mdrAmount"),
                    "mdrFee": item.get("mdrFee"),
                    "netAmount": item['amountInfo'].get("netAmount")
                }
                for i, item in enumerate(vendas)
            ]
        except Exception as e:
            logger.error(f"Erro ao formatar payload de vendas parceladas: {e}")
            return []    
