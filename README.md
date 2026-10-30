# TechFix — Sistema de Ordens de Serviço

Sistema web para uma assistência técnica de informática registrar e acompanhar
ordens de serviço. São duas aplicações Python ligadas ao mesmo banco
PostgreSQL na nuvem (Supabase): uma tela de cadastro para o balcão, que também
funciona no celular, e um painel administrativo com CRUD completo e indicadores.

Projeto desenvolvido na disciplina *Aplicações em Data Science* da
especialização em Ciência de Dados e Business Intelligence da Unicamp.

**Tecnologias:** Python · Gradio · Streamlit · Supabase (PostgreSQL) · pandas · SQL

## O problema

A TechFix Informática, uma loja fictícia, recebia todos os dias clientes com
computadores, notebooks e periféricos com defeito, e anotava o atendimento em
papel. Com isso, informações se perdiam, era difícil entrar em contato com o
cliente e não havia controle sobre o andamento dos reparos.

A solução separa as duas rotinas da loja:

| Aplicação | Quem usa | O que faz |
|---|---|---|
| **Atendimento** (`app_gradio.py`) | Atendente, no balcão ou pelo celular | Cadastra o cliente, o equipamento e o defeito e gera o número da OS |
| **Painel administrativo** (`app_streamlit.py`) | Gerente / técnico | Consulta, filtra, edita, exclui e acompanha os indicadores |

## Telas

**Cadastro de OS (Gradio)**

![Cadastro de OS](docs/Cadastro.PNG)

**Painel administrativo: consulta (Streamlit)**

![Consulta de ordens](docs/Consulta.PNG)

**Painel administrativo: indicadores (Streamlit)**

![Indicadores](docs/Indicadores.PNG)

## Funcionalidades

**Atendimento (Gradio)**
- Formulário responsivo, que pode ser usado pelo celular do atendente.
- Valida os dados antes de enviar ao banco: campos obrigatórios, formato de e-mail e celular só com números.
- Reaproveita o cliente quando o e-mail já existe. Assim, o mesmo cliente pode abrir várias OS sem gerar cadastro duplicado.
- Toda OS nova começa com status `Aberto`, e a tela mostra o número gerado.

**Painel administrativo (Streamlit)**
- **Consultar:** tabela de OS com os dados do cliente, filtros por nome, e-mail e status e exportação dos dados filtrados em CSV.
- **Cadastrar:** abre uma OS para um cliente existente ou novo.
- **Editar/Excluir:** muda o status e os dados da OS, edita os dados do cliente e exclui registros. Toda exclusão pede confirmação.
- **Indicadores:** total de OS por status, gráfico de barras por status e evolução das OS abertas por dia.

## Arquitetura

```
[Celular / Navegador]                [Navegador do Gerente]
         |                                     |
 App Gradio (cadastro)            App Streamlit (gerenciamento)
         |        supabase-py (API REST)       |
         +-------------> SUPABASE <------------+
                    (PostgreSQL na nuvem)
```

As duas aplicações acessam o Supabase pela biblioteca `supabase-py`. O
Supabase é um PostgreSQL gerenciado que expõe as tabelas por uma API REST.

## Modelagem do banco

Todo o banco é criado pelo script [`sql/schema.sql`](sql/schema.sql), que pode
ser executado mais de uma vez sem erro. Os dados ficam em duas tabelas com
relação 1:N, porque um mesmo cliente pode trazer vários equipamentos ao longo
do tempo:

- **`clientes`**: o cliente é identificado de forma única pelo e-mail (`UNIQUE`). Restrições `CHECK` validam o formato do e-mail e exigem que o celular tenha apenas dígitos (de 10 a 13).
- **`ordens_servico`**: cada OS aponta para um cliente por chave estrangeira com `ON DELETE CASCADE`. Ao excluir um cliente, as OS dele também são excluídas e nenhuma fica órfã. O `status` só aceita os valores `Aberto`, `Em análise`, `Aguardando peça`, `Concluído` e `Entregue`.

Além das tabelas, o script cria:
- **índices** em `cliente_id` e `status`, que aceleram os filtros do painel;
- um **trigger** que atualiza `data_atualizacao` sempre que uma OS muda, sem depender da aplicação;
- **políticas de RLS (Row Level Security)**, explicadas na seção seguinte;
- um conjunto de **dados fictícios** para demonstração.

## Decisões de segurança

- **Privilégio mínimo por aplicação.** O app do balcão usa a chave pública `anon`. Pelas políticas de RLS, essa chave só consegue consultar e inserir, e só abre OS com status `Aberto`: ela não edita nem exclui nada. A chave `service_role`, que tem acesso total, fica restrita ao painel do gerente.
- **Credenciais fora do código.** As chaves são lidas de `.env` ou `.streamlit/secrets.toml`, e os dois arquivos estão no `.gitignore`. O repositório traz apenas o `.env.example`, com os nomes das variáveis e sem valores.
- **Validação em duas camadas.** As mesmas regras são verificadas na interface, que dá um retorno imediato ao usuário, e no banco, por `CHECK` e `UNIQUE`, para que nenhum dado inválido seja gravado mesmo que chegue por outro caminho.
- **Tratamento de erros.** Todas as operações com o banco ficam em `try/except` e mostram mensagens amigáveis ao usuário.
- **LGPD.** Os dados de demonstração são todos fictícios.

## Como executar

**Requisitos:** Python 3.10+ e uma conta gratuita no [Supabase](https://supabase.com).

1. **Banco:** no SQL Editor do Supabase, cole e execute o `sql/schema.sql`.
2. **Dependências:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Credenciais:** copie o `.env.example` para `.env` e preencha com a Project URL e as chaves `anon` e `service_role`, que ficam em *Project Settings → API Keys*. A URL deve ter só o endereço do projeto (`https://xxxx.supabase.co`), sem `/rest/v1`.
4. **Aplicações:**
   ```bash
   python app_gradio.py            # atendimento: http://127.0.0.1:7860 + link público temporário
   streamlit run app_streamlit.py  # painel: http://localhost:8501
   ```

## Estrutura do projeto

```
techfix/
├── sql/schema.sql                  # criação do banco: tabelas, restrições, índices, trigger, RLS e dados de demonstração
├── app_gradio.py                   # aplicação de atendimento
├── app_streamlit.py                # painel administrativo
├── requirements.txt                # dependências
├── .env.example                    # variáveis de ambiente necessárias (sem valores)
├── .streamlit/secrets.toml.example # alternativa ao .env para o Streamlit
├── .gitignore
├── docs/                           # capturas de tela
└── README.md
```

## Autor

**Walter Cordeiro Guilhermino** · [GitHub](https://github.com/WalterCordeiroGuilhermino)
