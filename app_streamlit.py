"""
TechFix Informática — Painel Administrativo (Streamlit)

Painel do gerente/técnico para consultar, filtrar, cadastrar, editar,
excluir e acompanhar indicadores das ordens de serviço.

Execução:
    streamlit run app_streamlit.py
"""

import os
import re

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

st.set_page_config(page_title="TechFix — Painel", page_icon="🛠️", layout="wide")

STATUS = ["Aberto", "Em análise", "Aguardando peça", "Concluído", "Entregue"]
REGEX_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
REGEX_CELULAR = re.compile(r"^[0-9]{10,13}$")


# ---------------------------------------------------------------------
# Credenciais: primeiro .streamlit/secrets.toml, depois variáveis de
# ambiente / .env. Nada fica escrito no código.
# O painel usa a chave SERVICE_ROLE (acesso total, ignora o RLS)
# ---------------------------------------------------------------------
def ler_credencial(nome: str) -> str | None:
    try:
        if nome in st.secrets:
            return st.secrets[nome]
    except Exception:
        pass  # secrets.toml não existe — tenta o .env
    load_dotenv()
    return os.getenv(nome)


@st.cache_resource
def conectar() -> Client | None:
    url = ler_credencial("SUPABASE_URL")
    chave = ler_credencial("SUPABASE_SERVICE_KEY") or ler_credencial("SUPABASE_KEY")
    if not url or not chave:
        return None
    try:
        return create_client(url, chave)
    except Exception:
        return None


supabase = conectar()
if supabase is None:
    st.error(
        "Não foi possível conectar ao Supabase. Configure SUPABASE_URL e "
        "SUPABASE_SERVICE_KEY em `.streamlit/secrets.toml` ou no `.env`."
    )
    st.stop()


# ---------------------------------------------------------------------
# Leitura de dados (com cache curto para não consultar o banco a cada clique)
# ---------------------------------------------------------------------
@st.cache_data(ttl=30, show_spinner="Carregando dados...")
def carregar_os() -> pd.DataFrame:
    """OS + dados do cliente (join pela chave estrangeira cliente_id)."""
    resp = (
        supabase.table("ordens_servico")
        .select("*, clientes(nome, email, celular_whatsapp, endereco)")
        .order("id", desc=True)
        .execute()
    )
    linhas = []
    for r in resp.data:
        c = r.get("clientes") or {}
        linhas.append(
            {
                "OS": r["id"],
                "Cliente": c.get("nome"),
                "E-mail": c.get("email"),
                "Celular": c.get("celular_whatsapp"),
                "Endereço": c.get("endereco"),
                "Modelo": r["modelo_computador"],
                "Problema": r["problema_relatado"],
                "Status": r["status"],
                "Abertura": r["data_abertura"],
                "Atualização": r["data_atualizacao"],
                "cliente_id": r["cliente_id"],
            }
        )
    df = pd.DataFrame(linhas)
    if not df.empty:
        for col in ["Abertura", "Atualização"]:
            df[col] = (
                pd.to_datetime(df[col], utc=True)
                .dt.tz_convert("America/Sao_Paulo")
                .dt.tz_localize(None)
            )
    return df


@st.cache_data(ttl=30, show_spinner=False)
def carregar_clientes() -> pd.DataFrame:
    resp = supabase.table("clientes").select("*").order("nome").execute()
    return pd.DataFrame(resp.data)


def recarregar():
    """Limpa o cache depois de qualquer alteração no banco."""
    carregar_os.clear()
    carregar_clientes.clear()


def erro_amigavel(erro: Exception) -> str:
    texto = str(erro).lower()
    if "duplicate" in texto or "23505" in texto:
        return "Já existe um cliente com esse e-mail."
    if "check constraint" in texto or "23514" in texto:
        return "Dado recusado pelo banco (verifique e-mail, celular ou status)."
    if "foreign key" in texto or "23503" in texto:
        return "Registro vinculado a outro (chave estrangeira)."
    if "connect" in texto or "timeout" in texto:
        return "Falha de conexão com o banco. Verifique a internet."
    return "Erro inesperado ao acessar o banco."


