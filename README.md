# Acompanhamento da Linha de Pintura 3.0

Aplicacao em Streamlit para preencher uma ficha de inspecao da linha de pintura e salvar os registros em uma aba do Google Sheets.

## O que a aplicacao faz

- Exibe a ficha de inspecao em formato web.
- Permite preencher identificacao, dados da tinta, barra, camadas de tinta e testes.
- Salva cada inspecao em uma planilha do Google Sheets.
- Cria automaticamente a aba `inspecao_pintura_3_0`, se ela ainda nao existir.
- Mantem a ordem correta das colunas da planilha.
- Limpa o formulario depois que a inspecao e salva.
- Permite consultar os registros ja salvos na aba `Registros salvos`.

## Arquivos principais

- `app_inspecao_pintura.py`: aplicacao principal da ficha de inspecao.
- `requirements.txt`: dependencias Python necessarias para rodar o projeto.
- `.streamlit/secrets.toml`: configuracoes locais e credenciais. Este arquivo nao deve ser enviado para repositorios publicos.
- `.streamlit/secrets.toml.example`: modelo de configuracao para criar o `secrets.toml`.
- `app.py`: app anterior do projeto. Use `app_inspecao_pintura.py` para a ficha de pintura atual.

## Como configurar

1. Crie e ative um ambiente virtual, se ainda nao existir:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

3. Crie o arquivo `.streamlit/secrets.toml` usando `.streamlit/secrets.toml.example` como base.

4. No Google Cloud, ative a `Google Sheets API`.

5. Crie uma conta de servico no Google Cloud e copie o JSON da credencial para a secao `[gcp_service_account]` do `secrets.toml`.

6. Compartilhe a planilha do Google Sheets com o `client_email` da conta de servico.

7. Informe o ID da planilha no `secrets.toml`:

```toml
google_sheets_spreadsheet_id = "ID_DA_SUA_PLANILHA"
google_sheets_worksheet_name_inspecao = "inspecao_pintura_3_0"
```

O ID da planilha fica na URL do Google Sheets, entre `/d/` e `/edit`.

## Como executar

Use este comando na raiz do projeto:

```powershell
.\.venv\Scripts\python -m streamlit run app_inspecao_pintura.py
```

Depois, acesse o link local mostrado pelo Streamlit, normalmente:

```text
http://localhost:8501
```

## Como usar

1. Abra a aba `Ficha de inspecao`.
2. Preencha os campos da ficha.
3. Selecione as opcoes de barra e testes.
4. Preencha as camadas de tinta.
5. Clique em `Salvar inspecao`.
6. Depois do salvamento, o formulario volta para o estado inicial.
7. Para consultar o historico, abra a aba `Registros salvos`.

## Configuracoes opcionais

Estes dados aparecem no cabecalho da ficha e podem ser alterados no `secrets.toml`:

```toml
inspecao_pintura_document_code = "FI - Pintura"
inspecao_pintura_sector = "Qualidade Industrial"
inspecao_pintura_revision = "2"
inspecao_pintura_author = "Nome do autor"
inspecao_pintura_approved_by = "Nome do aprovador"
```

A data de atualizacao e calculada automaticamente com a data atual.

## Observacoes

- O app atual de inspecao usa apenas Google Sheets.
- A Google Drive API e os arquivos OAuth sao usados pelo app antigo `app.py`, nao pela ficha atual de pintura.
- Se a planilha nao abrir, confira se o `client_email` da conta de servico tem acesso a ela.
- Se a aba configurada nao existir, o app tenta cria-la automaticamente.
