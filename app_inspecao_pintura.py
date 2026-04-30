import json
import os
import re
import unicodedata
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from streamlit.errors import StreamlitSecretNotFoundError


SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

WORKSHEET_NAME_DEFAULT = "inspecao_pintura_3_0"
INSPECTION_TYPE_LABEL = "Inspecao diaria ou homologacao"
FORM_FEEDBACK_KEY = "inspecao_pintura_feedback"
DOCUMENT_CODE_DEFAULT = "FI - Pintura"
DOCUMENT_SECTOR_DEFAULT = "Qualidade Industrial"
DOCUMENT_REVISION_DEFAULT = "2"
DOCUMENT_AUTHOR_DEFAULT = "Evelyn Ruth Silva"
DOCUMENT_APPROVED_BY_DEFAULT = "Melina Favaro"

DEFAULT_HEADERS = [
    "record_id",
    "created_at",
    "tipo_inspecao",
    "data_inspecao",
    "hora_inicio",
    "hora_final",
    "inspetor",
    "cor_tinta",
    "fornecedor",
    "lote",
    "temperatura_secagem",
    "temperatura_cura",
    "velocidade",
    "transportador",
    "barra_retoque_liq",
    "barra_mistura_itens",
    "barra_retrabalho",
    "camada_topo_esquerda",
    "camada_topo_centro",
    "camada_topo_direita",
    "camada_meio_esquerda",
    "camada_meio_centro",
    "camada_meio_direita",
    "camada_baixo_esquerda",
    "camada_baixo_centro",
    "camada_baixo_direita",
    "avaliacao_inspetor",
    "teste_cura_mek",
    "teste_aderencia_grade",
    "teste_visual_barra",
    "item",
    "descricao",
    "pedido",
    "op",
    "observacoes",
]

LOCAL_SECRETS_PATH = Path(".streamlit/secrets.toml")
EXAMPLE_SECRETS_PATH = Path(".streamlit/secrets.toml.example")

BAR_OPTIONS = [
    ("Sim", "Com"),
    ("Nao", "Sem"),
    ("N/A", "NA"),
]

TEST_OPTIONS = [
    ("OK", "OK"),
    ("Nao OK", "N OK"),
    ("N/A", "NA"),
]

INSPECTOR_OPTIONS = [
    ("OK", "OK"),
    ("Nao OK", "N OK"),
    ("N/A", "NA"),
]

CAMADA_ROWS = [
    ("Topo", "topo"),
    ("Meio", "meio"),
    ("Baixo", "baixo"),
]

CAMADA_COLUMNS = [
    ("Esquerda", "esquerda"),
    ("Centro", "centro"),
    ("Direita", "direita"),
]

TIME_OPTIONS = [time(hour, minute) for hour in range(24) for minute in range(60)]


def get_secret_value(key: str, default: Any = None) -> Any:
    try:
        return st.secrets.get(key, default)
    except StreamlitSecretNotFoundError:
        return default


def load_document_metadata() -> dict[str, str]:
    # Os metadados ficam centralizados para alinhar a UI ao formulario fisico sem afetar o record.
    return {
        "code": get_secret_value("inspecao_pintura_document_code", "") or os.getenv(
            "INSPECAO_PINTURA_DOCUMENT_CODE",
            DOCUMENT_CODE_DEFAULT,
        ),
        "sector": get_secret_value("inspecao_pintura_sector", "") or os.getenv(
            "INSPECAO_PINTURA_SECTOR",
            DOCUMENT_SECTOR_DEFAULT,
        ),
        "revision": get_secret_value("inspecao_pintura_revision", "") or os.getenv(
            "INSPECAO_PINTURA_REVISION",
            DOCUMENT_REVISION_DEFAULT,
        ),
        "updated_at": date.today().strftime("%d/%m/%Y"),
        "author": get_secret_value("inspecao_pintura_author", "") or os.getenv(
            "INSPECAO_PINTURA_AUTHOR",
            DOCUMENT_AUTHOR_DEFAULT,
        ),
        "approved_by": get_secret_value("inspecao_pintura_approved_by", "") or os.getenv(
            "INSPECAO_PINTURA_APPROVED_BY",
            DOCUMENT_APPROVED_BY_DEFAULT,
        ),
    }


def normalize_service_account_info(service_account_info: dict[str, Any]) -> dict[str, Any]:
    normalized_info = dict(service_account_info)
    private_key = normalized_info.get("private_key")

    if isinstance(private_key, str) and "\\n" in private_key and "\n" not in private_key:
        normalized_info["private_key"] = private_key.replace("\\n", "\n")

    return normalized_info


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text).strip()


def build_record_id(prefix: str = "insp-pintura") -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}"


def load_service_account_info() -> dict[str, Any]:
    service_account = get_secret_value("gcp_service_account")
    if service_account:
        return normalize_service_account_info(dict(service_account))

    raw_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "").strip()
    if raw_json:
        return normalize_service_account_info(json.loads(raw_json))

    raise RuntimeError(
        "Credenciais do Google Sheets nao encontradas. Configure st.secrets['gcp_service_account'] "
        "ou a variavel GCP_SERVICE_ACCOUNT_JSON."
    )