def validar_cliente(nome, endereco, email, celular) -> list[str]:
    erros = []
    if not all(v.strip() for v in [nome, endereco, email, celular]):
        erros.append("Preencha nome, endereço, e-mail e celular.")
    if email.strip() and not REGEX_EMAIL.match(email.strip()):
        erros.append("E-mail em formato inválido.")
    if celular.strip() and not REGEX_CELULAR.match(celular.strip()):
        erros.append("Celular deve ter só números (10 a 13 dígitos, com DDD).")
    return erros


def rotulo_os(linha) -> str:
    return f"OS {linha['OS']} — {linha['Cliente']} — {linha['Modelo']} ({linha['Status']})"


# Mensagem de sucesso que sobrevive ao st.rerun()
if "aviso" in st.session_state:
    st.success(st.session_state.pop("aviso"))

# ---------------------------------------------------------------------
# Carga inicial
# ---------------------------------------------------------------------
try:
    df_os = carregar_os()
    df_clientes = carregar_clientes()
except Exception as e:
    st.error(f"Não foi possível carregar os dados. {erro_amigavel(e)}")
    st.stop()

# ---------------------------------------------------------------------
# Barra lateral: filtros
# ---------------------------------------------------------------------
st.sidebar.title("🔎 Filtros")
f_nome = st.sidebar.text_input("Nome do cliente", placeholder="Parte do nome")
f_email = st.sidebar.text_input("E-mail", placeholder="Parte do e-mail")
f_status = st.sidebar.multiselect("Status", STATUS, placeholder="Todos")
if st.sidebar.button("🔄 Atualizar dados", width="stretch"):
    recarregar()
    st.rerun()

df_filtrado = df_os.copy()
if not df_filtrado.empty:
    if f_nome:
        df_filtrado = df_filtrado[
            df_filtrado["Cliente"].str.contains(f_nome, case=False, na=False, regex=False)
        ]
    if f_email:
        df_filtrado = df_filtrado[
            df_filtrado["E-mail"].str.contains(f_email, case=False, na=False, regex=False)
        ]
    if f_status:
        df_filtrado = df_filtrado[df_filtrado["Status"].isin(f_status)]

st.sidebar.caption(f"{len(df_filtrado)} de {len(df_os)} ordens exibidas")

# ---------------------------------------------------------------------
# Cabeçalho e abas
# ---------------------------------------------------------------------
st.title("TechFix Informática — Painel Administrativo")
aba_consultar, aba_cadastrar, aba_editar, aba_indicadores = st.tabs(
    ["📋 Consultar", "➕ Cadastrar", "✏️ Editar/Excluir", "📊 Indicadores"]
)

# ============================ CONSULTAR ===============================
with aba_consultar:
    st.subheader("Ordens de serviço")
    if df_filtrado.empty:
        st.info("Nenhuma ordem de serviço encontrada com os filtros atuais.")
    else:
        st.dataframe(
            df_filtrado.drop(columns=["cliente_id"]),
            width="stretch",
            hide_index=True,
            column_config={
                "OS": st.column_config.NumberColumn("OS", format="%d"),
                "Abertura": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                "Atualização": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
            },
        )
        # Desafio opcional: exportar os dados filtrados em CSV
        csv = df_filtrado.drop(columns=["cliente_id"]).to_csv(
            index=False, sep=";", encoding="utf-8-sig"
        )
        st.download_button(
            "⬇️ Exportar dados filtrados (CSV)",
            data=csv.encode("utf-8-sig"),
            file_name="ordens_servico_techfix.csv",
            mime="text/csv",
        )

    with st.expander("👥 Ver todos os clientes"):
        if df_clientes.empty:
            st.info("Nenhum cliente cadastrado.")
        else:
            st.dataframe(df_clientes, width="stretch", hide_index=True)

