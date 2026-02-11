import os, json
import streamlit as st
import pandas as pd
from sheets_client import get_client, open_sheet_by_id, get_or_create_ws, clear_and_write_df

st.set_page_config(page_title="Pendências SEFAZ", layout="wide")

# Mapa BASE -> Sheet ID (vem do Render env var)
BASE_MAP = json.loads(os.environ.get("BASE_TO_SHEET_JSON", "{}"))

st.sidebar.title("📂 Menu")
pagina = st.sidebar.radio("Navegação", ["Upload", "Dashboard", "Detalhamento"])

MAPA_ABAS = {
    "Omissões de EFD": "OMISSAO_EFD",
    "Omissões e divergências de NFE": "NFE_OMISSAO_DIVERGENCIA",
    "NFe inexistente declarada": "NFE_INEXISTENTE_DECLARADA",
    "Omissões e Divergências CFe": "CFE_OMISSAO_DIVERGENCIA",
    "NFe sem REG_PAS": "NFE_SEM_REG_PAS",
}

def aplicar_prioridade(df):
    df["PRIORIDADE"] = "MÉDIO"
    df.loc[df["TIPO_PENDENCIA"] == "OMISSAO_EFD", "PRIORIDADE"] = "CRÍTICO"
    df.loc[df["TIPO_PENDENCIA"] == "NFE_INEXISTENTE_DECLARADA", "PRIORIDADE"] = "ALTO"
    df.loc[df["TIPO_PENDENCIA"] == "NFE_SEM_REG_PAS", "PRIORIDADE"] = "ALTO"
    return df

if "dados" not in st.session_state:
    st.session_state["dados"] = None

# =======================
# UPLOAD
# =======================
if pagina == "Upload":
    st.title("📥 Upload do Excel SEFAZ")
    uploaded = st.file_uploader("Envie o Excel bruto (.xlsx)", type=["xlsx"])

    if uploaded:
        xls = pd.ExcelFile(uploaded)
        det_list = []

        for aba, tipo in MAPA_ABAS.items():
            if aba in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=aba, dtype=str)
                df.columns = [str(c).strip().upper().replace(" ", "_") for c in df.columns]
                if "CGF" not in df.columns:
                    df["CGF"] = ""
                df["TIPO_PENDENCIA"] = tipo
                det_list.append(df)

        if det_list:
            det = pd.concat(det_list, ignore_index=True)
            det = aplicar_prioridade(det)

            # colunas operacionais
            if "STATUS" not in det.columns: det["STATUS"] = "PENDENTE"
            if "RESPONSAVEL" not in det.columns: det["RESPONSAVEL"] = ""
            if "PRAZO" not in det.columns: det["PRAZO"] = ""
            if "EVIDENCIA_LINK" not in det.columns: det["EVIDENCIA_LINK"] = ""
            if "OBS" not in det.columns: det["OBS"] = ""

            st.session_state["dados"] = det
            st.success("✅ Arquivo processado com sucesso! Vá para Dashboard.")
        else:
            st.error("❌ Nenhuma aba SEFAZ reconhecida encontrada.")

# =======================
# DASHBOARD
# =======================
elif pagina == "Dashboard":
    st.title("📊 Dashboard Geral")

    if st.session_state["dados"] is None:
        st.warning("Faça upload primeiro.")
        st.stop()

    det = st.session_state["dados"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 CRÍTICOS", int((det["PRIORIDADE"] == "CRÍTICO").sum()))
    c2.metric("🟠 ALTOS", int((det["PRIORIDADE"] == "ALTO").sum()))
    c3.metric("🟡 MÉDIOS", int((det["PRIORIDADE"] == "MÉDIO").sum()))
    c4.metric("📦 TOTAL", int(len(det)))

    st.subheader("Pendências por Tipo")
    st.bar_chart(det["TIPO_PENDENCIA"].value_counts())

    st.divider()
    st.subheader("☁️ Publicar no Google Sheets (planilha fixa)")

    if not BASE_MAP:
        st.error("Env var BASE_TO_SHEET_JSON não configurada no Render.")
        st.stop()

    base = st.selectbox("Selecione a BASE (cliente)", sorted(BASE_MAP.keys()))
    sheet_id = BASE_MAP[base]

    if st.button("🚀 Atualizar Google Sheets", type="primary"):
        try:
            resumo = (
                det.groupby("CGF")
                .agg(
                    QTDE_PENDENCIAS=("TIPO_PENDENCIA","size"),
                    QTDE_CRITICO=("PRIORIDADE", lambda s: (s=="CRÍTICO").sum()),
                    QTDE_ALTO=("PRIORIDADE", lambda s: (s=="ALTO").sum()),
                    TIPO_MAIS_COMUM=("TIPO_PENDENCIA", lambda s: s.value_counts().index[0] if len(s) else "")
                )
                .reset_index()
                .sort_values(["QTDE_CRITICO","QTDE_PENDENCIAS"], ascending=[False, False])
            )

            fila = det.copy()

            gc = get_client()
            ss = open_sheet_by_id(gc, sheet_id)

            ws = get_or_create_ws(ss, "PENDENCIAS_DETALHE", rows=max(2000, len(det)+20), cols=120)
            clear_and_write_df(ws, det)

            ws = get_or_create_ws(ss, "RESUMO_POR_CGF", rows=max(2000, len(resumo)+20), cols=50)
            clear_and_write_df(ws, resumo)

            ws = get_or_create_ws(ss, "FILA_TRABALHO", rows=max(2000, len(fila)+20), cols=120)
            clear_and_write_df(ws, fila)

            st.success("✅ Planilha atualizada com sucesso!")
        except Exception as e:
            st.exception(e)

# =======================
# DETALHAMENTO
# =======================
elif pagina == "Detalhamento":
    st.title("🔍 Detalhamento por CGF")

    if st.session_state["dados"] is None:
        st.warning("Faça upload primeiro.")
        st.stop()

    det = st.session_state["dados"]
    det["CGF"] = det["CGF"].astype(str)

    cgf_sel = st.selectbox("Selecione o CGF", sorted(det["CGF"].unique().tolist()))
    df_cgf = det[det["CGF"] == cgf_sel]

    st.dataframe(df_cgf, use_container_width=True)
