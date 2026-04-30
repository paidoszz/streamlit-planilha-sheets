# Acompanhamento da Linha de Pintura 3.0

Sistema web desenvolvido em Python e Streamlit para registrar inspecoes da linha de pintura, padronizar o preenchimento da ficha tecnica e salvar automaticamente os dados em uma planilha do Google Sheets.

O projeto foi pensado para uso operacional na area de qualidade: o inspetor preenche a ficha no navegador, o sistema valida os campos principais, grava o registro na aba configurada e permite consultar o historico das inspecoes ja salvas.

## Sumario

- [Funcionalidades](#funcionalidades)
- [Tecnologias utilizadas](#tecnologias-utilizadas)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Requisitos](#requisitos)
- [Instalacao local](#instalacao-local)
- [Configuracao do Google Sheets](#configuracao-do-google-sheets)
- [Configuracao do arquivo secrets.toml](#configuracao-do-arquivo-secretstoml)
- [Como executar](#como-executar)
- [Como usar o sistema](#como-usar-o-sistema)
- [Dados salvos na planilha](#dados-salvos-na-planilha)
- [Publicacao no Streamlit Community Cloud](#publicacao-no-streamlit-community-cloud)
- [Seguranca](#seguranca)
- [Solucao de problemas](#solucao-de-problemas)

## Funcionalidades

- Formulario digital para ficha de inspecao da linha de pintura.
- Registro de data, horario inicial, horario final, inspetor, pedido, O.P., item e descricao.
- Registro de dados da tinta: cor, fornecedor, lote, temperatura de secagem, temperatura de cura, velocidade e transportador.
- Marcacao de ocorrencias da barra: retoque, mistura de itens e retrabalho.
- Grade para registrar camadas de tinta por posicao: topo, meio e baixo; esquerda, centro e direita.
- Registro de avaliacao do inspetor e testes de qualidade, incluindo cura MEK, aderencia por grade e visual da barra.
- Salvamento automatico no Google Sheets.
- Criacao automatica da aba `inspecao_pintura_3_0` caso ela ainda nao exista.
- Sincronizacao dos cabecalhos da planilha conforme o formato esperado pelo sistema.
- Consulta dos registros salvos diretamente dentro do app.
- Botao para atualizar a lista de registros.
- Limpeza do formulario apos salvar uma inspecao com sucesso.
- Mensagens visuais para sucesso, campos obrigatorios e erros de configuracao.

## Tecnologias utilizadas

- [Python](https://www.python.org/)
- [Streamlit](https://streamlit.io/)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [gspread](https://docs.gspread.org/)
- [pandas](https://pandas.pydata.org/)
- [google-auth](https://google-auth.readthedocs.io/)

## Estrutura do projeto

```text
.
|-- app_inspecao_pintura.py        # Aplicacao principal da ficha de inspecao
|-- app.py                         # App antigo de cadastro com Sheets e Drive
|-- requirements.txt               # Dependencias Python
|-- README.md                      # Documentacao do projeto
|-- .gitignore                     # Arquivos ignorados pelo Git
|-- .streamlit/
|   |-- config.toml                # Tema visual do Streamlit
|   |-- secrets.toml.example       # Modelo de credenciais e configuracoes
|   `-- google_drive_oauth_client.example.json
`-- .github/
    `-- agents/
```

> Para a ficha atual de inspecao de pintura, use sempre o arquivo `app_inspecao_pintura.py`.

## Requisitos

Antes de executar o projeto, tenha instalado:

- Python 3.10 ou superior.
- Git.
- Conta Google com acesso ao Google Cloud.
- Uma planilha do Google Sheets.
- Google Sheets API ativada no projeto do Google Cloud.
- Uma conta de servico com permissao de acesso a planilha.

## Instalacao local

Clone o repositorio:

```powershell
git clone https://github.com/paidoszz/streamlit-planilha-sheets.git
cd streamlit-planilha-sheets
```

Crie um ambiente virtual:

```powershell
python -m venv .venv
```

Ative o ambiente virtual no Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Instale as dependencias:

```powershell
pip install -r requirements.txt
```

Se estiver usando macOS ou Linux, os comandos equivalentes sao:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuracao do Google Sheets

O sistema usa uma conta de servico do Google Cloud para gravar os registros na planilha.

### 1. Criar ou escolher uma planilha

Crie uma planilha no Google Sheets ou use uma planilha existente.

Copie o ID da planilha. Ele fica na URL, entre `/d/` e `/edit`.

Exemplo:

```text
https://docs.google.com/spreadsheets/d/ID_DA_PLANILHA/edit
```

### 2. Ativar a Google Sheets API

No Google Cloud:

1. Acesse o projeto desejado.
2. Abra o menu de APIs e servicos.
3. Ative a `Google Sheets API`.

### 3. Criar uma conta de servico

No Google Cloud:

1. Acesse `IAM e administrador`.
2. Abra `Contas de servico`.
3. Crie uma nova conta de servico.
4. Gere uma chave no formato JSON.
5. Baixe o arquivo JSON.

### 4. Compartilhar a planilha

Abra a planilha no Google Sheets e compartilhe com o e-mail da conta de servico.

Esse e-mail aparece no JSON da chave, no campo `client_email`.

Exemplo:

```text
minha-conta@meu-projeto.iam.gserviceaccount.com
```

Conceda permissao de editor para que o sistema consiga criar a aba e salvar os registros.

## Configuracao do arquivo secrets.toml

Crie o arquivo local de configuracao copiando o exemplo:

```powershell
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
```

No macOS ou Linux:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Abra `.streamlit/secrets.toml` e preencha com os dados reais da sua conta de servico e da planilha.

Modelo:

```toml
[gcp_service_account]
type = "service_account"
project_id = "seu-project-id"
private_key_id = "sua-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nSUA_CHAVE_AQUI\n-----END PRIVATE KEY-----\n"
client_email = "sua-conta@seu-projeto.iam.gserviceaccount.com"
client_id = "seu-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/sua-conta%40seu-projeto.iam.gserviceaccount.com"
universe_domain = "googleapis.com"

google_sheets_spreadsheet_id = "ID_DA_SUA_PLANILHA"
google_sheets_worksheet_name_inspecao = "inspecao_pintura_3_0"
```

Tambem e possivel personalizar os dados exibidos no cabecalho da ficha:

```toml
inspecao_pintura_document_code = "FI - Pintura"
inspecao_pintura_sector = "Qualidade Industrial"
inspecao_pintura_revision = "2"
inspecao_pintura_author = "Nome do autor"
inspecao_pintura_approved_by = "Nome do aprovador"
```

A data de atualizacao do cabecalho e gerada automaticamente com a data atual.

## Como executar

Com o ambiente virtual ativo, execute:

```powershell
streamlit run app_inspecao_pintura.py
```

Ou:

```powershell
.\.venv\Scripts\python -m streamlit run app_inspecao_pintura.py
```

Depois de iniciar, o Streamlit mostrara um endereco local parecido com este:

```text
http://localhost:8501
```

Abra esse endereco no navegador.

## Como usar o sistema

### 1. Abrir a ficha

Ao acessar o app, abra a aba `Ficha de inspecao`.

O sistema carrega o cabecalho da ficha, confere a conexao com o Google Sheets e prepara a aba da planilha.

### 2. Preencher identificacao

Preencha os dados de rastreabilidade:

- Data.
- Inspetor.
- Pedido.
- O.P.
- Item.
- Descricao.
- Hora de inicio.
- Hora final.

O campo `Inspetor` e obrigatorio.

### 3. Preencher dados da tinta

Informe:

- Cor da tinta.
- Fornecedor.
- Lote.
- Temperatura de secagem.
- Temperatura de cura.
- Velocidade.
- Transportador.

### 4. Registrar dados da barra

Marque as ocorrencias:

- Retoque.
- Mistura de itens.
- Retrabalho.

As opcoes exibidas sao `Sim`, `Nao` e `N/A`.

Na planilha, esses valores sao gravados como:

- `Com`
- `Sem`
- `NA`

### 5. Registrar camadas de tinta

Preencha a grade de camadas por posicao:

- Topo esquerda, centro e direita.
- Meio esquerda, centro e direita.
- Baixo esquerda, centro e direita.

### 6. Registrar testes e avaliacao

Informe os resultados:

- Avaliacao do inspetor.
- Teste de cura MEK.
- Teste de aderencia por grade.
- Teste visual da barra.

As opcoes sao `OK`, `Nao OK` e `N/A`.

Na planilha, os valores sao gravados como:

- `OK`
- `N OK`
- `NA`

### 7. Salvar a inspecao

Clique em `Salvar inspecao`.

Quando o salvamento for concluido:

- O registro e enviado para o Google Sheets.
- O sistema mostra o ID do registro salvo.
- O formulario volta para o estado inicial.
- A lista de registros fica pronta para atualizacao.

### 8. Consultar registros salvos

Abra a aba `Registros salvos`.

Nessa tela e possivel:

- Ver o total de inspecoes.
- Ver o total de colunas sincronizadas.
- Consultar os registros gravados na planilha.
- Clicar em `Atualizar lista` para recarregar os dados.

## Dados salvos na planilha

O sistema cria ou atualiza a primeira linha da aba configurada com os seguintes cabecalhos:

```text
record_id
created_at
tipo_inspecao
data_inspecao
hora_inicio
hora_final
inspetor
cor_tinta
fornecedor
lote
temperatura_secagem
temperatura_cura
velocidade
transportador
barra_retoque_liq
barra_mistura_itens
barra_retrabalho
camada_topo_esquerda
camada_topo_centro
camada_topo_direita
camada_meio_esquerda
camada_meio_centro
camada_meio_direita
camada_baixo_esquerda
camada_baixo_centro
camada_baixo_direita
avaliacao_inspetor
teste_cura_mek
teste_aderencia_grade
teste_visual_barra
item
descricao
pedido
op
observacoes
```

Cada inspecao gera uma nova linha.

Alguns detalhes importantes:

- `record_id` e gerado automaticamente no formato `insp-pintura-AAAAMMDDHHMMSS`.
- `created_at` e salvo em UTC no formato ISO.
- `tipo_inspecao` e preenchido como `Inspecao diaria ou homologacao`.
- `data_inspecao` e salva no formato `AAAA-MM-DD`.
- Horarios sao salvos no formato `HH:MM`.
- Temperaturas aceitam virgula ou ponto; o sistema normaliza para ponto.
- Campos de texto sao normalizados para reduzir variacoes de espaco e acentuacao nos dados gravados.

## Publicacao no Streamlit Community Cloud

Para publicar o projeto no Streamlit Community Cloud:

1. Suba o projeto para o GitHub.
2. Acesse o Streamlit Community Cloud.
3. Crie um novo app apontando para este repositorio.
4. Escolha o arquivo principal:

```text
app_inspecao_pintura.py
```

5. Configure os secrets do app no painel do Streamlit Cloud.

Use o mesmo conteudo do arquivo `.streamlit/secrets.toml`, sem enviar esse arquivo para o GitHub.

## Seguranca

Arquivos com credenciais reais nao devem ser publicados.

Este projeto ja ignora os principais arquivos sensiveis:

```text
.streamlit/secrets.toml
.streamlit/google_drive_oauth_client.json
.streamlit/google_drive_user_token.json
.venv/
__pycache__/
test-results/
```

Boas praticas:

- Nunca envie `secrets.toml` para o GitHub.
- Nunca publique chaves privadas da conta de servico.
- Compartilhe a planilha apenas com contas necessarias.
- Revogue e gere uma nova chave se alguma credencial for exposta.
- Use o arquivo `.streamlit/secrets.toml.example` apenas como modelo.

## Solucao de problemas

### Erro: credenciais nao encontradas

Confira se o arquivo `.streamlit/secrets.toml` existe e se a secao `[gcp_service_account]` esta preenchida corretamente.

### Erro: informe google_sheets_spreadsheet_id

Preencha a chave:

```toml
google_sheets_spreadsheet_id = "ID_DA_SUA_PLANILHA"
```

### Erro ao abrir a planilha

Verifique:

- Se o ID da planilha esta correto.
- Se a planilha foi compartilhada com o `client_email` da conta de servico.
- Se a conta de servico tem permissao de editor.
- Se a Google Sheets API esta ativa.

### A aba nao aparece na planilha

O sistema tenta criar automaticamente a aba configurada. Se isso nao acontecer, confirme se a conta de servico tem permissao de edicao na planilha.

### Registros nao aparecem na aba `Registros salvos`

Clique em `Atualizar lista`. A consulta usa cache curto para deixar a interface mais rapida.

### PowerShell bloqueou a ativacao do ambiente virtual

Execute o PowerShell como usuario normal e rode:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Depois tente ativar novamente:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Comandos Git mais usados

Para salvar alteracoes no GitHub:

```powershell
git status
git add .
git commit -m "Atualiza documentacao"
git push
```

## Observacoes sobre o app antigo

O arquivo `app.py` foi mantido no repositorio como uma versao anterior de cadastro com Google Sheets e upload opcional para Google Drive.

Para o sistema atual de acompanhamento da linha de pintura, o arquivo principal e:

```text
app_inspecao_pintura.py
```

## Autor

Desenvolvido por Marcelo Paidosz Junior.
