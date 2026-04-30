import io
import json
import mimetypes
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gspread
import pandas as pd
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from streamlit.errors import StreamlitSecretNotFoundError


SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
]

DEFAULT_HEADERS = [
    "record_id",
    "created_at",
    "nome",
    "email",
    "categoria",
    "valor",
    "valor_processado",
    "status",
    "descricao",
    "arquivo_nome",
    "arquivo_mime_type",
    "arquivo_drive_id",
    "arquivo_drive_link",
]

LOCAL_SECRETS_PATH = Path(".streamlit/secrets.toml")
EXAMPLE_SECRETS_PATH = Path(".streamlit/secrets.toml.example")
GOOGLE_DRIVE_OAUTH_CLIENT_PATH = Path(".streamlit/google_drive_oauth_client.json")
GOOGLE_DRIVE_OAUTH_CLIENT_EXAMPLE_PATH = Path(".streamlit/google_drive_oauth_client.example.json")
GOOGLE_DRIVE_OAUTH_TOKEN_PATH = Path(".streamlit/google_drive_user_token.json")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    compact = re.sub(r"\s+", " ", ascii_text).strip()
    return compact


def build_record_id(nome: str) -> str:
    slug = normalize_text(nome).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{slug or 'registro'}-{timestamp}"


def parse_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    cleaned = re.sub(r"[^0-9,.\-]", "", str(value).strip())
    if not cleaned:
        return 0.0

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")

    return float(cleaned or 0)


def resolve_status(processed_value: float, status_choice: str) -> str:
    if status_choice == "Prioritario":
        return "prioritario"
    if status_choice == "Normal":
        return "normal"
    return "prioritario" if processed_value >= 1000 else "normal"


def process_form_data(
    nome: str,
    email: str,
    categoria: str,
    valor: Any,
    descricao: str,
    status_choice: str,
) -> dict[str, Any]:
    processed_value = parse_float(valor)
    status = resolve_status(processed_value, status_choice)
    created_at = datetime.now(timezone.utc).isoformat()

    return {
        "record_id": build_record_id(nome),
        "created_at": created_at,
        "nome": normalize_text(nome),
        "email": email.strip().lower(),
        "categoria": categoria.strip(),
        "valor": processed_value,
        "valor_processado": f"R$ {processed_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "status": status,
        "descricao": normalize_text(descricao),
    }


def get_secret_value(key: str, default: Any = None) -> Any:
    try:
        return st.secrets.get(key, default)
    except StreamlitSecretNotFoundError:
        return default


def normalize_service_account_info(service_account_info: dict[str, Any]) -> dict[str, Any]:
    normalized_info = dict(service_account_info)
    private_key = normalized_info.get("private_key")

    # Some TOML/env setups persist the key with literal "\n" instead of real line breaks.
    if isinstance(private_key, str) and "\\n" in private_key and "\n" not in private_key:
        normalized_info["private_key"] = private_key.replace("\\n", "\n")

    return normalized_info


def load_service_account_info() -> dict[str, Any]:
    service_account = get_secret_value("gcp_service_account")
    if service_account:
        return normalize_service_account_info(dict(service_account))

    raw_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "").strip()
    if raw_json:
        return normalize_service_account_info(json.loads(raw_json))

    raise RuntimeError(
        "Credenciais nao encontradas. Configure st.secrets['gcp_service_account'] "
        "ou a variavel GCP_SERVICE_ACCOUNT_JSON."
    )


def load_app_settings() -> dict[str, str]:
    spreadsheet_id = get_secret_value("google_sheets_spreadsheet_id", "") or os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    worksheet_name = get_secret_value("google_sheets_worksheet_name", "") or os.getenv(
        "GOOGLE_SHEETS_WORKSHEET_NAME",
        "cadastros",
    )
    drive_folder_id = get_secret_value("google_drive_folder_id", "") or os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

    if not spreadsheet_id:
        raise RuntimeError("Informe google_sheets_spreadsheet_id no secrets.toml ou GOOGLE_SHEETS_SPREADSHEET_ID.")
    if not drive_folder_id:
        raise RuntimeError("Informe google_drive_folder_id no secrets.toml ou GOOGLE_DRIVE_FOLDER_ID.")

    return {
        "spreadsheet_id": spreadsheet_id,
        "worksheet_name": worksheet_name,
        "drive_folder_id": drive_folder_id,
    }


