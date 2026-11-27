# CLAUDE.md

Guia para agentes (Claude Code e similares) trabalhando neste repositório.

## O que é o projeto

API FastAPI que integra a **API da Rede (Itaú)** — autenticação OAuth2, links de pagamento e extrato de vendas/pagamentos (`merchant-statement`) — com o **ERP Sankhya**. A rotina principal busca os pagamentos da Rede e grava a data e o ID de pagamento na tabela customizada `AD_REDEPAGAMENTO` do Sankhya.

Toda a base (código, logs, mensagens de erro, docs) é em **português**. Mantenha o mesmo idioma.

## Como rodar

```powershell
python .              # __main__.py → bootstrap.py (cria venv, pip install -e ., cria SQLite) → python -m rede.main
```

- Ambiente já pronto: `venv\Scripts\python -m rede.main` (ou o script `start`, definido no `pyproject.toml`).
- O uvicorn sobe `rede.app:app` em `HOST`/`PORT` lidos do `.env`.
- Swagger em `/docs`. Não há testes automatizados, lint nem CI.
- Python >= 3.10 (o código usa `match`/`case`).

## Arquitetura

```
src/rede/
├── app.py               # FastAPI, CORS, lifespan que liga/desliga o scheduler
├── main.py              # entrypoint do uvicorn
├── controllers/api.py   # rotas + modelos Pydantic (validação de companyNumber, datas e NSU)
├── services/
│   ├── rede.py          # AutenticacaoService, LinkPagamentoService, VendasService (API Rede)
│   ├── sankhya.py       # AutenticacaoService, FinanceiroService, PagamentoService (API Sankhya)
│   ├── rotina.py        # RotinaService: orquestra Rede → Sankhya
│   ├── scheduler.py     # APScheduler: job diário às 01:00 (America/Sao_Paulo), roda o dia anterior
│   └── token.py         # TokenService: CRUD da tabela tokens
├── database/            # SQLAlchemy + SQLite (src/rede/database/db.sqlite), model Token
└── utils/log.py         # set_logger(__name__) → ./logs/AAAAMM.log
```

### Rotas (`controllers/api.py`)

| Rota | Auth | Serviço |
|---|---|---|
| `GET /info` | — | health check |
| `POST /auth/login` | — | `rede.AutenticacaoService.logar` |
| `POST /vendas/consulta-parcelas` | Bearer | `VendasService.consultarVendasParceladas` |
| `POST /vendas/consulta-pgto-oc` | Bearer | `VendasService.consultarPagamentosOc` |
| `POST /vendas/consulta-pgto-id` | Bearer | `VendasService.consultarPagamentosId` |
| `POST /rotina/registra-pagamento` | — | `RotinaService.registrarDadosPagamento` |
| `POST /rotina/atualiza-pagamento` | — | `RotinaService.atualizarDadosPagamento` (o mesmo que o scheduler executa) |

`validar_token` só confere se existe um Bearer não vazio; o valor do token não é validado.

### Autenticação e tokens

- `rede.py` e `sankhya.py` têm cada um sua própria `AutenticacaoService`, com o mesmo padrão: `validarToken` → `atualizarToken`/`logar` → `salvarToken`.
- Os métodos que chamam a API externa usam o decorator `@AutenticacaoService.accessToken`, que coloca o token em `self.token` durante a chamada e limpa depois.
- Os tokens ficam na tabela SQLite `tokens` (uma linha por `sistema`: `'rede'` ou `'sankhya'`), com expiração antecipada em 60s.
- Ambiente `trn` (sandbox) ou `prd`; pacote `pgto` (payment-link) ou `vendas` (merchant-statement). A URL vem de `URL_{AUTH_}{S|P}{P|T}` no `.env` (ex.: `URL_SP` = vendas/produção).

### Sankhya

- Gateway: `https://api.sankhya.com.br/gateway/v1/mge/service.sbr` (URLs fixas no código), usando `CRUDServiceProvider.loadRecords` para ler e `DatasetSP.save` para gravar.
- Entidades: `Financeiro` (`FinanceiroService`, campos `AD_REDE_*`) e `AD_REDEPAGAMENTO` (`PagamentoService`, usado pela rotina).
- O payload do `DatasetSP.save` referencia os campos **pela posição** na lista `self.fields` (ex.: `"6"` = PAYMENTDATE, `"7"` = PAYMENTID). Se mudar a ordem de `fields`, os payloads quebram.
- Datas: a Rede usa `AAAA-MM-DD` e o Sankhya `DD/MM/AAAA`. O cruzamento entre os dois é feito por `saleSummaryNumber` ↔ `salesumnum` + data de vencimento.

## Configuração (`.env`)

Use o `example.env` como base. Variáveis principais: `HOST`, `PORT`, `API_TITLE/DESCRIPTION/VERSION` (o app não sobe sem elas), `LOGGER_FORMAT`, `COMPANY_NUMBER_LIST` (lista separada por vírgula, que é a whitelist de `companyNumber` e a lista de empresas do job), `BASIC_CLIENT_*` (`client_id:client_secret`) e `URL_*`.

⚠️ O código do Sankhya lê `URL_AUTH_SNK`, `XTOKEN` e `APP_ID`, que **não estão** no `example.env` (lá aparecem `X_TOKEN`/`CLIENT_ID`/`CLIENT_SECRET`). Além disso, `rede.AutenticacaoService` sempre prefere `BASIC_CLIENT_SP` ao `auth` recebido.

Nunca faça commit de `.env`, `*.json` (tokens), `*.sqlite` nem `logs/` (todos estão no `.gitignore`).

## Convenções de código

- Métodos e variáveis em **camelCase em português** (`consultarPagamentosOc`, `formatarPayloadPagamento`); classes terminam em `Service`.
- Imports absolutos começando por `src.rede...` (ex.: `from src.rede.services.rede import VendasService`). Por isso o processo precisa rodar a partir da raiz do repositório.
- Cada módulo começa com `logger = set_logger(__name__)` e `load_dotenv()`.
- Padrão dos métodos: variáveis tipadas inicializadas no topo, depois `try/except Exception` com `logger.error(...)`, `finally: pass` e retorno de `dict`/`bool`/`list`. Na rotina, o retorno segue o formato `{"sucesso": bool, "mensagem": str, ...}`.
- Os services retornam o JSON de erro da Rede (com chave `message`) em vez de lançar exceção. Quem chama verifica `'message' in resposta`.
- `database.py` monta `DB_PATH` com `"src\\rede\\database\\db.sqlite"` (separador do Windows). O ambiente-alvo é Windows.

## Documentação

- [readme.md](readme.md): visão geral.
- [DOCUMENTACAO_TECNICA.md](DOCUMENTACAO_TECNICA.md): dicionário do banco, modelos Pydantic e descrição de cada classe. Atualize esse arquivo quando mudar models, rotas ou services.