def load_app_settings() -> dict[str, str]:
    spreadsheet_id = get_secret_value("google_sheets_spreadsheet_id", "") or os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    worksheet_name = get_secret_value("google_sheets_worksheet_name_inspecao", "") or os.getenv(
        "GOOGLE_SHEETS_WORKSHEET_NAME_INSPECAO",
        WORKSHEET_NAME_DEFAULT,
    )

    if not spreadsheet_id:
        raise RuntimeError("Informe google_sheets_spreadsheet_id no secrets.toml ou GOOGLE_SHEETS_SPREADSHEET_ID.")

    return {
        "spreadsheet_id": spreadsheet_id,
        "worksheet_name": worksheet_name,
    }


@st.cache_resource(show_spinner=False)
def get_sheets_client_and_settings():
    service_account_info = load_service_account_info()
    settings = load_app_settings()

    credentials = ServiceAccountCredentials.from_service_account_info(service_account_info, scopes=SHEETS_SCOPES)
    sheets_client = gspread.authorize(credentials)

    return sheets_client, settings


def get_worksheet():
    sheets_client, settings = get_sheets_client_and_settings()
    spreadsheet = sheets_client.open_by_key(settings["spreadsheet_id"])

    try:
        worksheet = spreadsheet.worksheet(settings["worksheet_name"])
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=settings["worksheet_name"], rows=2000, cols=40)
        worksheet.append_row(DEFAULT_HEADERS)

    headers = worksheet.row_values(1)
    if headers != DEFAULT_HEADERS:
        worksheet.update(range_name="A1:AI1", values=[DEFAULT_HEADERS])

    return worksheet


def save_record(record: dict[str, Any]) -> None:
    worksheet = get_worksheet()
    row = [record.get(header, "") for header in DEFAULT_HEADERS]
    worksheet.append_row(row, value_input_option="USER_ENTERED")


def load_records() -> pd.DataFrame:
    worksheet = get_worksheet()
    records = worksheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=DEFAULT_HEADERS)
    return pd.DataFrame(records)


@st.cache_data(ttl=30, show_spinner=False)
def load_records_cached() -> pd.DataFrame:
    # Mantem a consulta da aba leve sem alterar o contrato dos dados salvos.
    return load_records()


def normalize_optional_number(value: str) -> str:
    cleaned = normalize_text(value)
    if not cleaned:
        return ""
    return cleaned.replace(",", ".")


def build_inspection_record(
    tipo_inspecao: str,
    data_inspecao: date,
    hora_inicio: time,
    hora_final: time,
    inspetor: str,
    cor_tinta: str,
    fornecedor: str,
    lote: str,
    temperatura_secagem: str,
    temperatura_cura: str,
    velocidade: str,
    transportador: str,
    barra_retoque_liq: str,
    barra_mistura_itens: str,
    barra_retrabalho: str,
    camada_values: dict[str, str],
    avaliacao_inspetor: str,
    teste_cura_mek: str,
    teste_aderencia_grade: str,
    teste_visual_barra: str,
    item: str,
    descricao: str,
    pedido: str,
    op: str,
    observacoes: str,
) -> dict[str, str]:
    return {
        "record_id": build_record_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tipo_inspecao": tipo_inspecao,
        "data_inspecao": data_inspecao.isoformat(),
        "hora_inicio": hora_inicio.strftime("%H:%M"),
        "hora_final": hora_final.strftime("%H:%M"),
        "inspetor": normalize_text(inspetor),
        "cor_tinta": normalize_text(cor_tinta),
        "fornecedor": normalize_text(fornecedor),
        "lote": normalize_text(lote),
        "temperatura_secagem": normalize_optional_number(temperatura_secagem),
        "temperatura_cura": normalize_optional_number(temperatura_cura),
        "velocidade": normalize_text(velocidade),
        "transportador": normalize_text(transportador),
        "barra_retoque_liq": barra_retoque_liq,
        "barra_mistura_itens": barra_mistura_itens,
        "barra_retrabalho": barra_retrabalho,
        "camada_topo_esquerda": camada_values["camada_topo_esquerda"],
        "camada_topo_centro": camada_values["camada_topo_centro"],
        "camada_topo_direita": camada_values["camada_topo_direita"],
        "camada_meio_esquerda": camada_values["camada_meio_esquerda"],
        "camada_meio_centro": camada_values["camada_meio_centro"],
        "camada_meio_direita": camada_values["camada_meio_direita"],
        "camada_baixo_esquerda": camada_values["camada_baixo_esquerda"],
        "camada_baixo_centro": camada_values["camada_baixo_centro"],
        "camada_baixo_direita": camada_values["camada_baixo_direita"],
        "avaliacao_inspetor": avaliacao_inspetor,
        "teste_cura_mek": teste_cura_mek,
        "teste_aderencia_grade": teste_aderencia_grade,
        "teste_visual_barra": teste_visual_barra,
        "item": normalize_text(item),
        "descricao": normalize_text(descricao),
        "pedido": normalize_text(pedido),
        "op": normalize_text(op),
        "observacoes": normalize_text(observacoes),
    }


def get_default_form_state() -> dict[str, Any]:
    return {
        "data_inspecao": date.today(),
        "hora_inicio": time(8, 0),
        "hora_final": time(17, 0),
        "inspetor": "",
        "pedido": "",
        "op": "",
        "item": "",
        "descricao": "",
        "cor_tinta": "",
        "fornecedor": "",
        "lote": "",
        "temperatura_secagem": "",
        "temperatura_cura": "",
        "velocidade": "",
        "transportador": "",
        "barra_retoque_liq": None,
        "barra_mistura_itens": None,
        "barra_retrabalho": None,
        "camada_topo_esquerda": "",
        "camada_topo_centro": "",
        "camada_topo_direita": "",
        "camada_meio_esquerda": "",
        "camada_meio_centro": "",
        "camada_meio_direita": "",
        "camada_baixo_esquerda": "",
        "camada_baixo_centro": "",
        "camada_baixo_direita": "",
        "avaliacao_inspetor": None,
        "teste_cura_mek": None,
        "teste_aderencia_grade": None,
        "teste_visual_barra": None,
    }


