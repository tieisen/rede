# Rede

## Sumario

- [Documentacao dos objetos do banco de dados](#documentacao-dos-objetos-do-banco-de-dados)
- [Documentacao dos modelos Pydantic](#documentacao-dos-modelos-pydantic)
- [Documentacao das classes da aplicacao](#documentacao-das-classes-da-aplicacao)
- [Endpoints da API](#endpoints-da-api)
- [Fluxos principais](#fluxos-principais)
- [Configuracao e variaveis de ambiente](#configuracao-e-variaveis-de-ambiente)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Pontos de atencao tecnica](#pontos-de-atencao-tecnica)

## Documentacao dos objetos do banco de dados

### Visao geral

O projeto utiliza um banco SQLite local para persistir tokens de autenticacao das integracoes com a Rede e com o Sankhya.

A configuracao do banco esta em `src/rede/database/database.py`. O arquivo fisico do banco e resolvido a partir da raiz do projeto e criado em:

```text
src/rede/database/db.sqlite
```

A criacao do arquivo e das tabelas e executada por `bootstrap.py`, por meio das funcoes `verificarCriarBanco()` e `criarTabelas()`.

### Tabelas

#### tokens

##### Visao geral

Tabela responsavel por armazenar o token vigente de cada sistema integrado. Cada sistema possui no maximo um registro, controlado por restricao de unicidade no campo `sistema`.

##### Dicionario de dados

| Nome do campo | Descricao | Tipo | Obrigatorio | Valores/regras |
| --- | --- | --- | --- | --- |
| `id` | Identificador primario do token | Integer | Sim | Chave primaria |
| `sistema` | Sistema dono do token | String(20) | Sim | Unico; deve estar em `sankhya`, `rede` |
| `access_token` | Token de acesso persistido | String | Sim | Texto retornado pela API externa |
| `expires_at` | Data/hora de expiracao considerada pela aplicacao | DateTime | Nao | Gravada com margem de 60 segundos antes da expiracao real |
| `updated_at` | Data/hora da criacao ou ultima atualizacao | DateTime(timezone=True) | Nao | Default/onupdate em UTC-3 |

##### Restricoes

| Restricao | Campo(s) | Descricao |
| --- | --- | --- |
| Primary key | `id` | Identifica unicamente cada linha |
| Unique | `sistema` | Garante um token por sistema |
| Check `ck_tokens_sistema` | `sistema` | Permite apenas `sankhya` ou `rede` |

##### Cardinalidade

Nao ha relacionamentos ORM definidos com outras tabelas. A tabela funciona como armazenamento local de credenciais temporarias para servicos externos.

## Documentacao dos modelos Pydantic

Os modelos Pydantic estao definidos em `src/rede/controllers/api.py` e representam os contratos de entrada dos endpoints.

### AutenticacaoModel

Modelo usado pelo endpoint `POST /auth/login` para solicitar autenticacao direta na Rede.

| Campo | Tipo | Valores/regras | Descricao |
| --- | --- | --- | --- |
| `ambiente` | Literal | `trn`, `prd` | Ambiente de teste ou producao |
| `pacote` | Literal | `pgto`, `vendas` | Familia de API da Rede |
| `auth` | str | Obrigatorio | Credencial base para geracao do Basic Auth |

### LinkPagamentoModel

Modelo para operacoes de link de pagamento. A classe existe no controller, mas nao ha endpoint registrado atualmente usando este modelo.

| Campo | Tipo | Valores/regras | Descricao |
| --- | --- | --- | --- |
| `ambiente` | Literal | `trn`, `prd` | Ambiente Rede |
| `paymentLinkId` | str | Obrigatorio | Identificador do link de pagamento |
| `companyNumber` | str | Deve existir em `COMPANY_NUMBER_LIST` | Numero da empresa/estabelecimento |
| `body` | dict | Obrigatorio | Payload enviado para a API de link de pagamento |

Validacao adicional:

- `validar_companynumber`: rejeita company numbers que nao estejam configurados em `COMPANY_NUMBER_LIST`.

### VendasModel

Modelo usado nas consultas de vendas parceladas e pagamentos por ordem de credito.

| Campo | Tipo | Valores/regras | Descricao |
| --- | --- | --- | --- |
| `ambiente` | Literal | `trn`, `prd` | Ambiente Rede |
| `companyNumber` | int | Deve existir em `COMPANY_NUMBER_LIST` | Numero da empresa/estabelecimento |
| `nsu` | int ou None | Se informado, minimo de 8 digitos | NSU para consulta especifica |
| `startDate` | date | Deve ser menor ou igual a `endDate` | Data inicial |
| `endDate` | date | Deve ser maior ou igual a `startDate` | Data final |

Validacoes adicionais:

- `validar_periodo`: impede periodo com data inicial maior que data final.
- `validar_nsu`: exige NSU com pelo menos 8 digitos quando informado.
- `validar_companynumber`: valida a empresa contra `COMPANY_NUMBER_LIST`.

### RotinaVendaModel

Modelo usado pelo endpoint `POST /rotina/registra-pagamento`.

| Campo | Tipo | Valores/regras | Descricao |
| --- | --- | --- | --- |
| `companyNumber` | int | Deve existir em `COMPANY_NUMBER_LIST` | Numero da empresa/estabelecimento |
| `startDate` | date | Deve ser menor ou igual a `endDate` | Data da venda ou inicio do periodo |
| `endDate` | date | Deve ser maior ou igual a `startDate` | Final do periodo |
| `nsu` | int ou None | Se informado, minimo de 8 digitos | NSU da venda |

Validacoes adicionais:

- `validar_periodo`
- `validar_nsu`
- `validar_companynumber`

### RotinaPagamentoModel

Modelo usado pelo endpoint `POST /rotina/atualiza-pagamento`.

| Campo | Tipo | Valores/regras | Descricao |
| --- | --- | --- | --- |
| `companyNumber` | int | Deve existir em `COMPANY_NUMBER_LIST` | Numero da empresa/estabelecimento |
| `startDate` | date | Deve ser menor ou igual a `endDate` | Data inicial do periodo de pagamentos |
| `endDate` | date | Deve ser maior ou igual a `startDate` | Data final do periodo de pagamentos |

Validacoes adicionais:

- `validar_periodo`
- `validar_companynumber`

### VendasPgtoId

Modelo usado pelo endpoint `POST /vendas/consulta-pgto-id`.

| Campo | Tipo | Valores/regras | Descricao |
| --- | --- | --- | --- |
| `ambiente` | Literal | `trn`, `prd` | Ambiente Rede |
| `companyNumber` | int | Nao ha validator especifico neste modelo | Numero da empresa/estabelecimento |
| `paymentId` | str | Obrigatorio | Identificador do pagamento na Rede |

## Documentacao das classes da aplicacao

### Resumo

Este documento registra a estrutura tecnica do projeto `rede`, um client/API Python para integracao com a API de Vendas e Pagamentos da Rede (Itau) e com servicos Sankhya. A aplicacao expoe endpoints FastAPI para autenticacao, consultas de vendas/pagamentos e execucao de rotinas de conciliacao/atualizacao.

### Dados do projeto

| Item | Valor |
| --- | --- |
| Nome do projeto | `rede` |
| Versao declarada | `0.1.0` no `pyproject.toml`; API exposta como `1.0` no `example.env` |
| Linguagem principal | Python |
| Versao minima | Python >= 3.10 |
| Framework API | FastAPI |
| Servidor ASGI | Uvicorn |
| Banco local | SQLite |
| ORM | SQLAlchemy |
| Agendador | APScheduler |
| Repositorio remoto informado | `https://github.com/tieisen/rede` |

### `src/rede/app.py`

#### Visao geral

Modulo de composicao da aplicacao FastAPI. Carrega metadados via variaveis de ambiente, configura CORS, registra o router principal e gerencia o ciclo de vida do scheduler.

#### Principais responsabilidades

- Carregar `API_TITLE`, `API_DESCRIPTION` e `API_VERSION`.
- Instanciar `FastAPI`.
- Configurar `CORSMiddleware`.
- Incluir o router de `src/rede/controllers/api.py`.
- Iniciar e encerrar `SchedulerService` no lifespan da aplicacao.
- Expor endpoint raiz de status fora do schema.
- Registrar log de boot da API.

#### Componentes

| Componente | Tipo | Descricao |
| --- | --- | --- |
| `app` | FastAPI | Instancia principal da API |
| `lifespan` | async context manager | Inicializa e encerra o scheduler |
| `read_root()` | funcao | Retorna mensagem simples com titulo e versao |

### `src/rede/main.py`

#### Visao geral

Ponto de entrada runtime para subir a API com Uvicorn.

#### Principais responsabilidades

- Carregar `HOST` e `PORT`.
- Validar existencia e tipo numerico da porta.
- Executar `uvicorn.run(app="rede.app:app", host=host, port=port)`.

### `src/rede/controllers/api.py`

#### Visao geral

Modulo controller da API. Define modelos Pydantic, dependencia de autenticacao Bearer e endpoints expostos.

#### Principais responsabilidades

- Declarar os contratos de entrada da API.
- Validar ambientes, periodos, NSU e company numbers.
- Exigir Bearer token nos endpoints de consulta da Rede.
- Delegar regras de negocio para `AutenticacaoService`, `VendasService` e `RotinaService`.
- Converter excecoes em `HTTPException`.

#### Dependencias

| Dependencia | Tipo | Uso |
| --- | --- | --- |
| `fastapi.APIRouter` | Framework | Registro de rotas |
| `HTTPBearer` | Framework | Validacao basica do header Authorization |
| `pydantic.BaseModel` | Validacao | Modelos de entrada |
| `model_validator` | Validacao | Regras de negocio de payload |
| `AutenticacaoService` | Servico interno | Login Rede |
| `VendasService` | Servico interno | Consultas Rede |
| `RotinaService` | Servico interno | Orquestracao das rotinas |

### `src/rede/database/database.py`

#### Visao geral

Modulo de infraestrutura do banco SQLite local.

#### Principais responsabilidades

- Resolver o caminho do banco SQLite.
- Definir `DATABASE_URL`.
- Declarar a base ORM `Base`.
- Criar engine SQLAlchemy.
- Criar fabrica de sessoes `SessionLocal`.
- Criar arquivo de banco quando inexistente.
- Criar tabelas registradas nos models.
- Fornecer `get_session()` como context manager.

#### Componentes

| Componente | Tipo | Descricao |
| --- | --- | --- |
| `Base` | DeclarativeBase | Classe base dos modelos ORM |
| `engine` | SQLAlchemy Engine | Conexao SQLite |
| `SessionLocal` | sessionmaker | Fabrica de sessoes |
| `verificarCriarBanco()` | funcao | Cria o arquivo `db.sqlite` se necessario |
| `criarTabelas()` | funcao | Executa `Base.metadata.create_all` |
| `get_session()` | context manager | Abre e fecha sessoes de banco |

### `src/rede/database/models.py`

#### Visao geral

Define as entidades ORM persistidas pela aplicacao.

#### Classes

##### Token

Representa a tabela `tokens`.

Principais atributos:

- `id`
- `sistema`
- `access_token`
- `expires_at`
- `updated_at`

Regras:

- `sistema` e unico.
- `sistema` aceita apenas `sankhya` ou `rede`.
- `updated_at` usa horario com offset UTC-3.

### `src/rede/services/token.py`

#### Visao geral

Camada de servico/repository para persistencia e consulta de tokens no SQLite.

#### Classe `TokenService`

| Metodo | Descricao |
| --- | --- |
| `__init__(db)` | Recebe uma sessao SQLAlchemy |
| `salvarToken(sistema, accessToken, expiresAt)` | Atualiza o token existente do sistema ou cria novo registro |
| `obterToken(sistema)` | Retorna o token persistido para o sistema informado |

### `src/rede/services/rede.py`

#### Visao geral

Modulo responsavel pela integracao com APIs da Rede. Contem autenticacao OAuth client credentials, endpoints de link de pagamento e consultas de vendas/pagamentos.

#### Classe `AutenticacaoService`

Responsavel pela autenticacao na Rede e pelo cache do token no banco local.

| Metodo | Descricao |
| --- | --- |
| `__init__(ambiente='prd', pacote='vendas', auth='')` | Inicializa contexto de autenticacao Rede |
| `converterBase64(texto)` | Converte credencial para Base64 |
| `validarAmbienteAuth()` | Resolve URL e header Basic conforme `ambiente` e `pacote` |
| `calcularExpiracao(dados)` | Calcula `request_time` e `expire_time` a partir de `expires_in` |
| `logar()` | Executa `POST` OAuth com `grant_type=client_credentials` |
| `salvarToken(dadosToken)` | Persiste token Rede no SQLite |
| `carregarToken()` | Busca token Rede no SQLite |
| `validarToken()` | Verifica token local e expiracao |
| `atualizarToken()` | Gera novo token e persiste |
| `autenticar()` | Reutiliza token valido ou renova |
| `accessToken(func)` | Decorator que injeta Bearer token em servicos Rede |

#### Classe `LinkPagamentoService`

Especializacao para API de link de pagamento.

| Metodo | Descricao |
| --- | --- |
| `validarAmbienteLink(ambiente)` | Retorna URL base de link de pagamento conforme ambiente |
| `consultarDetalhesLink(paymentLinkId, companyNumber, ambiente)` | Consulta detalhes de um link |
| `criarLink(companyNumber, body, ambiente)` | Cria link de pagamento |

Observacao: a classe esta implementada, mas nao ha endpoints no router atual expondo essas operacoes.

#### Classe `VendasService`

Especializacao para API de vendas e pagamentos da Rede.

| Metodo | Descricao |
| --- | --- |
| `validarAmbienteVendas(ambiente)` | Retorna URL base da API de vendas conforme ambiente |
| `consultarVendasParceladas(companyNumber, startDate, endDate, nsu, ambiente)` | Consulta parcelas por periodo ou por NSU |
| `consultarPagamentosOc(companyNumber, startDate, endDate, ambiente)` | Consulta pagamentos por ordem de credito |
| `consultarPagamentosId(companyNumber, paymentId, ambiente)` | Consulta pagamento por ID |
| `formatarPayloadConsultaVendasParceladas(dadosVendas)` | Converte parcelas da Rede para lista simplificada |

### `src/rede/services/sankhya.py`

#### Visao geral

Modulo responsavel pela autenticacao e integracao com servicos Sankhya. Trabalha com os servicos gateway `CRUDServiceProvider.loadRecords`, `CRUDServiceProvider.loadView`, `DbExplorerSP.executeQuery` e `DatasetSP.save`.

#### Classe `AutenticacaoService`

Responsavel pela autenticacao Sankhya e cache do token local.

| Metodo | Descricao |
| --- | --- |
| `__init__()` | Carrega URL, token de integracao e app id |
| `salvarToken(dadosToken)` | Persiste token Sankhya no SQLite |
| `carregarToken()` | Recupera token Sankhya local |
| `logar()` | Chama endpoint Sankhya de autenticacao |
| `validarToken()` | Valida token local e expiracao |
| `atualizarToken()` | Renova token Sankhya |
| `autenticar()` | Reutiliza ou renova token |
| `accessToken(func)` | Decorator que injeta Bearer token em metodos Sankhya |

#### Classe `FinanceiroService`

Servico para consultar e atualizar a entidade `Financeiro` do Sankhya.

| Metodo | Descricao |
| --- | --- |
| `formatarRetorno(res)` | Normaliza diferentes formatos de retorno Sankhya |
| `buscar(saleSummaryNumber, lista)` | Busca registros financeiros por numero de resumo de venda |
| `atualizar(payload)` | Atualiza campos adicionais na entidade `Financeiro` |
| `formatarPayloadVenda(companyNumber, dadosRede, dadosFinanceiro)` | Monta payload de atualizacao de venda |
| `formatarPayloadPagamento(dadosPagamento, dadosFinanceiro)` | Monta payload de atualizacao de dados de pagamento |

Campos usados em `FinanceiroService`:

- `AD_REDE_AMOUNT`
- `AD_REDE_EXPIRATIONDATE`
- `AD_REDE_INSTALLMENTNUM`
- `AD_REDE_MDRAMOUNT`
- `AD_REDE_MDRFEE`
- `AD_REDE_NETAMOUNT`
- `AD_REDE_PAYMENTDATE`
- `AD_REDE_PAYMENTID`
- `AD_REDE_PROCESSADO`
- `AD_REDE_TID`
- `AD_COMPANYNUMBER`

#### Classe `PagamentoService`

Servico para consultar e atualizar a entidade customizada `AD_REDEPAGAMENTO`.

| Metodo | Descricao |
| --- | --- |
| `formatarRetorno(res)` | Normaliza retornos Sankhya |
| `formatarPayloadRegistro(dadosRede, dadosSankhya)` | Monta payload inicial de registro de parcelas |
| `formatarPayloadPagamento(dadosPagamento, dadosFinanceiro)` | Monta payload de atualizacao de pagamento |
| `buscar(saleSummaryNumber, nsu, lista_saleSummaryNumber, lista_nsu)` | Busca registros de pagamento por criterios individuais ou listas |
| `enviar(payload)` | Envia registros para `AD_REDEPAGAMENTO` |
| `atualizar(payload)` | Atualiza registros em `AD_REDEPAGAMENTO` |

Campos usados em `PagamentoService`:

- `AMOUNT`
- `BANDEIRA`
- `EXPIRATIONDATE`
- `MDRAMOUNT`
- `MDRFEE`
- `NETAMOUNT`
- `PAYMENTDATE`
- `PAYMENTID`

### `src/rede/services/rotina.py`

#### Visao geral

Modulo de orquestracao entre Rede e Sankhya.

#### Classe `RotinaService`

| Metodo | Descricao |
| --- | --- |
| `__init__()` | Instancia `PagamentoService` e `VendasService` |
| `registrarDadosPagamento(companyNumber, dataVendas, nsu)` | Consulta parcelas na Rede e formata retorno para registro |
| `atualizarDadosPagamento(companyNumber, startDate, endDate)` | Consulta pagamentos na Rede, busca registros Sankhya e atualiza pagamento |

### `src/rede/services/scheduler.py`

#### Visao geral

Modulo responsavel por tarefas agendadas com APScheduler.

#### Classe `SchedulerService`

| Metodo | Descricao |
| --- | --- |
| `__init__()` | Inicializa atributo `scheduler` |
| `startScheduler()` | Configura tarefas e inicia o scheduler |
| `stopScheduler()` | Encerra o scheduler |
| `jobAtualizarDadosPagamento()` | Executa rotina diaria de atualizacao de pagamentos para cada company number |
| `inicializarTarefas()` | Configura executor, defaults e job cron |

Configuracao do job:

- Timezone: `America/Sao_Paulo`
- Frequencia: diariamente as 01:00
- Job ID: `job_atualizar_dados_pagamento`
- Rotina executada: `RotinaService.atualizarDadosPagamento`
- Periodo consultado: dia anterior

### `src/rede/utils/log.py`

#### Visao geral

Modulo utilitario para configuracao de logging.

#### Funcoes

| Funcao | Descricao |
| --- | --- |
| `buscar_path()` | Cria/resolve arquivo mensal em `./logs/YYYYMM.log` |
| `set_logger(name)` | Configura logging basico e retorna logger nomeado |

Regras:

- O formato do log vem de `LOGGER_FORMAT`.
- Logs sao gravados no diretorio `logs`.
- Bibliotecas `apscheduler` e `uvicorn.access` sao silenciadas para nivel `WARNING`.

### `bootstrap.py`

#### Visao geral

Script de preparacao do projeto.

#### Principais responsabilidades

- Criar `venv` se nao existir.
- Atualizar `pip`.
- Instalar o projeto em modo editavel com `pip install -e .`.
- Inicializar banco SQLite e tabelas.

### `__main__.py`

#### Visao geral

Permite executar o projeto com `python .`.

#### Principais responsabilidades

- Executar `bootstrap.py`.
- Executar `python -m rede.main` usando o Python do ambiente virtual.

## Endpoints da API

### Rotas publicas

| Metodo | Rota | Handler | Descricao |
| --- | --- | --- | --- |
| GET | `/` | `read_root` | Retorna mensagem de boot com titulo e versao |
| GET | `/info` | `info` | Retorna status, health e version |
| POST | `/auth/login` | `logar` | Gera token Rede para ambiente/pacote informado |

### Rotas com dependencia Bearer

Estas rotas usam `validar_token`, que verifica apenas a presenca de `Authorization: Bearer <token>` e rejeita scheme invalido ou token vazio.

| Metodo | Rota | Body | Handler | Descricao |
| --- | --- | --- | --- | --- |
| POST | `/vendas/consulta-parcelas` | `VendasModel` | `consultaParcelas` | Consulta vendas parceladas na Rede |
| POST | `/vendas/consulta-pgto-oc` | `VendasModel` | `consultaPagamentosPorOc` | Consulta pagamentos por ordem de credito |
| POST | `/vendas/consulta-pgto-id` | `VendasPgtoId` | `consultaPagamentosPorId` | Consulta pagamento por ID |

### Rotas de rotina

| Metodo | Rota | Body | Handler | Descricao |
| --- | --- | --- | --- | --- |
| POST | `/rotina/registra-pagamento` | `RotinaVendaModel` | `registraPagamento` | Consulta parcelas Rede e retorna dados formatados |
| POST | `/rotina/atualiza-pagamento` | `RotinaPagamentoModel` | `atualizaPagamento` | Atualiza dados de pagamento no Sankhya com base na Rede |

## Fluxos principais

### Autenticacao Rede

1. Controller recebe `AutenticacaoModel`.
2. `src.rede.services.rede.AutenticacaoService` valida ambiente e pacote.
3. Credencial e convertida para Base64.
4. A API Rede recebe `POST` com `grant_type=client_credentials`.
5. A resposta recebe `request_time` e `expire_time`.
6. Quando usado pelo decorator, o token e salvo/recuperado da tabela `tokens`.

### Consulta de vendas parceladas

1. Endpoint recebe `VendasModel`.
2. O Bearer token da chamada HTTP e validado quanto a presenca.
3. `VendasService.consultarVendasParceladas` autentica na Rede via decorator.
4. A URL e montada por NSU ou por periodo.
5. Respostas `200` retornam JSON; `204` retornam mensagem de ausencia de dados.

### Consulta de pagamentos por ordem de credito

1. Endpoint recebe `VendasModel`.
2. `VendasService.consultarPagamentosOc` consulta `/v1/payments/credit-orders`.
3. Retorno com corpo e convertido em JSON.
4. Retorno OK sem corpo gera mensagem de ausencia de dados.

### Atualizacao de dados de pagamento no Sankhya

1. `RotinaService.atualizarDadosPagamento` consulta pagamentos na Rede.
2. Extrai `saleSummaryNumber` dos pagamentos encontrados.
3. `PagamentoService.buscar` consulta `AD_REDEPAGAMENTO` no Sankhya.
4. `PagamentoService.formatarPayloadPagamento` cruza pagamento Rede com registro Sankhya.
5. `PagamentoService.atualizar` envia payload para `DatasetSP.save`.
6. O retorno indica sucesso ou mensagem de erro.

### Scheduler diario

1. `app.py` inicia `SchedulerService` no startup.
2. O job roda todos os dias as 01:00.
3. O job le `COMPANY_NUMBER_LIST`.
4. Para cada empresa, executa `RotinaService.atualizarDadosPagamento` para o dia anterior.
5. O resultado e registrado em log.

## Configuracao e variaveis de ambiente

As variaveis esperadas foram identificadas a partir do codigo e de `example.env`. O arquivo `.env` real nao foi acessado.

| Variavel | Uso | Origem no codigo |
| --- | --- | --- |
| `LOGGER_FORMAT` | Formato das mensagens de log | `utils/log.py` |
| `HOST` | Host do Uvicorn | `main.py` |
| `PORT` | Porta do Uvicorn | `main.py` |
| `API_TITLE` | Titulo da API | `app.py` |
| `API_DESCRIPTION` | Descricao da API | `app.py` |
| `API_VERSION` | Versao exibida pela API | `app.py` |
| `COMPANY_NUMBER_LIST` | Lista de empresas permitidas e usadas pelo scheduler | `controllers/api.py`, `scheduler.py` |
| `BASIC_CLIENT_SP` | Credencial padrao de vendas/producao Rede | `services/rede.py` |
| `PATH_TOKEN_REDE` | Caminho esperado para token Rede | `services/rede.py` |
| `URL_AUTH_SP` | OAuth Rede vendas/producao | `services/rede.py` |
| `URL_AUTH_ST` | OAuth Rede vendas/teste | `services/rede.py` |
| `URL_AUTH_PP` | OAuth Rede pagamento/producao | `services/rede.py` |
| `URL_AUTH_PT` | OAuth Rede pagamento/teste | `services/rede.py` |
| `URL_SP` | Base URL Rede vendas/producao | `services/rede.py` |
| `URL_ST` | Base URL Rede vendas/teste | `services/rede.py` |
| `URL_PP` | Base URL Rede link pagamento/producao | `services/rede.py` |
| `URL_PT` | Base URL Rede link pagamento/teste | `services/rede.py` |
| `URL_AUTH_SNK` | URL de autenticacao Sankhya | `services/sankhya.py` |
| `XTOKEN` | Header de autenticacao Sankhya | `services/sankhya.py` |
| `APP_ID` | Identificador da aplicacao Sankhya | `services/sankhya.py` |

## Estrutura do projeto

```text
rede/
|-- DOCUMENTACAO_TECNICA.md
|-- DOCUMENTAÇÃO TÉCNICA.docx
|-- __main__.py
|-- bootstrap.py
|-- example.env
|-- nb.ipynb
|-- pyproject.toml
|-- readme.md
|-- token_rede.json
|-- logs/
|-- src/
|   `-- rede/
|       |-- __init__.py
|       |-- app.py
|       |-- main.py
|       |-- controllers/
|       |   |-- __init__.py
|       |   `-- api.py
|       |-- database/
|       |   |-- __init__.py
|       |   |-- database.py
|       |   `-- models.py
|       |-- services/
|       |   |-- __init__.py
|       |   |-- rede.py
|       |   |-- rotina.py
|       |   |-- sankhya.py
|       |   |-- scheduler.py
|       |   `-- token.py
|       `-- utils/
|           |-- __init__.py
|           `-- log.py
|-- venv/
`-- __pycache__/
```

### Arquivos e diretorios principais

| Caminho | Descricao |
| --- | --- |
| `pyproject.toml` | Metadados do pacote, dependencias e entry point `start = rede.main:main` |
| `readme.md` | Visao geral do projeto e instrucoes basicas |
| `example.env` | Modelo de configuracao de ambiente |
| `DOCUMENTAÇÃO TÉCNICA.docx` | Documento usado como referencia estrutural para esta documentacao |
| `bootstrap.py` | Prepara ambiente virtual e banco |
| `__main__.py` | Ponto de entrada para `python .` |
| `nb.ipynb` | Notebook de apoio com exemplos de chamadas aos servicos |
| `logs/` | Diretorio de logs mensais |
| `src/rede/app.py` | Composicao FastAPI |
| `src/rede/main.py` | Execucao Uvicorn |
| `src/rede/controllers/api.py` | Modelos Pydantic, validacoes e rotas |
| `src/rede/database/` | Configuracao e modelos do banco local |
| `src/rede/services/` | Regras de negocio e integracoes externas |
| `src/rede/utils/log.py` | Logging |
| `venv/` | Ambiente virtual local |

## Pontos de atencao tecnica

- O arquivo `.env` real nao foi acessado para elaboracao desta documentacao.
- `token_rede.json` foi identificado na estrutura, mas nao e usado pelo fluxo atual de persistencia principal, que grava tokens no SQLite.
- `services/rede.py` ainda referencia `PATH_TOKEN_REDE`, mas o token e salvo/carregado via `TokenService` e `get_session()`.
- `example.env` define `X_TOKEN`, enquanto `services/sankhya.py` le `XTOKEN`.
- `services/sankhya.py` le `APP_ID`, mas essa variavel nao aparece no `example.env`.
- `LinkPagamentoModel` e `LinkPagamentoService` existem, porem nao ha endpoints de link de pagamento expostos no router atual.
- `VendasPgtoId` nao aplica a mesma validacao de `COMPANY_NUMBER_LIST` existente em outros modelos.
- A dependencia Bearer do controller valida presenca/formato basico, mas nao valida o token contra banco, provedor externo ou assinatura.
