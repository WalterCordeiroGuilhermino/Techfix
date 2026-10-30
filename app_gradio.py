"""
TechFix Informática — Aplicação de Atendimento (Gradio)

Interface web (computador e celular) usada no balcão para cadastrar o
cliente, o equipamento e o problema relatado. Os dados são gravados no
Supabase (PostgreSQL na nuvem).

Execução:
    python app_gradio.py
"""

import os
import re

import gradio as gr
from dotenv import load_dotenv
from supabase import Client, create_client

# ---------------------------------------------------------------------
# Conexão com o Supabase
# As credenciais vêm do arquivo .env
# O atendimento usa a chave ANON: pelas políticas RLS do schema.sql,
# ---------------------------------------------------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def conectar() -> Client | None:
    """Cria o cliente do Supabase ou retorna None se faltar configuração."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as erro:  # URL malformada, chave inválida etc.
        print(f"[ERRO] Falha ao criar cliente do Supabase: {erro}")
        return None


supabase = conectar()

# ---------------------------------------------------------------------
# Validação dos dados (feita ANTES de enviar ao banco)
# As mesmas regras existem como CHECK no banco — dupla proteção.
# ---------------------------------------------------------------------
REGEX_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
REGEX_CELULAR = re.compile(r"^[0-9]{10,13}$")


def validar(nome, endereco, email, celular, modelo, problema) -> list[str]:
    """Retorna a lista de erros encontrados (lista vazia = tudo certo)."""
    erros = []
    campos = {
        "Nome do Cliente": nome,
        "Endereço": endereco,
        "E-mail": email,
        "Celular/WhatsApp": celular,
        "Modelo do Computador": modelo,
        "Problema Apresentado": problema,
    }
    vazios = [rotulo for rotulo, valor in campos.items() if not valor.strip()]
    if vazios:
        erros.append("Preencha os campos obrigatórios: " + ", ".join(vazios) + ".")

    if email.strip() and not REGEX_EMAIL.match(email.strip()):
        erros.append("E-mail em formato inválido (exemplo: nome@dominio.com).")

    if celular.strip() and not REGEX_CELULAR.match(celular.strip()):
        erros.append(
            "Celular deve conter apenas números, com DDD, entre 10 e 13 dígitos "
            "(exemplo: 19999998888)."
        )
    return erros


# ---------------------------------------------------------------------
# Regra de negócio: cadastrar (ou reaproveitar) cliente e abrir a OS
# ---------------------------------------------------------------------
def cadastrar(nome, endereco, email, celular, modelo, problema):
    if supabase is None:
        return (
            "❌ **Banco de dados não configurado.** Verifique as variáveis "
            "SUPABASE_URL e SUPABASE_KEY no arquivo `.env`."
        )

    erros = validar(nome, endereco, email, celular, modelo, problema)
    if erros:
        return "⚠️ **Corrija antes de enviar:**\n\n" + "\n".join(f"- {e}" for e in erros)

    email = email.strip().lower()

    try:
        # 1) O e-mail já existe? Se sim, reaproveita o cliente.
        busca = (
            supabase.table("clientes")
            .select("id, nome")
            .eq("email", email)
            .limit(1)
            .execute()
        )

        if busca.data:
            cliente_id = busca.data[0]["id"]
            aviso_cliente = f"Cliente já cadastrado (**{busca.data[0]['nome']}**) — reaproveitado."
        else:
            # 2) Caso contrário, cria um cliente novo.
            novo = (
                supabase.table("clientes")
                .insert(
                    {
                        "nome": nome.strip(),
                        "endereco": endereco.strip(),
                        "email": email,
                        "celular_whatsapp": celular.strip(),
                    }
                )
                .execute()
            )
            cliente_id = novo.data[0]["id"]
            aviso_cliente = "Novo cliente cadastrado."

        # 3) Abre a ordem de serviço com status inicial 'Aberto'.
        os_criada = (
            supabase.table("ordens_servico")
            .insert(
                {
                    "cliente_id": cliente_id,
                    "modelo_computador": modelo.strip(),
                    "problema_relatado": problema.strip(),
                    "status": "Aberto",
                }
            )
            .execute()
        )
        numero_os = os_criada.data[0]["id"]

        return (
            f"✅ **Ordem de Serviço nº {numero_os} aberta com sucesso!**\n\n"
            f"{aviso_cliente} Status inicial: **Aberto**."
        )

    except Exception as erro:
        print(f"[ERRO] Falha no cadastro: {erro}")  # detalhe técnico só no terminal
        texto = str(erro).lower()
        if "duplicate" in texto or "23505" in texto:
            msg = "Este e-mail já está cadastrado. Tente novamente."
        elif "check constraint" in texto or "23514" in texto:
            msg = "Algum dado foi recusado pelo banco (formato de e-mail ou celular)."
        elif "row-level security" in texto or "42501" in texto:
            msg = "Sem permissão para gravar. Confira as políticas RLS do banco."
        elif "pgrst205" in texto or "42p01" in texto or "does not exist" in texto or "schema cache" in texto:
            msg = "As tabelas não foram encontradas no banco. Rode o schema.sql no SQL Editor do Supabase."
        elif "invalid api key" in texto or "jwt" in texto or "401" in texto:
            msg = "Chave do Supabase inválida. Confira SUPABASE_KEY no arquivo .env."
        elif "connect" in texto or "timeout" in texto or "name or service" in texto:
            msg = "Não foi possível conectar ao banco. Verifique a internet e a SUPABASE_URL."
        else:
            msg = "Erro inesperado ao gravar os dados. Tente novamente."
        return (
            f"❌ **Não foi possível cadastrar.** {msg}\n\n"
            f"<sub>Detalhe técnico: {str(erro)[:300]}</sub>"
        )


def limpar():
    """Esvazia todos os campos e a mensagem de retorno."""
    return "", "", "", "", "", "", ""


# ---------------------------------------------------------------------
# Interface (gr.Blocks) — em telas pequenas as colunas empilham sozinhas
# ---------------------------------------------------------------------
CSS = """
.gradio-container { max-width: 900px !important; margin: auto; }
#titulo h1 { margin-bottom: 0; }
"""

with gr.Blocks(title="TechFix — Atendimento") as app:
    gr.Markdown(
        """
        TechFix Informática
        ### Abertura de Ordem de Serviço

        Preencha **todos os campos** e toque em **Cadastrar**. Se o e-mail já
        estiver cadastrado, os dados do cliente são reaproveitados e apenas
        uma nova OS é aberta.
        """,
        elem_id="titulo",
    )

    with gr.Row():
        # Coluna 1: dados do cliente
        with gr.Column(min_width=280):
            gr.Markdown("#### 👤 Cliente")
            nome = gr.Textbox(label="Nome do Cliente", placeholder="Ex.: Maria da Silva")
            endereco = gr.Textbox(
                label="Endereço", placeholder="Ex.: Rua das Flores, 100 - Centro"
            )
            email = gr.Textbox(
                label="E-mail", placeholder="Ex.: maria@exemplo.com", type="email"
            )
            celular = gr.Textbox(
                label="Celular/WhatsApp",
                placeholder="Somente números, com DDD. Ex.: 19999998888",
                max_length=13,
            )

        # Coluna 2: dados do equipamento
        with gr.Column(min_width=280):
            gr.Markdown("#### 💻 Equipamento")
            modelo = gr.Textbox(
                label="Modelo do Computador",
                placeholder="Ex.: Notebook Dell Inspiron 15",
            )
            problema = gr.Textbox(
                label="Problema Apresentado",
                placeholder="Descreva o defeito relatado pelo cliente...",
                lines=6,
            )

    with gr.Row():
        btn_cadastrar = gr.Button("Cadastrar", variant="primary", size="lg")
        btn_limpar = gr.Button("Limpar", variant="secondary", size="lg")

    resultado = gr.Markdown()

    entradas = [nome, endereco, email, celular, modelo, problema]
    btn_cadastrar.click(cadastrar, inputs=entradas, outputs=resultado)
    btn_limpar.click(limpar, inputs=None, outputs=entradas + [resultado])


if __name__ == "__main__":
    if supabase is None:
        print("[AVISO] SUPABASE_URL/SUPABASE_KEY ausentes — confira o arquivo .env")
    # share=True gera um link público temporário (*.gradio.live) para
    # abrir a interface no celular.
    # (No Gradio 6, tema e CSS são passados ao launch.)
    app.launch(share=True, theme=gr.themes.Soft(), css=CSS)