def initialize_form_state() -> None:
    # Centraliza os defaults para evitar que o usuario perca dados em validacoes.
    for key, value in get_default_form_state().items():
        st.session_state.setdefault(key, value)


def reset_form_state() -> None:
    for key, value in get_default_form_state().items():
        st.session_state[key] = value


def set_feedback(kind: str, title: str, message: str, payload: dict[str, Any] | None = None) -> None:
    st.session_state[FORM_FEEDBACK_KEY] = {
        "kind": kind,
        "title": title,
        "message": message,
        "payload": payload,
    }


def render_feedback() -> None:
    feedback = st.session_state.get(FORM_FEEDBACK_KEY)
    if not feedback:
        return

    body = f"**{feedback['title']}**\n\n{feedback['message']}"

    if feedback["kind"] == "success":
        st.success(body)
    elif feedback["kind"] == "warning":
        st.warning(body)
    elif feedback["kind"] == "error":
        st.error(body)
    else:
        st.info(body)

    if feedback.get("payload"):
        with st.expander("Ver registro salvo"):
            st.json(feedback["payload"])


def clear_feedback() -> None:
    st.session_state.pop(FORM_FEEDBACK_KEY, None)


def show_configuration_help(error_message: str) -> None:
    st.error(error_message)
    st.info(
        f"Preencha o arquivo {LOCAL_SECRETS_PATH} com as credenciais da conta de servico "
        "e o ID da planilha do Google Sheets."
    )
    st.caption(f"Modelo disponivel em: {EXAMPLE_SECRETS_PATH}")