# ============================ CADASTRAR ===============================
with aba_cadastrar:
    st.subheader("Nova ordem de serviço")
    tipo = st.radio(
        "Cliente", ["Cliente já cadastrado", "Novo cliente"], horizontal=True
    )

    with st.form("form_nova_os", clear_on_submit=True):
        cliente_escolhido = None
        if tipo == "Cliente já cadastrado":
            if df_clientes.empty:
                st.warning("Ainda não há clientes. Escolha 'Novo cliente'.")
            else:
                opcoes = {
                    f"{r['nome']} — {r['email']}": r["id"]
                    for _, r in df_clientes.iterrows()
                }
                cliente_escolhido = st.selectbox("Selecione o cliente", list(opcoes))
        else:
            c1, c2 = st.columns(2)
            n_nome = c1.text_input("Nome do Cliente", placeholder="Ex.: Maria da Silva")
            n_email = c2.text_input("E-mail", placeholder="Ex.: maria@exemplo.com")
            n_endereco = c1.text_input("Endereço", placeholder="Rua, número - bairro")
            n_celular = c2.text_input(
                "Celular/WhatsApp", placeholder="Somente números. Ex.: 19999998888"
            )

        modelo = st.text_input("Modelo do Computador", placeholder="Ex.: Notebook Lenovo")
        problema = st.text_area("Problema Apresentado", placeholder="Descreva o defeito")
        status_novo = st.selectbox("Status inicial", STATUS, index=0)
        enviar = st.form_submit_button("Cadastrar OS", type="primary")

    if enviar:
        erros = []
        if not modelo.strip() or not problema.strip():
            erros.append("Preencha o modelo e o problema apresentado.")
        if tipo == "Novo cliente":
            erros += validar_cliente(n_nome, n_endereco, n_email, n_celular)
        elif cliente_escolhido is None:
            erros.append("Selecione um cliente.")

        if erros:
            for e in erros:
                st.warning(e)
        else:
            try:
                if tipo == "Novo cliente":
                    email_limpo = n_email.strip().lower()
                    existente = (
                        supabase.table("clientes").select("id")
                        .eq("email", email_limpo).limit(1).execute()
                    )
                    if existente.data:  # e-mail já existe: reaproveita
                        cliente_id = existente.data[0]["id"]
                    else:
                        cliente_id = (
                            supabase.table("clientes")
                            .insert({
                                "nome": n_nome.strip(),
                                "endereco": n_endereco.strip(),
                                "email": email_limpo,
                                "celular_whatsapp": n_celular.strip(),
                            })
                            .execute()
                            .data[0]["id"]
                        )
                else:
                    cliente_id = opcoes[cliente_escolhido]

                nova = (
                    supabase.table("ordens_servico")
                    .insert({
                        "cliente_id": int(cliente_id),
                        "modelo_computador": modelo.strip(),
                        "problema_relatado": problema.strip(),
                        "status": status_novo,
                    })
                    .execute()
                )
                recarregar()
                st.session_state["aviso"] = f"OS nº {nova.data[0]['id']} cadastrada com sucesso!"
                st.rerun()
            except Exception as e:
                st.error(f"Não foi possível cadastrar. {erro_amigavel(e)}")