@st.cache_resource(show_spinner=False)
def get_sheets_client_and_settings():
    service_account_info = load_service_account_info()
    settings = load_app_settings()

    credentials = ServiceAccountCredentials.from_service_account_info(service_account_info, scopes=SHEETS_SCOPES)
    sheets_client = gspread.authorize(credentials)

    return sheets_client, settings


def load_drive_oauth_client_config() -> dict[str, Any] | None:
    raw_json = os.getenv("GOOGLE_DRIVE_OAUTH_CLIENT_JSON", "").strip()
    if raw_json:
        return json.loads(raw_json)

    if GOOGLE_DRIVE_OAUTH_CLIENT_PATH.exists():
        return json.loads(GOOGLE_DRIVE_OAUTH_CLIENT_PATH.read_text(encoding="utf-8"))

    return None


def save_drive_user_credentials(credentials: UserCredentials) -> None:
    GOOGLE_DRIVE_OAUTH_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOOGLE_DRIVE_OAUTH_TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")


def load_drive_user_credentials() -> UserCredentials | None:
    if not GOOGLE_DRIVE_OAUTH_TOKEN_PATH.exists():
        return None

    try:
        credentials = UserCredentials.from_authorized_user_file(str(GOOGLE_DRIVE_OAUTH_TOKEN_PATH), DRIVE_SCOPES)
    except Exception:
        return None

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_drive_user_credentials(credentials)

    if credentials.valid:
        return credentials

    return None


def start_drive_oauth_flow() -> None:
    client_config = load_drive_oauth_client_config()
    if not client_config:
        raise RuntimeError(
            "Adicione o arquivo .streamlit/google_drive_oauth_client.json com o OAuth Client "
            "do tipo Desktop App antes de conectar seu Google Drive."
        )

    flow = InstalledAppFlow.from_client_config(client_config, DRIVE_SCOPES)
    credentials = flow.run_local_server(
        host="localhost",
        port=0,
        open_browser=True,
        authorization_prompt_message="Abrindo o navegador para conectar seu Google Drive...",
        success_message="Conexao concluida. Voce pode fechar esta aba e voltar ao Streamlit.",
    )
    save_drive_user_credentials(credentials)


def disconnect_drive_oauth() -> None:
    if GOOGLE_DRIVE_OAUTH_TOKEN_PATH.exists():
        GOOGLE_DRIVE_OAUTH_TOKEN_PATH.unlink()


def get_drive_service():
    client_config = load_drive_oauth_client_config()
    if client_config:
        user_credentials = load_drive_user_credentials()
        if not user_credentials:
            raise RuntimeError(
                "Conecte seu Google Drive no painel lateral antes de enviar imagens para o Meu Drive."
            )
        return build("drive", "v3", credentials=user_credentials), "oauth_user"

    service_account_info = load_service_account_info()
    service_account_credentials = ServiceAccountCredentials.from_service_account_info(
        service_account_info,
        scopes=DRIVE_SCOPES,
    )
    return build("drive", "v3", credentials=service_account_credentials), "service_account"


def get_worksheet():
    sheets_client, settings = get_sheets_client_and_settings()
    spreadsheet = sheets_client.open_by_key(settings["spreadsheet_id"])

    try:
        worksheet = spreadsheet.worksheet(settings["worksheet_name"])
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=settings["worksheet_name"], rows=1000, cols=20)
        worksheet.append_row(DEFAULT_HEADERS)

    headers = worksheet.row_values(1)
    if headers != DEFAULT_HEADERS:
        worksheet.update(range_name="A1:M1", values=[DEFAULT_HEADERS])

    return worksheet


