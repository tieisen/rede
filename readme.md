# Rede API Client — Python

**Client Python REST para integração com a API de Vendas e Pagamentos da Rede (Itaú)**

Este projeto provê uma base para acessar os serviços de **autenticação**, **criação/consulta de links de pagamento** e **consulta de relatórios de vendas e pagamentos** expostos pela API da Rede (Itaú). Ele encapsula chamadas HTTP, tratamento de respostas e integração com infraestrutura de logging, oferecendo um ponto centralizado para uso em aplicações backend Python.

## Visão Geral

- **Autenticação** — Geração e renovação de tokens de acesso conforme o modelo suportado pela Rede.
- **Links de Pagamento** — Criação, consulta e gestão de links para pagamento online.
- **Relatórios de Vendas e Pagamentos** — Consulta de transações, vendas e pagamentos.
- **Infraestrutura de Logging** — Registro de chamadas e respostas para auditoria e diagnóstico.
- **Estrutura Modular** — Organização por responsabilidade, facilitando manutenção e evolução.

## Estrutura do Projeto

```text
rede/
├── pyproject.toml
├── README.md
├── .gitignore
├── .env
├── bootstrap.py
├── __main__.py
├── src/
│   └── rede/
│       ├── app.py
│       ├── main.py
│       ├── controllers/
│       │   └── api.py
│       ├── database/
│       │   ├── database.py
│       │   └── models.py
│       ├── services/
│       │   ├── rede.py
│       │   ├── rotina.py
│       │   ├── sankhya.py
│       │   ├── scheduler.py
│       │   └── token.py
│       ├── utils/
│       │   └── log.py
│       ├── app.py
│       └── main.py
└── logs/
```

## Instalação

```bash
# Clone o repositório
git clone https://github.com/tieisen/rede.git

# Execute o setup do projeto
python .
```

## Configuração

Antes de utilizar a API, é necessário possuir credenciais válidas (Company Number, Client ID e Client Secret) junto à **Rede (Itaú)**, tanto para ambiente de Teste quanto para Produção.

As credenciais podem ser configuradas via arquivo `.env` utilizando o arquivo de exemplo:

```env
BASIC_CLIENT_TEST = "seu_client_id_teste:seu_client_secret_teste"
```

## Funcionalidades Disponíveis

| Funcionalidade                     | Descrição |
|-----------------------------------|-----------|
| Autenticação                      | Obtenção de token de acesso à API da Rede |
| Criação de Link de Pagamento      | Geração de links para cobrança online |
| Consulta de Link de Pagamento     | Consulta de status e detalhes do link |
| Relatórios de Vendas e Pagamentos | Consulta de transações e conciliação |
| Logging                           | Registro estruturado de eventos e erros |