def render_styles() -> None:
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

            :root {
                --brand-900: #0A2540;
                --brand-700: #1D4ED8;
                --brand-100: #EAF2FF;
                --white: #FFFFFF;
                --gray-50: #F5F7FA;
                --gray-100: #EDF2F7;
                --gray-200: #D1D5DB;
                --gray-300: #CBD5E1;
                --gray-500: #64748B;
                --gray-700: #334155;
                --shadow-soft: 0 4px 14px rgba(10, 37, 64, 0.06);
                --radius-lg: 16px;
                --radius-md: 12px;
                --radius-sm: 10px;
            }

            html,
            body,
            [data-testid="stAppViewContainer"],
            .stApp {
                color-scheme: light !important;
                background: var(--gray-50) !important;
            }

            .stApp {
                font-family: 'Inter', 'Segoe UI', sans-serif;
                color: var(--brand-900);
            }

            .block-container {
                max-width: 1160px !important;
                padding-top: 1rem !important;
                padding-bottom: 2rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
            }

            [data-testid="stHeader"] {
                background: rgba(245, 247, 250, 0.96);
                border-bottom: 1px solid rgba(10, 37, 64, 0.06);
            }

            /* st.form removido — regra abaixo mantida por compatibilidade caso reintroduzido */
            div[data-testid="stForm"] {
                border: none !important;
                background: transparent !important;
                padding: 0 !important;
            }

            div[data-testid="stVerticalBlockBorderWrapper"] {
                background: var(--white);
                border: 1px solid rgba(10, 37, 64, 0.08) !important;
                border-radius: var(--radius-lg) !important;
                box-shadow: var(--shadow-soft);
                padding: 1.15rem !important;
            }

            .st-key-document_header div[data-testid="stVerticalBlockBorderWrapper"] {
                background: var(--white);
                border: 1px solid rgba(10, 37, 64, 0.12) !important;
                box-shadow: var(--shadow-soft);
            }

            .document-shell {
                display: flex;
                flex-direction: column;
                gap: 1rem;
            }

            .document-kicker {
                margin: 0 0 0.35rem 0;
                color: var(--brand-700);
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }

            .document-title {
                margin: 0;
                color: var(--brand-900);
                font-size: clamp(1.5rem, 2.5vw, 2rem);
                font-weight: 800;
                line-height: 1.15;
                letter-spacing: -0.02em;
            }

            .document-subtitle {
                margin: 0.35rem 0 0 0;
                color: var(--gray-700);
                font-size: 0.95rem;
                font-weight: 600;
            }

            .document-code {
                display: inline-flex;
                align-items: center;
                width: fit-content;
                margin-top: 0.75rem;
                padding: 0.32rem 0.72rem;
                border-radius: 999px;
                background: var(--brand-100);
                border: 1px solid rgba(29, 78, 216, 0.16);
                color: var(--brand-900);
                font-size: 0.82rem;
                font-weight: 700;
            }

            .document-meta-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.65rem;
            }

            .document-meta-item {
                padding: 0.7rem 0.8rem;
                border-radius: var(--radius-md);
                background: var(--gray-50);
                border: 1px solid rgba(10, 37, 64, 0.08);
            }

            .document-meta-label {
                display: block;
                margin-bottom: 0.18rem;
                color: var(--gray-500);
                font-size: 0.74rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }

            .document-meta-value {
                color: var(--brand-900);
                font-size: 0.9rem;
                font-weight: 700;
                line-height: 1.45;
            }

            .section-header {
                display: flex;
                flex-direction: column;
                gap: 0.35rem;
                margin-bottom: 1.1rem;
            }

            .section-kicker {
                color: var(--brand-700);
                font-size: 0.76rem;
                font-weight: 700;
                letter-spacing: 0.08em;
                text-transform: uppercase;
            }

            .section-title {
                margin: 0;
                color: var(--brand-900);
                font-size: 1.3rem;
                font-weight: 700;
                letter-spacing: -0.02em;
            }

            .section-description {
                margin: 0;
                color: var(--gray-500);
                font-size: 0.9rem;
                line-height: 1.5;
            }

            .subsection-title {
                margin: 0 0 0.95rem 0;
                color: var(--brand-900);
                font-size: 0.92rem;
                font-weight: 700;
                letter-spacing: 0.01em;
            }

            .field-label {
                margin: 0 0 0.42rem 0;
                color: var(--gray-700);
                font-size: 0.83rem;
                font-weight: 600;
                letter-spacing: 0.02em;
            }

            .field-required {
                color: #dc2626;
                margin-left: 0.2rem;
            }

            .helper-text {
                margin: -0.12rem 0 0.55rem 0;
                color: var(--gray-500);
                font-size: 0.76rem;
                line-height: 1.5;
            }

            .section-note {
                margin: 0;
                color: var(--gray-500);
                font-size: 0.84rem;
                line-height: 1.55;
            }

            .st-key-form_intro div[data-testid="stVerticalBlockBorderWrapper"] {
                background: var(--white);
                border-color: rgba(10, 37, 64, 0.1) !important;
                box-shadow: none;
            }

            .intro-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.3rem;
                padding: 0.28rem 0.6rem;
                border-radius: 999px;
                background: var(--gray-100);
                color: var(--brand-900);
                font-size: 0.72rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }

            .intro-title {
                margin: 0.65rem 0 0.3rem 0;
                color: var(--brand-900);
                font-size: 1rem;
                font-weight: 700;
            }

            .intro-copy {
                margin: 0;
                color: var(--gray-500);
                font-size: 0.88rem;
                line-height: 1.55;
            }

            div[data-testid="stTextInput"] input,
            div[data-testid="stDateInput"] input,
            div[data-testid="stTimeInput"] input,
            div[data-testid="stTextArea"] textarea {
                min-height: 48px !important;
                border-radius: 12px !important;
                border: 1px solid var(--gray-300) !important;
                background: var(--white) !important;
                color: var(--brand-900) !important;
                font-size: 0.95rem !important;
                font-weight: 500 !important;
                padding: 0.75rem 0.95rem !important;
                box-shadow: none !important;
                transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
            }

            div[data-testid="stTextArea"] textarea {
                min-height: 118px !important;
            }

            div[data-testid="stTextInput"] input::placeholder,
            div[data-testid="stTextArea"] textarea::placeholder {
                color: #94a3b8 !important;
                opacity: 1 !important;
            }

            div[data-testid="stTextInput"] input:hover,
            div[data-testid="stDateInput"] input:hover,
            div[data-testid="stTimeInput"] input:hover,
            div[data-testid="stTextArea"] textarea:hover,
            div[data-baseweb="select"] > div:hover {
                border-color: rgba(29, 78, 216, 0.45) !important;
            }

            div[data-testid="stTextInput"] input:focus,
            div[data-testid="stDateInput"] input:focus,
            div[data-testid="stTimeInput"] input:focus,
            div[data-testid="stTextArea"] textarea:focus {
                border-color: var(--brand-700) !important;
                box-shadow: 0 0 0 4px rgba(29, 78, 216, 0.12) !important;
            }

            div[data-testid="stDateInput"] label,
            div[data-testid="stTimeInput"] label,
            div[data-testid="stTextInput"] label,
            div[data-testid="stTextArea"] label {
                display: none !important;
            }

            div[data-baseweb="select"] > div {
                min-height: 48px !important;
                border-radius: 12px !important;
                border: 1px solid var(--gray-300) !important;
                background: var(--white) !important;
                box-shadow: none !important;
            }

            div[data-baseweb="select"] * {
                color: var(--brand-900) !important;
                font-size: 0.92rem !important;
            }

            /* Botões de seleção padrão / radio group */
            div[data-testid="stRadio"] {
                width: 100%;
            }

            div[data-testid="stRadio"] [role="radiogroup"] {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.55rem;
                width: 100%;
            }

            div[data-testid="stRadio"] [role="radiogroup"] label {
                margin: 0 !important;
                min-height: 44px;
                min-width: 0;
                padding: 0.55rem 0.75rem !important;
                border-radius: 12px !important;
                border: 1px solid var(--gray-300) !important;
                background: var(--white) !important;
                color: var(--gray-700) !important;
                font-size: 0.9rem !important;
                font-weight: 700 !important;
                box-shadow: none !important;
                transition: border-color 0.18s ease, background 0.18s ease, color 0.18s ease, transform 0.18s ease;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
            }

            div[data-testid="stRadio"] [role="radiogroup"] label:hover {
                border-color: rgba(29, 78, 216, 0.42) !important;
                color: var(--brand-700) !important;
            }

            div[data-testid="stRadio"] [role="radiogroup"] label[data-selected="true"],
            div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked),
            div[data-testid="stRadio"] [role="radiogroup"] label[aria-checked="true"] {
                border-color: var(--brand-700) !important;
                background: linear-gradient(135deg, #0A2540 0%, #1D4ED8 100%) !important;
                color: var(--white) !important;
            }

            div[data-testid="stRadio"] [role="radiogroup"] label[data-selected="true"] *,
            div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) *,
            div[data-testid="stRadio"] [role="radiogroup"] label[aria-checked="true"] * {
                color: var(--white) !important;
            }

            div[data-testid="stRadio"] [role="radiogroup"] label:active {
                transform: translateY(1px);
            }

            div[data-testid="stRadio"] [role="radiogroup"] label:focus-within,
            .st-key-save_inspection button:focus-visible,
            .st-key-refresh_records button:focus-visible,
            .stDownloadButton > button:focus-visible {
                outline: none !important;
                box-shadow: 0 0 0 3px rgba(29, 78, 216, 0.18) !important;
            }

            div[data-testid="stRadio"] [role="radiogroup"] label > div:first-of-type,
            div[data-testid="stRadio"] [role="radiogroup"] label input {
                display: none !important;
            }

            div[data-testid="stRadio"] [role="radiogroup"] label p {
                margin: 0 !important;
                width: auto !important;
                text-align: center !important;
                white-space: nowrap !important;
                line-height: 1.15 !important;
            }

            .st-key-section_barra .field-label {
                margin-bottom: 0.62rem;
            }

            .st-key-section_barra div[data-testid="stRadio"] {
                margin-bottom: 0.75rem;
            }

            .st-key-section_barra div[data-testid="stRadio"] [role="radiogroup"] {
                gap: 0.9rem;
            }

            .st-key-section_barra div[data-testid="stRadio"] [role="radiogroup"] label {
                min-height: 52px;
                padding-left: 0.85rem !important;
                padding-right: 0.85rem !important;
            }

            .grid-header {
                margin-bottom: 0.7rem;
            }

            .grid-axis-label,
            .grid-row-label {
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 48px;
                border-radius: 12px;
                background: var(--gray-100);
                color: var(--brand-900);
                font-size: 0.82rem;
                font-weight: 700;
                letter-spacing: 0.03em;
                text-transform: uppercase;
            }

            .grid-row-label {
                background: var(--gray-50);
            }

            .grid-caption {
                margin: 0 0 0.9rem 0;
                color: var(--gray-500);
                font-size: 0.84rem;
                line-height: 1.55;
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 0.45rem;
                padding: 0.35rem;
                background: var(--white);
                border: 1px solid rgba(10, 37, 64, 0.08);
                border-radius: 999px;
                margin-bottom: 1.1rem;
            }

            .stTabs [data-baseweb="tab"] {
                min-height: 44px;
                padding: 0.55rem 1.1rem;
                border-radius: 999px;
                color: var(--gray-500);
                font-size: 0.9rem;
                font-weight: 600;
            }

            .stTabs [data-baseweb="tab"]:hover {
                color: var(--brand-700);
            }

            .stTabs [aria-selected="true"] {
                background: linear-gradient(135deg, #0A2540 0%, #1D4ED8 100%) !important;
                color: #FFFFFF !important;
                border-radius: 999px !important;
                padding: 0.5rem 1.2rem;
                box-shadow: none;
            }

            .stTabs [aria-selected="true"] * {
                color: #FFFFFF !important;
            }

            .st-key-save_inspection button,
            .st-key-refresh_records button {
                min-height: 48px;
                border-radius: 12px !important;
                font-size: 0.94rem !important;
                font-weight: 700 !important;
                letter-spacing: 0.01em;
                box-shadow: none !important;
            }

            .st-key-save_inspection button:active,
            .st-key-refresh_records button:active {
                transform: translateY(1px);
            }

            .action-note {
                margin: 0;
                color: var(--gray-500);
                font-size: 0.86rem;
                line-height: 1.55;
            }

            [data-testid="stMetric"] {
                background: var(--white);
                border: 1px solid rgba(10, 37, 64, 0.08);
                border-radius: var(--radius-md);
                padding: 0.8rem 1rem;
                box-shadow: none;
            }

            [data-testid="stMetricLabel"] {
                color: var(--gray-500) !important;
            }

            [data-testid="stMetricValue"] {
                color: var(--brand-900) !important;
                font-weight: 800 !important;
            }

            [data-testid="stAlert"] {
                border-radius: 16px !important;
                border: 1px solid rgba(10, 37, 64, 0.06);
            }

            .records-toolbar {
                margin: 0;
                color: var(--gray-500);
                font-size: 0.92rem;
                line-height: 1.6;
            }

            @media (max-width: 900px) {
                .block-container {
                    padding-left: 0.8rem !important;
                    padding-right: 0.8rem !important;
                }

                div[data-testid="stVerticalBlockBorderWrapper"] {
                    padding: 1rem !important;
                }

                .document-meta-grid {
                    grid-template-columns: 1fr;
                }
            }

            @media (max-width: 640px) {
                .block-container {
                    padding-left: 0.5rem !important;
                    padding-right: 0.5rem !important;
                    padding-top: 0.6rem !important;
                }

                .document-title {
                    font-size: 1.4rem;
                }

                div[data-testid="stTextInput"] input,
                div[data-testid="stDateInput"] input,
                div[data-testid="stTimeInput"] input,
                div[data-testid="stTextArea"] textarea {
                    min-height: 46px !important;
                    font-size: 1rem !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_section_card(title: str, description: str, key: str, kicker: str) -> Any:
    section = st.container(border=True, key=key)
    with section:
        st.markdown(
            f"""
            <div class="section-header">
                <div class="section-kicker">{kicker}</div>
                <h2 class="section-title">{title}</h2>
                <p class="section-description">{description}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    return section


def render_field_label(container: Any, label: str, required: bool = False, help_text: str = "") -> None:
    required_html = "<span class='field-required'>*</span>" if required else ""
    container.markdown(f"<div class='field-label'>{label}{required_html}</div>", unsafe_allow_html=True)
    if help_text:
        container.markdown(f"<p class='helper-text'>{help_text}</p>", unsafe_allow_html=True)


def render_input_group(container: Any, fields: list[dict[str, Any]], column_spec: int | list[float] | tuple[float, ...]) -> dict[str, Any]:
    # O layout recebe apenas configuracoes de campo; a criacao do widget fica unificada.
    if isinstance(column_spec, int):
        columns = container.columns(column_spec, gap="medium")
    else:
        columns = container.columns(list(column_spec), gap="medium")

    values: dict[str, Any] = {}
    for field, column in zip(fields, columns):
        values[field["key"]] = render_input_field(column, field)
    return values


def render_input_field(container: Any, field: dict[str, Any]) -> Any:
    field_type = field.get("type", "text")
    label = field["label"]
    key = field["key"]

    render_field_label(
        container,
        label=label,
        required=field.get("required", False),
        help_text=field.get("help_text", ""),
    )

    widget_label = field.get("widget_label", label)

    if field_type == "date":
        return container.date_input(
            widget_label,
            key=key,
            label_visibility="collapsed",
            format="DD/MM/YYYY",
            width="stretch",
        )

    if field_type == "time":
        return container.selectbox(
            widget_label,
            options=TIME_OPTIONS,
            format_func=lambda value: value.strftime("%H:%M"),
            key=key,
            label_visibility="collapsed",
            width="stretch",
        )

    if field_type == "textarea":
        return container.text_area(
            widget_label,
            key=key,
            label_visibility="collapsed",
            placeholder=field.get("placeholder"),
            width="stretch",
        )

    return container.text_input(
        widget_label,
        key=key,
        label_visibility="collapsed",
        placeholder=field.get("placeholder"),
        width="stretch",
    )


def render_toggle_buttons(
    container: Any,
    label: str,
    options: list[tuple[str, str]],
    key: str,
    required: bool = False,
    help_text: str = "",
) -> str:
    render_field_label(container, label=label, required=required, help_text=help_text)

    option_labels = {option_value: option_label for option_label, option_value in options}
    option_values = list(option_labels)
    current = st.session_state.get(key)

    # Evita o repaint do tema do st.button usando um controle de selecao estavel.
    selection = container.radio(
        label,
        options=option_values,
        index=option_values.index(current) if current in option_values else None,
        format_func=lambda value: option_labels[value],
        key=key,
        horizontal=True,
        label_visibility="collapsed",
        width="stretch",
    )

    return selection if selection is not None else ""


def render_grid_inputs(container: Any) -> dict[str, str]:
    camada_values: dict[str, str] = {}
    container.markdown(
        "<p class='grid-caption'>Preencha a espessura em um ou registre o resultado em cada ponto da peca.</p>",
        unsafe_allow_html=True,
    )

    header_cols = container.columns([0.95, 1, 1, 1], gap="small")
    header_cols[0].markdown("<div class='grid-header'></div>", unsafe_allow_html=True)
    for header_column, (label, _) in zip(header_cols[1:], CAMADA_COLUMNS):
        header_column.markdown(f"<div class='grid-axis-label'>{label}</div>", unsafe_allow_html=True)

    for row_label, row_key in CAMADA_ROWS:
        row_columns = container.columns([0.95, 1, 1, 1], gap="small")
        row_columns[0].markdown(f"<div class='grid-row-label'>{row_label}</div>", unsafe_allow_html=True)

        for target_column, (column_label, column_key) in zip(row_columns[1:], CAMADA_COLUMNS):
            field_key = f"camada_{row_key}_{column_key}"
            camada_values[field_key] = render_input_field(
                target_column,
                {
                    "label": f"{row_label} / {column_label}",
                    "widget_label": f"{row_label} / {column_label}",
                    "key": field_key,
                    "placeholder": "Ex.: 80 um ou OK",
                    "type": "text",
                },
            ) or ""

    return camada_values


def render_form_intro() -> None:
    intro = st.container(border=True, key="form_intro")
    with intro:
        st.markdown(
            """
            <div class="intro-badge">Orientacoes</div>
            <h3 class="intro-title">Preenchimento objetivo para uso em linha</h3>
            <p class="intro-copy">
                Campos com <strong>*</strong> sao obrigatorios. Os horarios aceitam qualquer minuto de 00 a 59.
            </p>
            """,
            unsafe_allow_html=True,
        )


def render_header(metadata: dict[str, str]) -> None:
    header = st.container(border=True, key="document_header")
    with header:
        left_column, right_column = st.columns([1.45, 1], gap="medium")

        with left_column:
            st.markdown(
                f"""
                <div class="document-shell">
                    <div>
                        <p class="document-kicker">Qualidade Industrial</p>
                        <h1 class="document-title">Acompanhamento da Linha de Pintura 3.0</h1>
                        <p class="document-subtitle">Inspecao diaria ou homologacao</p>
                        <div class="document-code">{metadata['code']}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with right_column:
            st.markdown(
                f"""
                <div class="document-meta-grid">
                    <div class="document-meta-item">
                        <span class="document-meta-label">Setor</span>
                        <span class="document-meta-value">{metadata['sector']}</span>
                    </div>
                    <div class="document-meta-item">
                        <span class="document-meta-label">Revisao</span>
                        <span class="document-meta-value">{metadata['revision']}</span>
                    </div>
                    <div class="document-meta-item">
                        <span class="document-meta-label">Autor</span>
                        <span class="document-meta-value">{metadata['author']}</span>
                    </div>
                    <div class="document-meta-item">
                        <span class="document-meta-label">Aprovado por</span>
                        <span class="document-meta-value">{metadata['approved_by']}</span>
                    </div>
                    <div class="document-meta-item">
                        <span class="document-meta-label">Data de atualizacao</span>
                        <span class="document-meta-value">{metadata['updated_at']}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_identification_section() -> dict[str, Any]:
    values: dict[str, Any] = {}
    section = render_section_card(
        title="Identificacao",
        description="Dados de rastreabilidade da inspecao e do item.",
        key="section_identificacao",
        kicker="01 - Identificacao",
    )

    with section:
        values.update(
            render_input_group(
                section,
                [
                    {"label": "Data", "key": "data_inspecao", "type": "date", "required": True},
                    {"label": "Inspetor", "key": "inspetor", "placeholder": "Nome do inspetor", "required": True},
                ],
                2,
            )
        )
        values.update(
            render_input_group(
                section,
                [
                    {"label": "Pedido", "key": "pedido", "placeholder": "Numero do pedido"},
                    {"label": "O.P.", "key": "op", "placeholder": "Ordem de producao"},
                ],
                2,
            )
        )
        values.update(
            render_input_group(
                section,
                [
                    {"label": "Item", "key": "item", "placeholder": "Codigo do item"},
                    {"label": "Descricao", "key": "descricao", "placeholder": "Descricao da peca ou lote"},
                ],
                2,
            )
        )
        section.markdown("<p class='subsection-title'>Janela da inspecao</p>", unsafe_allow_html=True)
        values.update(
            render_input_group(
                section,
                [
                    {"label": "Hora de Inicio", "key": "hora_inicio", "type": "time"},
                    {"label": "Hora Final", "key": "hora_final", "type": "time"},
                ],
                2,
            )
        )

    return values


def render_paint_section() -> dict[str, Any]:
    values: dict[str, Any] = {}
    section = render_section_card(
        title="Tinta",
        description="Dados da tinta aplicada e parametros do processo.",
        key="section_tinta",
        kicker="02 - Tinta",
    )

    with section:
        values.update(
            render_input_group(
                section,
                [
                    {"label": "Cor da tinta", "key": "cor_tinta", "placeholder": "Ex.: RAL 9006"},
                    {"label": "Fornecedor", "key": "fornecedor", "placeholder": "Nome do fornecedor"},
                ],
                2,
            )
        )
        values.update(
            render_input_group(
                section,
                [
                    {"label": "Lote", "key": "lote", "placeholder": "Numero do lote"},
                ],
                1,
            )
        )
        section.markdown("<p class='subsection-title'>Processo</p>", unsafe_allow_html=True)
        values.update(
            render_input_group(
                section,
                [
                    {
                        "label": "Temperatura de Secagem",
                        "key": "temperatura_secagem",
                        "placeholder": "Ex.: 180",
                    },
                    {
                        "label": "Temperatura de Cura",
                        "key": "temperatura_cura",
                        "placeholder": "Ex.: 200",
                    },
                ],
                2,
            )
        )
        values.update(
            render_input_group(
                section,
                [
                    {
                        "label": "Velocidade",
                        "key": "velocidade",
                        "placeholder": "Ex.: 2,5 m/min",
                    },
                    {
                        "label": "Transportador",
                        "key": "transportador",
                        "placeholder": "Ex.: Linha 3",
                    },
                ],
                2,
            )
        )

    return values


def render_bar_section() -> dict[str, str]:
    section = render_section_card(
        title="Barra",
        description="Registro das ocorrencias observadas na barra.",
        key="section_barra",
        kicker="03 - Barra",
    )
    values: dict[str, str] = {}

    with section:
        values["barra_retoque_liq"] = render_toggle_buttons(section, "Retoque", BAR_OPTIONS, "barra_retoque_liq")
        values["barra_mistura_itens"] = render_toggle_buttons(
            section,
            "Mistura de itens",
            BAR_OPTIONS,
            "barra_mistura_itens",
        )
        values["barra_retrabalho"] = render_toggle_buttons(section, "Retrabalho", BAR_OPTIONS, "barra_retrabalho")

    return values


def render_layers_section() -> dict[str, str]:
    section = render_section_card(
        title="Camadas de Tinta",
        description="Registro por posicao da peca.",
        key="section_camadas",
        kicker="04 - Camadas",
    )
    with section:
        return render_grid_inputs(section)


def render_tests_section() -> dict[str, str]:
    section = render_section_card(
        title="Testes e Avaliacao",
        description="Resultado do inspetor e testes da barra.",
        key="section_testes",
        kicker="05 - Testes",
    )

    values: dict[str, str] = {}
    with section:
        first_column, second_column = section.columns(2, gap="medium")

        values["avaliacao_inspetor"] = render_toggle_buttons(
            first_column,
            "Avaliacao do inspetor",
            INSPECTOR_OPTIONS,
            "avaliacao_inspetor",
        )
        values["teste_cura_mek"] = render_toggle_buttons(
            first_column,
            "Teste de cura (MEK)",
            TEST_OPTIONS,
            "teste_cura_mek",
        )
        values["teste_aderencia_grade"] = render_toggle_buttons(
            second_column,
            "Teste de aderencia (grade)",
            TEST_OPTIONS,
            "teste_aderencia_grade",
        )
        values["teste_visual_barra"] = render_toggle_buttons(
            second_column,
            "Teste visual da barra",
            TEST_OPTIONS,
            "teste_visual_barra",
        )

    return values


def validate_form(identification: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if not (identification["inspetor"] or "").strip():
        errors.append("Informe o nome do inspetor.")

    return errors


def handle_form_submission(
    identification: dict[str, Any],
    paint: dict[str, Any],
    bar: dict[str, str],
    layers: dict[str, str],
    tests: dict[str, str],
) -> None:
    # A montagem do record continua isolada aqui para preservar a integracao com a planilha.
    errors = validate_form(identification)
    if errors:
        set_feedback(
            "warning",
            "Campos obrigatorios pendentes",
            " ".join(errors),
        )
        st.rerun()

    record = build_inspection_record(
        tipo_inspecao=INSPECTION_TYPE_LABEL,
        data_inspecao=identification["data_inspecao"],
        hora_inicio=identification["hora_inicio"],
        hora_final=identification["hora_final"],
        inspetor=identification["inspetor"],
        cor_tinta=paint["cor_tinta"],
        fornecedor=paint["fornecedor"],
        lote=paint["lote"],
        temperatura_secagem=paint["temperatura_secagem"],
        temperatura_cura=paint["temperatura_cura"],
        velocidade=paint["velocidade"],
        transportador=paint["transportador"],
        barra_retoque_liq=bar["barra_retoque_liq"],
        barra_mistura_itens=bar["barra_mistura_itens"],
        barra_retrabalho=bar["barra_retrabalho"],
        camada_values={key: value.strip() for key, value in layers.items()},
        avaliacao_inspetor=tests["avaliacao_inspetor"],
        teste_cura_mek=tests["teste_cura_mek"],
        teste_aderencia_grade=tests["teste_aderencia_grade"],
        teste_visual_barra=tests["teste_visual_barra"],
        item=identification["item"],
        descricao=identification["descricao"],
        pedido=identification["pedido"],
        op=identification["op"],
        observacoes="",
    )

    try:
        save_record(record)
        load_records_cached.clear()
        reset_form_state()
        set_feedback(
            "success",
            "Inspecao salva com sucesso",
            f"Registro {record['record_id']} enviado para a aba {get_sheets_client_and_settings()[1]['worksheet_name']}.",
            payload=record,
        )
        st.rerun()
    except Exception as error:
        set_feedback(
            "error",
            "Nao foi possivel salvar a inspecao",
            str(error),
        )
        st.rerun()


def render_inspection_form() -> None:
    initialize_form_state()
    render_feedback()
    render_form_intro()

    identification = render_identification_section()
    paint = render_paint_section()

    side_left, side_right = st.columns([0.95, 1.25], gap="medium")
    with side_left:
        bar = render_bar_section()
    with side_right:
        layers = render_layers_section()

    tests = render_tests_section()

    actions_left, actions_right = st.columns([1.7, 1], gap="medium")
    actions_left.markdown(
        """
        <p class="action-note">
            Os dados sao enviados ao Google Sheets mantendo a estrutura original do registro.
        </p>
        <p class="action-note" style="margin-top: 0.5rem; color: var(--gray-500); font-size: 0.80rem;">
            Desenvolvido por <strong style="color: var(--brand-900);">Marcelo Paidosz Junior</strong>
            &mdash; Aprendiz Operador WEB
        </p>
        """,
        unsafe_allow_html=True,
    )
    if actions_right.button(
        "Salvar inspecao",
        key="save_inspection",
        type="primary",
        use_container_width=True,
    ):
        handle_form_submission(
            identification=identification,
            paint=paint,
            bar=bar,
            layers=layers,
            tests=tests,
        )


def render_records_tab() -> None:
    toolbar = st.container(border=True, key="records_toolbar")
    with toolbar:
        title_column, action_column = st.columns([1.8, 1], gap="medium")
        title_column.markdown(
            """
            <div class="section-header">
                <div class="section-kicker">Historico</div>
                <h2 class="section-title">Registros salvos</h2>
                <p class="records-toolbar">
                    Consulte as inspecoes gravadas na planilha e atualize a lista quando necessario.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if action_column.button("Atualizar lista", key="refresh_records", type="secondary", use_container_width=True):
            clear_feedback()
            load_records_cached.clear()
            st.rerun()

    try:
        df = load_records_cached()
        metrics = st.columns(2, gap="medium")
        metrics[0].metric("Total de inspecoes", len(df))
        metrics[1].metric("Colunas sincronizadas", len(DEFAULT_HEADERS))

        if df.empty:
            st.info("Nenhuma inspecao encontrada na aba configurada.")
            return

        # Converte todos os valores para string para evitar problemas de tipo
        df = df.astype(str)
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as error:
        st.error(f"Nao foi possivel carregar os registros: {error}")


def main() -> None:
    st.set_page_config(
        page_title="Acompanhamento da Linha de Pintura 3.0",
        page_icon=":material/format_paint:",
        layout="wide",
    )
    render_styles()

    try:
        get_sheets_client_and_settings()
        get_worksheet()
    except Exception as error:
        show_configuration_help(str(error))
        st.stop()

    metadata = load_document_metadata()
    render_header(metadata)

    form_tab, records_tab = st.tabs(["Ficha de inspecao", "Registros salvos"])

    with form_tab:
        render_inspection_form()

    with records_tab:
        render_records_tab()

if __name__ == "__main__":
    main()