def upload_file_to_drive(uploaded_file, record_id: str) -> dict[str, str]:
    drive_service, drive_mode = get_drive_service()
    settings = load_app_settings()

    mime_type = uploaded_file.type or mimetypes.guess_type(uploaded_file.name)[0] or "application/octet-stream"
    file_bytes = io.BytesIO(uploaded_file.getvalue())
    media = MediaIoBaseUpload(file_bytes, mimetype=mime_type, resumable=False)

    file_metadata = {
        "name": f"{record_id}-{uploaded_file.name}",
        "parents": [settings["drive_folder_id"]],
    }

    created_file = (
        drive_service.files()
        .create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink, webContentLink",
            supportsAllDrives=True,
        )
        .execute()
    )

    return {
        "arquivo_nome": uploaded_file.name,
        "arquivo_mime_type": mime_type,
        "arquivo_drive_id": created_file["id"],
        "arquivo_drive_link": created_file.get("webViewLink") or created_file.get("webContentLink", ""),
        "arquivo_drive_modo": drive_mode,
    }


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


def format_integration_error(error: Exception) -> str:
    error_text = str(error)

    if "Conecte seu Google Drive no painel lateral" in error_text:
        return error_text

    if "google_drive_oauth_client.json" in error_text:
        return (
            "Falta configurar o cliente OAuth do Google Drive. "
            "Baixe um OAuth Client ID do tipo Desktop App no Google Cloud e salve em "
            ".streamlit/google_drive_oauth_client.json."
        )

    if isinstance(error, HttpError):
        status_code = getattr(error.resp, "status", None)

        if "storageQuotaExceeded" in error_text or "Service Accounts do not have storage quota" in error_text:
            return (
                "A conta de servico ja consegue acessar a pasta, mas nao pode enviar arquivos para uma pasta "
                "do Meu Drive. Contas de servico nao tem cota de armazenamento no Google Drive. "
                "Para upload no seu Drive pessoal, configure o arquivo "
                ".streamlit/google_drive_oauth_client.json e conecte sua conta no painel lateral."
            )

        if status_code == 404 and "notFound" in error_text:
            return (
                "A pasta do Google Drive nao foi encontrada para a conta autenticada. "
                "Confira o ID da pasta e compartilhe a pasta com o email da conta de servico."
            )

        if status_code == 403:
            return (
                "O Google recusou a operacao por permissao ou limite. "
                "Verifique se as APIs do Drive e Sheets estao ativas e se a planilha e a pasta foram "
                "compartilhadas com a conta de servico."
            )

    if isinstance(error, OSError) and getattr(error, "winerror", None) == 10053:
        return (
            "A conexao com o Google foi interrompida no proprio computador (WinError 10053). "
            "Tente novamente. Se persistir, antivirus, firewall, proxy ou inspecao SSL podem estar "
            "interferindo na conexao HTTPS."
        )

    if "WinError 10053" in str(error):
        return (
            "A conexao com o Google foi interrompida no proprio computador (WinError 10053). "
            "Tente novamente. Se persistir, antivirus, firewall, proxy ou inspecao SSL podem estar "
            "interferindo na conexao HTTPS."
        )

    return str(error)


def show_configuration_help(error_message: str) -> None:
    st.error(error_message)
    st.info(
        f"Preencha o arquivo {LOCAL_SECRETS_PATH} com as credenciais da conta de servico, "
        "o ID da planilha e o ID da pasta do Google Drive."
    )
    st.caption(f"Modelo disponivel em: {EXAMPLE_SECRETS_PATH}")
    st.caption(
        "Para enviar imagens ao Meu Drive com a sua conta Google, salve tambem o cliente OAuth em "
        f"{GOOGLE_DRIVE_OAUTH_CLIENT_PATH}."
    )