# ========================== EDITAR / EXCLUIR ==========================
with aba_editar:
    col_os, col_cli = st.columns(2, gap="large")

    # ---------- Ordem de serviço ----------
    with col_os:
        st.subheader("Ordem de serviço")
        if df_os.empty:
            st.info("Nenhuma OS cadastrada.")
        else:
            mapa_os = {rotulo_os(r): r for _, r in df_os.iterrows()}
            escolha_os = st.selectbox("Selecione a OS", list(mapa_os), key="sel_os")
            os_sel = mapa_os[escolha_os]

            with st.form("form_editar_os"):
                e_status = st.selectbox(
                    "Status", STATUS, index=STATUS.index(os_sel["Status"])
                )
                e_modelo = st.text_input("Modelo do Computador", value=os_sel["Modelo"])
                e_problema = st.text_area("Problema Apresentado", value=os_sel["Problema"])
                salvar_os = st.form_submit_button("💾 Salvar alterações da OS", type="primary")

            if salvar_os:
                if not e_modelo.strip() or not e_problema.strip():
                    st.warning("Modelo e problema não podem ficar vazios.")
                else:
                    try:
                        supabase.table("ordens_servico").update({
                            "status": e_status,
                            "modelo_computador": e_modelo.strip(),
                            "problema_relatado": e_problema.strip(),
                        }).eq("id", int(os_sel["OS"])).execute()
                        recarregar()
                        st.session_state["aviso"] = f"OS nº {os_sel['OS']} atualizada."
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível atualizar. {erro_amigavel(e)}")

            st.markdown("##### 🗑️ Excluir OS")
            conf_os = st.checkbox(
                f"Confirmo que desejo excluir a OS nº {os_sel['OS']}",
                key=f"conf_os_{os_sel['OS']}",
            )
            if st.button("Excluir OS", disabled=not conf_os, key="btn_del_os"):
                try:
                    supabase.table("ordens_servico").delete().eq(
                        "id", int(os_sel["OS"])
                    ).execute()
                    recarregar()
                    st.session_state["aviso"] = f"OS nº {os_sel['OS']} excluída."
                    st.rerun()
                except Exception as e:
                    st.error(f"Não foi possível excluir. {erro_amigavel(e)}")

    # ---------- Cliente ----------
    with col_cli:
        st.subheader("Cliente")
        if df_clientes.empty:
            st.info("Nenhum cliente cadastrado.")
        else:
            mapa_cli = {
                f"{r['nome']} — {r['email']}": r for _, r in df_clientes.iterrows()
            }
            escolha_cli = st.selectbox("Selecione o cliente", list(mapa_cli), key="sel_cli")
            cli = mapa_cli[escolha_cli]

            with st.form("form_editar_cliente"):
                c_nome = st.text_input("Nome", value=cli["nome"])
                c_endereco = st.text_input("Endereço", value=cli["endereco"])
                c_email = st.text_input("E-mail", value=cli["email"])
                c_celular = st.text_input("Celular/WhatsApp", value=cli["celular_whatsapp"])
                salvar_cli = st.form_submit_button("💾 Salvar dados do cliente", type="primary")

            if salvar_cli:
                erros = validar_cliente(c_nome, c_endereco, c_email, c_celular)
                if erros:
                    for e in erros:
                        st.warning(e)
                else:
                    try:
                        supabase.table("clientes").update({
                            "nome": c_nome.strip(),
                            "endereco": c_endereco.strip(),
                            "email": c_email.strip().lower(),
                            "celular_whatsapp": c_celular.strip(),
                        }).eq("id", int(cli["id"])).execute()
                        recarregar()
                        st.session_state["aviso"] = f"Cliente {c_nome.strip()} atualizado."
                        st.rerun()
                    except Exception as e:
                        st.error(f"Não foi possível atualizar. {erro_amigavel(e)}")

            qtd_os = int((df_os["cliente_id"] == cli["id"]).sum()) if not df_os.empty else 0
            st.markdown("##### 🗑️ Excluir cliente")
            if qtd_os:
                st.warning(
                    f"Este cliente possui {qtd_os} OS. Elas também serão excluídas "
                    "(ON DELETE CASCADE)."
                )
            conf_cli = st.checkbox(
                f"Confirmo que desejo excluir {cli['nome']}",
                key=f"conf_cli_{cli['id']}",
            )
            if st.button("Excluir cliente", disabled=not conf_cli, key="btn_del_cli"):
                try:
                    supabase.table("clientes").delete().eq("id", int(cli["id"])).execute()
                    recarregar()
                    st.session_state["aviso"] = f"Cliente {cli['nome']} excluído."
                    st.rerun()
                except Exception as e:
                    st.error(f"Não foi possível excluir. {erro_amigavel(e)}")

# ============================ INDICADORES =============================
with aba_indicadores:
    st.subheader("Indicadores (considerando os filtros da barra lateral)")
    contagem = (
        df_filtrado["Status"].value_counts().reindex(STATUS, fill_value=0)
        if not df_filtrado.empty
        else pd.Series(0, index=STATUS)
    )

    st.metric("Total de OS", int(contagem.sum()))
    colunas = st.columns(len(STATUS))
    for col, status in zip(colunas, STATUS):
        col.metric(status, int(contagem[status]))

    st.markdown("#### OS por status")
    st.bar_chart(contagem.rename("Quantidade"), x_label="Status", y_label="Quantidade")

    if not df_filtrado.empty:
        st.markdown("#### OS abertas por dia")
        por_dia = df_filtrado.groupby(df_filtrado["Abertura"].dt.date).size()
        por_dia.index.name = "Data"
        st.line_chart(por_dia.rename("OS abertas"))