def main():
    st.set_page_config(page_title="Cadastro com Google Sheets e Drive", layout="wide")
    st.title("Cadastro com Streamlit + Google Sheets + Google Drive")
    st.caption("Insira dados, processe o conteudo, consulte os registros e envie imagens diretamente para o Drive.")

    with st.sidebar:
        st.subheader("Como funciona")
        st.write("1. Preencha o formulario.")
        st.write("2. O app processa os dados.")
        st.write("3. O registro vai para o Google Sheets.")
        st.write("4. A imagem vai para o Google Drive.")

        st.divider()
        st.subheader("Google Drive")
        oauth_client_configured = load_drive_oauth_client_config() is not None
        user_drive_credentials = load_drive_user_credentials()

        if oauth_client_configured and user_drive_credentials:
            connected_account = user_drive_credentials.account or "sua conta Google"
            st.success(f"Conectado via OAuth: {connected_account}")
            if st.button("Desconectar Google Drive"):
                disconnect_drive_oauth()
                st.rerun()
        elif oauth_client_configured:
            st.info("Cliente OAuth encontrado. Conecte seu Google Drive para enviar imagens ao Meu Drive.")
            if st.button("Conectar meu Google Drive"):
                try:
                    with st.spinner("Abrindo o navegador para autorizar o Google Drive..."):
                        start_drive_oauth_flow()
                    st.success("Google Drive conectado com sucesso.")
                    st.rerun()
                except Exception as error:
                    st.error(format_integration_error(error))
        else:
            st.caption("Opcional para Meu Drive")
            st.write(
                "Se quiser enviar imagens para o seu Google Drive pessoal, salve o JSON de um "
                "OAuth Client do tipo Desktop App em "
                f"`{GOOGLE_DRIVE_OAUTH_CLIENT_PATH}`."
            )
            st.caption(f"Modelo: {GOOGLE_DRIVE_OAUTH_CLIENT_EXAMPLE_PATH}")

    try:
        get_sheets_client_and_settings()
    except Exception as error:
        show_configuration_help(str(error))
        st.stop()

    col_form, col_table = st.columns([1, 1.25], gap="large")

    with col_form:
        st.subheader("Novo registro")
        with st.form("registro_form", clear_on_submit=True):
            nome = st.text_input("Nome")
            email = st.text_input("Email")
            categoria = st.selectbox("Categoria", ["Cliente", "Fornecedor", "Parceiro", "Interno"])
            valor = st.text_input("Valor", placeholder="Ex.: 1500,75")
            status_choice = st.selectbox(
                "Prioridade",
                ["Automatica", "Normal", "Prioritario"],
                help="Automatica define a prioridade com base no valor informado.",
            )
            descricao = st.text_area("Descricao")
            uploaded_file = st.file_uploader("Imagem para enviar ao Google Drive", accept_multiple_files=False)

            submitted = st.form_submit_button("Salvar registro")

        if submitted:
            if not nome.strip() or not email.strip():
                st.warning("Preencha pelo menos Nome e Email.")
            else:
                try:
                    record = process_form_data(nome, email, categoria, valor, descricao, status_choice)

                    upload_data = {
                        "arquivo_nome": "",
                        "arquivo_mime_type": "",
                        "arquivo_drive_id": "",
                        "arquivo_drive_link": "",
                    }

                    if uploaded_file is not None:
                        upload_data = upload_file_to_drive(uploaded_file, record["record_id"])

                    record.update(upload_data)
                    save_record(record)
                    st.cache_data.clear()

                    st.success("Registro salvo com sucesso no Google Sheets e arquivo enviado ao Google Drive.")
                    st.json(record)
                except ValueError:
                    st.error("O campo Valor precisa ser numerico. Exemplo valido: 1500,75")
                except Exception as error:
                    st.error(f"Erro ao salvar o registro: {format_integration_error(error)}")

    with col_table:
        st.subheader("Registros cadastrados")
        if st.button("Atualizar lista"):
            st.cache_data.clear()

        @st.cache_data(ttl=30, show_spinner=False)
        def cached_records() -> pd.DataFrame:
            return load_records()

        try:
            df = cached_records()
            st.metric("Total de registros", len(df))

            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.download_button(
                    "Baixar CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name="registros_google_sheets.csv",
                    mime="text/csv",
                )
            else:
                st.info("Nenhum registro encontrado na planilha.")
        except Exception as error:
            st.error(f"Nao foi possivel carregar os registros: {format_integration_error(error)}")


if __name__ == "__main__":
    main()
