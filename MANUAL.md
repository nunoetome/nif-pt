# Manual de Instruções — nif-pt v0.3.0

> Ferramenta Python para consulta de NIFs portugueses via [nif.pt](http://www.nif.pt) (`?json=1`) com validação Mod-11 e persistência SQLite / Azure SQL.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-v0.2.0--beta-orange.svg)](CHANGELOG.md)

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Arquitetura e Pipeline](#2-arquitetura-e-pipeline)
3. [Pré-requisitos](#3-pré-requisitos)
4. [Instalação](#4-instalação)
5. [Configuração](#5-configuração)
6. [Utilização — Modos de Operação](#6-utilização--modos-de-operação)
7. [Esquemas de Base de Dados](#7-esquemas-de-base-de-dados)
8. [Referência CLI](#8-referência-cli)
9. [Referência de Dados e JSON](#9-referência-de-dados-e-json)
10. [Códigos de Erro e Saída](#10-códigos-de-erro-e-saída)
11. [Logging](#11-logging)
12. [Exemplos Práticos (PowerShell & Bash)](#12-exemplos-práticos-powershell--bash)
13. [Resolução de Problemas (Troubleshooting)](#13-resolução-de-problemas-troubleshooting)
14. [FAQ](#14-faq)
15. [Anexos](#15-anexos)

---

## 1. Visão Geral

### 1.1 Objetivo e âmbito

O `nif-pt` consulta a base pública do portal `nif.pt` e guarda o resultado localmente (SQLite) e/ou remotamente (Azure SQL). Destina-se a **pessoas coletivas** com registo público; NIFs de pessoas singulares ou recentes podem devolver `No records found` sem que isso indique erro de validação.

### 1.2 Funcionalidades

| ID | Funcionalidade | Estado |
|----|----------------|--------|
| RF-01 | Validar formato do NIF (9 dígitos, Mod-11) | ✅ `consulta_nif.py:26` |
| RF-02 | Consultar API `nif.pt` (`?json=1&q=<NIF>&key=<KEY>`) | ✅ `consulta_nif.py:38` |
| RF-03 | Devolver JSON normalizado (`valido`, `fonte`, `erro`, `dados`, `creditos`) | ✅ |
| RF-04 | Guardar JSON bruto em SQLite (`data/nif_pt.db`, WAL) | ✅ `importar_nif_sqlite.py:37` |
| RF-05 | Normalizar 36 colunas e inserir em Azure SQL `stg_nunotome.nif_pt_stg` | ✅ `importar_nif.py:83` |
| RF-06 | Pipeline `stdin`/`stdout` com `exit code` | ✅ |
| RF-07 | Logging estruturado (template) | 🚧 `Logging/logging_template.py:1` não integrado |

### 1.3 Requisitos não-funcionais

* **Performance:** `timeout` configurável, `PRAGMA journal_mode=WAL` no SQLite.
* **Segurança:** chave `NIF-PT-KEY` e credenciais Azure apenas em `config/.env` (ignorado em `.gitignore:7`).
* **Portabilidade:** `pathlib`, `pyodbc` + `ODBC Driver 18 for SQL Server`.

### 1.4 Público-alvo e limitações da fonte

Operações, compliance e data engineering que necessitem enriquecer NIFs. A fonte `nif.pt` é agregadora — pode estar desatualizada, incompleta ou com rate-limit (`creditos.left`).

### 1.5 Histórico de versões

| Versão | Data | Destaque |
|--------|------|----------|
| `v.0.1.0-alpha` | 2026-06-26 | Fundação: `consulta_nif.py` + `importar_nif.py` + `importar_nif_sqlite.py` + DDL Azure |
| `v0.2.0-beta` | 2026-06-26 | Refactor: config centralizada, SQLite JSON bruto, `MANUAL.md` 310L, PK `id IDENTITY` |
| `v0.2.1` (Unreleased) | 2026-09-10 | Fix `requirements.txt` (`yaml`→`pyyaml`, falta `python-dotenv`/`pyodbc`), `README` + `docs/` |
| `v0.3.0-docs` (este manual) | 2026-09-10 | Documentação completa |

Ver [CHANGELOG.md](CHANGELOG.md) para detalhe.

---

## 2. Arquitetura e Pipeline

### 2.1 Diagrama de pipeline

```mermaid
graph LR
    U[Utilizador<br/>NIF 9 dígitos] --> C[consulta_nif.py<br/>validar_nif + requests]
    C -->|stdout JSON<br/>ensure_ascii=False| S[importar_nif_sqlite.py<br/>JSON bruto]
    C -->|stdout JSON| A[importar_nif.py<br/>36 cols normalizadas]
    S --> DB1[(data/nif_pt.db<br/>id, nif, dados, data_consulta<br/>PRAGMA WAL)]
    A --> DB2[(Azure SQL<br/>stg_nunotome.nif_pt_stg<br/>40 cols)]
    DB2 -. MERGE futuro .-> DB3[(stg_nunotome.nif_pt<br/>37 cols PK nif)]
    CFG[config.yaml + .env<br/>get_config()] -.-> C & S & A
```

Fonte única em [docs/architecture/diagrams.md](docs/architecture/diagrams.md).

### 2.2 Pipeline `stdin`/`stdout`

```
consulta_nif.py  ──JSON──>  importar_nif_sqlite.py  (SQLite local)
                ──JSON──>  importar_nif.py         (Azure SQL)
```

* `consulta_nif.py` escreve **apenas JSON** em `stdout` (`consulta_nif.py:103` `json.dumps(..., indent=2, ensure_ascii=False)`); mensagens humanas vão para `stderr`.
* Importadores leem **todo o `stdin`** (`sys.stdin.read()` em `importar_nif_sqlite.py:47` e `importar_nif.py:157`); falham com `exit 1` se `stdin` vazio ou `resultado.erro` presente.
* `exit 0` sucesso, `exit 1` erro — permite `if ($?)` / `if [ $? -eq 0 ]`.

### 2.3 Centralização de configuração

`config/config.py:17` `get_config(script_name)` funde:
1. `default` (`config/config.yaml:1` — `retry_count`, `timeout`, `tempo_de_espera`)
2. Bloco específico (`consulta_nif` / `importar_nif_sqlite` / `importar_nif`)
3. Segredos de `config/.env` (`NIF-PT-KEY`, `AZURE_USER`, `AZURE_PALAVRA_CHAVE`, `API_TOKEN`)

```python
cfg = get_config("consulta_nif")
API_BASE = cfg.get("api_base", "http://www.nif.pt")
API_KEY  = cfg.get("NIF_PT_KEY")  # vem de os.getenv("NIF-PT-KEY")
TIMEOUT  = cfg.get("timeout", 1000)
```

### 2.4 Decisões técnicas (ADRs)

| ADR | Decisão | Justificação |
|-----|---------|--------------|
| ADR-001 | SQLite guarda **JSON bruto** (`dados TEXT`) vs Azure normaliza 36 cols | SQLite schemaless resiste a mudanças da API; Azure normalizado permite `SELECT` analítico. Ver [docs/architecture/architecture.md](docs/architecture/architecture.md). |
| ADR-002 | `PRAGMA journal_mode=WAL` | Resolve `database is locked` na maioria dos casos. |
| ADR-003 | `ODBC Driver 18` com `Encrypt=yes` | Exigido pelo Azure SQL atual. |

### 2.5 Estado atual e roadmap

* **Funcional:** `consulta_nif.py`, `importar_nif_sqlite.py`, `importar_nif.py`, `config/`, `sql/01_criar_tabelas.sql`.
* **Stub / reservado:** `main.py:1` (7L, só `print`), `api/__init__.py`, `models/__init__.py`, `scrapers/__init__.py`, `utils/__init__.py` (0 bytes), `Logging/logging_template.py:1` (579L, não importado).
* **Órfão:** `suport/favicon.ico` (1150 bytes, não referenciado).
* **Roadmap `v0.3`:** `main.py` → `cli.py` com `argparse` (`--nif`, `--to {sqlite,azure,both}`), integração logging, `api/` FastAPI, `models/` Pydantic.

---

## 3. Pré-requisitos

### 3.1 Matriz de dependências

| Dependência | Versão | Instalação | Obrigatória |
|-------------|--------|------------|-------------|
| Python | `>=3.11` | https://www.python.org/downloads/ | ✅ |
| `requests` | `>=2.31.0` | `pip install -r requirements.txt` | ✅ |
| `pyyaml` | `>=6.0.1` | idem | ✅ |
| `python-dotenv` | `>=1.0.0` | idem | ✅ |
| `pyodbc` | `>=5.0.0` | idem | Só para `importar_nif.py` |
| `ODBC Driver 18 for SQL Server` | 18.x | https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server | Só para Azure SQL |
| Chave `nif.pt` | — | http://www.nif.pt/contactos/api/ | ✅ |

> **Nota:** `requirements.txt` esteve quebrado até `v0.2.0-beta` (`yaml` em vez de `pyyaml`, falta `python-dotenv`/`pyodbc`). Corrigido em `v0.2.1` (`hotfix/erro_nos_requirements`).

### 3.2 Chave `NIF-PT-KEY`

1. Solicitar em http://www.nif.pt/contactos/api/ (resposta por email, 1-2 dias).
2. Copiar a chave para `config/.env` como `NIF-PT-KEY=xxxxx` (**com hífen**, `config/config.py:38`).

### 3.3 Azure SQL (opcional)

* Servidor `kiwa-pt-operations.database.windows.net`, BD `kiwa-pt-operations`, schema `stg_nunotome` (`config/config.yaml:23`).
* O IP local deve estar em *Firewall rules* no Portal Azure.
* Verificar driver: `odbcinst -q -d` (Linux) ou `Get-OdbcDriver` (PowerShell).

---

## 4. Instalação

### 4.1 Clonar

```bash
git clone https://github.com/nunoetome/nif-pt.git
cd nif-pt
git checkout prod   # estável; dev para desenvolvimento
```

### 4.2 Criar `venv`

**Git Bash (MINGW64) — o teu caso:**
```bash
python -m venv venv
source venv/Scripts/activate
# verificar:
which python  # .../nif-pt/venv/Scripts/python.exe
```

**PowerShell:**
```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
# se bloquear: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**cmd.exe:**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

> **Erro comum:** `source venv/bin/activate` é Linux; em Windows é `venv/Scripts/activate`. `Activate.ps1` só funciona em PowerShell.

### 4.3 Instalar dependências

```bash
pip install -r requirements.txt
# requirements.txt contém:
# requests>=2.31.0
# pyyaml>=6.0.1
# python-dotenv>=1.0.0
# pyodbc>=5.0.0
```

### 4.4 Verificar

```bash
python -c "from config.config import get_config; print(get_config('consulta_nif').keys())"
python consulta_nif.py 509442013  # requer NIF-PT-KEY
```

---

## 5. Configuração

### 5.1 `config/config.yaml` (27L)

```yaml
default:
  retry_count: 0        # 🚧 reservado, não implementado
  timeout: 1000         # ⚠️ em segundos para requests (ver 5.4)
  tempo_de_espera: 60   # 🚧 reservado

consulta_nif:
  api_base: "http://www.nif.pt"

importar_nif_sqlite:
  db_path: "data/nif_pt.db"
  tabela: "nif_pt"

importar_nif:
  sql_server: "kiwa-pt-operations.database.windows.net"
  sql_database: "kiwa-pt-operations"
  sql_schema: "stg_nunotome"
  sql_driver: "ODBC Driver 18 for SQL Server"
  tabela_staging: "nif_pt_stg"
```

| Chave | Onde usada | Descrição |
|-------|------------|-----------|
| `default.timeout` | `consulta_nif.py:23` `requests.get(timeout=TIMEOUT)` | Timeout HTTP em **segundos** |
| `default.retry_count` | — | Reservado |
| `consulta_nif.api_base` | `consulta_nif.py:21` | Base URL da API |
| `importar_nif_sqlite.db_path` | `importar_nif_sqlite.py:24` | Caminho SQLite (relativo à raiz) |
| `importar_nif.sql_*` | `importar_nif.py:25` | Conexão Azure SQL |

### 5.2 `config/.env` (+ `.env.example`)

```env
# NIF-PT — obter em http://www.nif.pt/contactos/api/
NIF-PT-KEY=coloque_aqui

# Azure SQL — portal.azure.com → SQL → Connection strings
AZURE_USER=seu_user
AZURE_PALAVRA_CHAVE=sua_password

# Opcional futuro
# API_TOKEN=se_tiver_api_propria
```

* Criar com `cp config/.env.example config/.env` e editar.
* **Nunca** commitar `.env` (`.gitignore:7`).
* Nome **exato** `NIF-PT-KEY` com hífen — `NIF_PT_KEY` não é lido (`config.py:38` `os.getenv("NIF-PT-KEY")`).

### 5.3 Precedência

`default` < bloco do script < `.env`. `config.py:29` faz `config.update(script_config)` (shallow merge).

### 5.4 Problemas conhecidos de configuração

| Chave | Problema | Recomendação |
|-------|----------|--------------|
| `timeout:1000` | 1000s ≈ 16min; intenção provável era 1000ms = 1s | Mudar para `timeout: 10` ou `15` e documentar unidade **segundos** |
| `retry_count:0` / `tempo_de_espera:60` | Lidos mas nunca usados (`consulta_nif.py` não faz retry) | Implementar `for attempt in range(retry_count+1): try: requests... except Timeout: sleep(tempo_de_espera)` ou marcar como 🚧 |

---

## 6. Utilização — Modos de Operação

### 6.1 Modo 1 — Só consulta (sem gravar)

```bash
python consulta_nif.py 509442013
```

* Valida formato (`consulta_nif.py:98` `nif.isdigit()`) e dígito de controlo (`validar_nif():26`).
* Se formato básico inválido → `{"erro":"NIF deve conter apenas dígitos"}` + `exit 1` sem request.
* Se `NIF-PT-KEY` em falta → `{"erro":"NIF-PT-KEY não encontrada no .env"}` + `exit 1` (`consulta_nif.py:40`).
* Caso contrário faz `GET http://www.nif.pt/?json=1&q=<NIF>&key=<KEY>` e imprime JSON em `stdout`.

### 6.2 Modo 2 — SQLite local

```bash
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
# stderr: NIF 509442013 guardado em nif_pt.
```

* `importar_nif_sqlite.py:37` `get_db()` cria `data/nif_pt.db` e tabela se não existir (`CREATE TABLE IF NOT EXISTS nif_pt:27`), ativa `PRAGMA journal_mode=WAL`.
* Insere `(nif, dados=JSON completo, data_consulta=datetime.now())`.

### 6.3 Modo 3 — Azure SQL

```bash
python consulta_nif.py 509442013 | python importar_nif.py
# stderr: NIF 509442013 inserido em stg_nunotome.nif_pt_stg.
```

* Pré-requisitos: ODBC 18, `AZURE_USER`/`AZURE_PALAVRA_CHAVE` em `.env`, tabela criada via `sql/01_criar_tabelas.sql`.
* `importar_nif.py:83` `mapear_registo()` normaliza 36 colunas; `INSERT` parametrizado (`?`) com `commit`/`rollback`.

### 6.4 Modo 4 — Ambos em simultâneo

**Bash (WSL/Git Bash):**
```bash
python consulta_nif.py 509442013 | tee >(python importar_nif_sqlite.py) | python importar_nif.py
```

**PowerShell (correção — `tee` com `>( )` não existe):**
```powershell
$json = python consulta_nif.py 509442013
$json | python importar_nif_sqlite.py
$json | python importar_nif.py
# ou com ficheiro temporário:
python consulta_nif.py 509442013 | Tee-Object -FilePath temp.json | python importar_nif.py
python importar_nif_sqlite.py < temp.json
```

### 6.5 Modo 5 — Ficheiro intermédio

```bash
python consulta_nif.py 509442013 > resultado.json
python importar_nif_sqlite.py < resultado.json
python importar_nif.py < resultado.json
```

### 6.6 Batch (múltiplos NIFs)

**PowerShell:**
```powershell
Get-Content nifs.txt | ForEach-Object {
    python consulta_nif.py $_ | python importar_nif_sqlite.py
    Start-Sleep -Seconds 1  # respeitar rate-limit
}
```

**Bash:**
```bash
while read nif; do
    python consulta_nif.py "$nif" | python importar_nif_sqlite.py
    sleep 1
done < nifs.txt
```

---

## 7. Esquemas de Base de Dados

### 7.1 Visão comparativa

| Aspeto | SQLite (`nif_pt`) | Azure SQL (`nif_pt` / `nif_pt_stg`) |
|--------|-------------------|-------------------------------------|
| Ficheiro | `data/nif_pt.db` (ignorado) | `kiwa-pt-operations.stg_nunotome.*` |
| Estratégia | JSON bruto schemaless | 36 cols normalizadas |
| PK | `id INTEGER AUTOINCREMENT` | `nif BIGINT PK` (`nif_pt`) / `id BIGINT IDENTITY` (`nif_pt_stg`) |
| Histórico | Sim (sem unicidade `nif`) | `nif_pt` só último; `nif_pt_stg` com histórico + `processado` |
| DDL | `importar_nif_sqlite.py:27` inline | `sql/01_criar_tabelas.sql:21` |

### 7.2 SQLite — `nif_pt` (4 colunas)

```sql
CREATE TABLE IF NOT EXISTS nif_pt (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nif             INTEGER NOT NULL,
    dados           TEXT NOT NULL,          -- JSON completo do resultado
    data_consulta   TEXT NOT NULL DEFAULT (datetime('now'))
);
```

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | INTEGER PK | Auto-incremento WAL |
| `nif` | INTEGER | NIF consultado |
| `dados` | TEXT | `json.dumps(resultado, ensure_ascii=False)` |
| `data_consulta` | TEXT | `YYYY-MM-DD HH:MM:SS` (`datetime.now()`) |

### 7.3 Azure SQL — `stg_nunotome.nif_pt` (37 cols, PK `nif`)

```sql
CREATE TABLE stg_nunotome.nif_pt (
    nif                     BIGINT          NOT NULL,
    nif_valido_formato      BIT             NULL,
    data_consulta           DATETIME2       NOT NULL DEFAULT GETDATE(),
    consulta_origem         NVARCHAR(50)    NULL DEFAULT 'nif.pt',
    seo_url                 NVARCHAR(255)   NULL,
    title                   NVARCHAR(500)   NULL,
    alias                   NVARCHAR(500)   NULL,
    status                  NVARCHAR(50)    NULL,
    start_date              DATE            NULL,
    activity                NVARCHAR(MAX)   NULL,
    place_address           NVARCHAR(500)   NULL,
    place_pc4               NVARCHAR(10)    NULL,
    place_pc3               NVARCHAR(10)    NULL,
    place_city              NVARCHAR(100)   NULL,
    address                 NVARCHAR(500)   NULL,
    pc4                     NVARCHAR(10)    NULL,
    pc3                     NVARCHAR(10)    NULL,
    city                    NVARCHAR(100)   NULL,
    geo_region              NVARCHAR(100)   NULL,
    geo_county              NVARCHAR(100)   NULL,
    geo_parish              NVARCHAR(100)   NULL,
    contacts_email          NVARCHAR(255)   NULL,
    contacts_phone          NVARCHAR(50)    NULL,
    contacts_website        NVARCHAR(255)   NULL,
    contacts_fax            NVARCHAR(50)    NULL,
    structure_nature        NVARCHAR(50)    NULL,
    structure_capital       DECIMAL(18,2)   NULL,
    structure_capital_currency NVARCHAR(10) NULL,
    cae                     NVARCHAR(500)   NULL,
    racius                  NVARCHAR(500)   NULL,
    portugalio              NVARCHAR(500)   NULL,
    creditos_used           NVARCHAR(50)    NULL,
    creditos_left_month     INT             NULL,
    creditos_left_day       INT             NULL,
    creditos_left_hour      INT             NULL,
    creditos_left_minute    INT             NULL,
    creditos_left_paid      INT             NULL,
    CONSTRAINT pk_nif_pt PRIMARY KEY CLUSTERED (nif)
);
```

### 7.4 Azure SQL — `stg_nunotome.nif_pt_stg` (40 cols, PK `id`)

Igual ao `nif_pt` + 3 colunas de controlo staging:

```sql
CREATE TABLE stg_nunotome.nif_pt_stg (
    id                      BIGINT          IDENTITY(1,1) NOT NULL,
    -- ... mesmos 37 cols do nif_pt ...
    data_staging            DATETIME2       NOT NULL DEFAULT GETDATE(),
    processado              BIT             NOT NULL DEFAULT 0,
    CONSTRAINT pk_nif_pt_stg PRIMARY KEY CLUSTERED (id)
);
```

Diferença: `nif_pt_stg` tem `id`, `data_staging`, `processado`; `nif_pt` não. `importar_nif.py:132` `colunas_tabela()` lista 36 cols (sem `id/data_consulta/data_staging/processado` que são `DEFAULT`).

### 7.5 Criação das tabelas

```bash
# SSMS / Azure Data Studio / sqlcmd
# Executar sql/01_criar_tabelas.sql — cria schema stg_nunotome se não existir
```

> **Atenção:** o DDL faz `IF OBJECT_ID(...) IS NOT NULL DROP TABLE` — **destrutivo**. Em produção usar `IF NOT EXISTS CREATE` ou migrations. Recomenda-se `CREATE INDEX ON nif_pt_stg(nif, processado) WHERE processado=0`.

### 7.6 Estratégia staging → prod

`importar_nif.py` insere sempre em `nif_pt_stg` (`importar_nif.py:9` docstring: “O tratamento e migração para `nif_pt` é feito posteriormente noutro processo”). Um `MERGE`/`procedure` futuro (`usp_merge_nif_pt`) deve fazer `INSERT/UPDATE` em `nif_pt` onde `processado=0`.

```sql
-- Exemplo futuro (não incluído no repo):
MERGE stg_nunotome.nif_pt AS target
USING (SELECT * FROM stg_nunotome.nif_pt_stg WHERE processado=0) AS source
ON target.nif = source.nif
WHEN MATCHED THEN UPDATE SET ...
WHEN NOT MATCHED THEN INSERT ...
```

Ver [docs/database/schema.md](docs/database/schema.md) para ER completo.

---

## 8. Referência CLI

| Comando | Argumentos | stdin | stdout | stderr | Exit |
|---------|------------|-------|--------|--------|------|
| `consulta_nif.py` | `<NIF>` (9 dígitos) | — | JSON | mensagens erro | `0` ok, `1` erro |
| `importar_nif_sqlite.py` | — | JSON | — | `NIF x guardado` | `0`/`1` |
| `importar_nif.py` | — | JSON | — | `NIF x inserido` | `0`/`1` |

### 8.1 `consulta_nif.py`

```
Uso: python consulta_nif.py <NIF>
Exemplo: python consulta_nif.py 509442013
```

* Valida `nif.isdigit()` (`consulta_nif.py:98`) antes de rede.
* Validação Mod-11 completa em `validar_nif():26` afeta campo `valido` mas **não bloqueia request** (ver §13.6).
* `TIMEOUT` de `config.yaml` (segundos) passado a `requests.get(timeout=TIMEOUT)`.

### 8.2 `importar_nif_sqlite.py` / `importar_nif.py`

```
Uso: python consulta_nif.py 509442013 | python importar_nif_sqlite.py
     python importar_nif_sqlite.py < ficheiro.json
```

* Ambos: `sys.stdin.read()` → `json.loads` → valida `resultado.erro` e `nif` → `INSERT`.
* `importar_nif.py:179` exige `AZURE_USER`/`AZURE_PALAVRA_CHAVE` em `.env`.

---

## 9. Referência de Dados e JSON

### 9.1 Exemplo JSON sucesso (resposta real `509442013`, 2026-09-10)

```json
{
  "nif": "509442013",
  "valido": true,
  "fonte": "nif.pt",
  "erro": null,
  "dados": {
    "nif": 509442013,
    "seo_url": "nexperience-lda",
    "title": "Nexperience, Unipessoal, Lda",
    "alias": "Nexperience",
    "status": "active",
    "start_date": "2010-05-18",
    "activity": "<p>Desenvolvimento de software...</p>",
    "address": "Rua de Santa Catarina, Nº 1232",
    "pc4": "4000",
    "pc3": "457",
    "city": "Porto",
    "place": {
      "address": "Rua de Santa Catarina, Nº 1232",
      "pc4": "4000", "pc3": "457", "city": "Porto"
    },
    "geo": {
      "region": "Porto", "county": "Porto", "parish": "Cedofeita"
    },
    "contacts": {
      "email": "info@nex.pt",
      "phone": "220 198 228",
      "website": "www.nex.pt",
      "fax": "224 905 459"
    },
    "structure": {
      "nature": "UNI", "capital": "248000.00", "capital_currency": "EUR"
    },
    "cae": ["62010", "63120", "62020", "46510"],
    "racius": "https://www.racius.com/nexperience-lda/",
    "portugalio": null
  },
  "nif_valido_formato": true,
  "creditos": {
    "used": "free",
    "left": []
  }
}
```

### 9.2 Exemplo JSON erro

```json
{
  "nif": "999999999",
  "valido": false,
  "fonte": "nif.pt",
  "erro": "No records found",
  "dados": {
    "result": "No records found",
    "nif_validation": false
  }
}
```

### 9.3 Mapeamento `mapear_registo()` → SQL

`importar_nif.py:83` desembrulha `dados.{place,geo,contacts,structure}` + `creditos`:

| Campo API | Coluna SQL | Parser |
|-----------|------------|--------|
| `dados.seo_url` | `seo_url` | direto |
| `dados.title` | `title` | direto |
| `dados.status` | `status` | direto |
| `dados.start_date` | `start_date` | `parse_date():54` `fromisoformat` |
| `dados.cae` (lista) | `cae` | `extrair_cae():45` `",".join` |
| `dados.contacts.email` | `contacts_email` | direto |
| `dados.structure.capital` | `structure_capital` | `parse_capital():65` `","→"."` float |
| `creditos.used` | `creditos_used` | direto |
| `creditos.left.month` | `creditos_left_month` | `parse_int():74` |

Lista completa em `colunas_tabela():132` (36 nomes).

### 9.4 Caso limite `creditos.left`

* **Pago:** `left: {"month":999, "day":99, "hour":9, "minute":0, "paid":0}` → `parse_int` extrai valores.
* **Gratuito (real 2026-09-10):** `left: []` (lista vazia) → `importar_nif.py:90` faz `creditos.get("left") or {}` → `{}` → todas as colunas `creditos_left_*` ficam `NULL`. **Não crasha**, mas `MANUAL.md` anterior exemplificava sempre `dict` — agora documentado.

### 9.5 Validação Mod-11

`consulta_nif.py:26`:

```python
def validar_nif(nif: str) -> bool:
    if not nif.isdigit() or len(nif) != 9: return False
    total = sum(int(d) * (9 - i) for i, d in enumerate(nif[:8]))
    resto = total % 11
    digito_controlo = 0 if resto in (0, 1) else 11 - resto
    return digito_controlo == int(nif[8])
```

Fórmula AT: `Σ d[i]*(9-i) %11 → 0 se resto 0/1 senão 11-resto`.

---

## 10. Códigos de Erro e Saída

| Campo `erro` | `valido` | `exit` | Significado | Ação |
|--------------|----------|--------|-------------|------|
| `null` | `true` | `0` | Sucesso | — |
| `Uso: python consulta_nif.py <NIF>` | — | `1` | Sem argumento | Passar NIF |
| `NIF deve conter apenas dígitos` | — | `1` | `nif.isdigit()==False` | Corrigir input |
| `NIF-PT-KEY não encontrada no .env` | `validar_nif(nif)` | `1` | Chave em falta | Criar `config/.env` |
| `Timeout na consulta à API nif.pt` | `validar_nif(nif)` | `1` | `requests.Timeout` | Aumentar `timeout` ou retry |
| `Erro de rede: ...` | `validar_nif(nif)` | `1` | `RequestException` | Verificar rede/DNS |
| `Resposta inválida (não JSON)` | `validar_nif(nif)` | `1` | `JSONDecodeError` | Reportar à API |
| `No records found` / `error` | `validar_nif(nif)` | `1` | `result != "success"` | NIF sem registo público |
| `ERRO: Nenhum JSON recebido no stdin.` | — | `1` | `stdin` vazio | Verificar pipe |
| `ERRO: AZURE_USER ... não definidos` | — | `1` | `.env` sem Azure | Preencher `.env` |
| `ERRO: Falha na ligação à BD` | — | `1` | `pyodbc.Error` | Ver driver/firewall |

Importadores propagam `resultado.erro` — se `consulta_nif.py` falhou, `importar_*.py` também falha sem inserir.

---

## 11. Logging

### 11.1 Estado atual

`Logging/logging_template.py:1` (579L) é **template avançado não integrado**. Nenhum script faz `import logging` ou `setup_logging()`; erros vão para `stderr` via `print(..., file=sys.stderr)`.

### 11.2 Funcionalidades do template

* Níveis: `LOG_LEVEL_GLOBAL=INFO`, `LOG_LEVEL_FILE=INFO`, `LOG_LEVEL_CONSOLE=INFO`.
* Saída: `LOG_FOLDER='log_files'`, `LOG_OUTPUT_FILE='log_files/general_app.log'`, prefixo `<<eqs>>` (legado, deve ser `<<nif-pt>>`).
* Formatos: `LOG_FORMAT_FILE/CONSOLE` + ultra-debug `%(filename)s - %(funcName)s - %(lineno)d`.
* Rotação: `RotatingFileHandler` custom com `LOG_MAX_BYTES=10485760` (10 MB), `LOG_MAX_RECORDS=5000`, `LOG_MAX_BACKUP=10`.
* Livro de estilo (9 estilos): `BANNER_APP_START/END [=,49]`, `BANNER_SECTION [-,49]`, `BANNER_FUNCTION [~,49,DEBUG]`, `TAG [tag]`, `SEPARATOR`, `BOX`, `TIMING_APP/SECTION/FUNCTION` (`time.perf_counter()`, `%.2fs`).

Ver [docs/guides/logging.md](docs/guides/logging.md) para integração.

### 11.3 Como ativar (roadmap `v0.3`)

```python
from Logging.logging_template import setup_logging
logger = setup_logging()
logger.info("=" * 49)
logger.info(f"{' nif-pt a iniciar ':=^49}")
logger.info("=" * 49)
```

Trocar `LOG_OUTPUT_PREFIX='<<eqs>>'` → `'<<nif-pt>>'` e criar `log_files/`.

---

## 12. Exemplos Práticos (PowerShell & Bash)

Cada cenário em **duas colunas**: PowerShell 5.1 e Bash (WSL/Git Bash).

### 12.1 Consultar e guardar em SQLite

| PowerShell | Bash |
|------------|------|
| `python consulta_nif.py 509442013 \| python importar_nif_sqlite.py` | idem |

### 12.2 Consultar e guardar em Azure SQL

| PowerShell | Bash |
|------------|------|
| `python consulta_nif.py 509442013 \| python importar_nif.py` | idem |

### 12.3 Consultar e guardar em ambos

| PowerShell | Bash |
|------------|------|
| `$j = python consulta_nif.py 509442013`<br>`$j \| python importar_nif_sqlite.py`<br>`$j \| python importar_nif.py` | `python consulta_nif.py 509442013 \| tee >(python importar_nif_sqlite.py) \| python importar_nif.py` |

### 12.4 Guardar JSON para ficheiro

| PowerShell | Bash |
|------------|------|
| `python consulta_nif.py 509442013 > resultado.json` | idem |
| `python importar_nif_sqlite.py < resultado.json` | idem |

### 12.5 Batch de NIFs

**PowerShell:**
```powershell
Get-Content nifs.txt | ForEach-Object {
    Write-Host "A consultar $_"
    python consulta_nif.py $_ | python importar_nif_sqlite.py
    Start-Sleep -Seconds 1
}
```

**Bash:**
```bash
while read nif; do
    echo "A consultar $nif"
    python consulta_nif.py "$nif" | python importar_nif_sqlite.py
    sleep 1
done < nifs.txt
```

### 12.6 Consultar histórico SQLite

```bash
# PowerShell e Bash (sqlite3 precisa estar no PATH)
python -c "
import sqlite3, json
conn = sqlite3.connect('data/nif_pt.db')
for id, nif, dados, data in conn.execute('SELECT id, nif, dados, data_consulta FROM nif_pt ORDER BY data_consulta DESC LIMIT 5'):
    j = json.loads(dados)
    print(f'{id}: NIF {nif} — {j[\"dados\"][\"title\"]} — {data}')
"

# Via sqlite3 CLI
sqlite3 data/nif_pt.db "SELECT id, nif, data_consulta FROM nif_pt;"
sqlite3 data/nif_pt.db ".schema nif_pt"
```

### 12.7 Validar NIF sem gastar créditos

```bash
python -c "from consulta_nif import validar_nif; print(validar_nif('509442013'))"  # True
python -c "from consulta_nif import validar_nif; print(validar_nif('123456789'))"  # False
```

---

## 13. Resolução de Problemas (Troubleshooting)

### 13.1 "NIF-PT-KEY não encontrada no .env"

1. Verificar `config/.env` existe (não `config\.env` nem `.env` na raiz).
2. Linha exata `NIF-PT-KEY=xxxxx` com hífen, sem espaços à volta de `=`.
3. Solicitar chave em http://www.nif.pt/contactos/api/.

### 13.2 "No records found"

NIF válido mas sem registo público em `nif.pt`. Pode ser pessoa singular sem atividade ou NIF recente. Não é erro de código — `importar_*.py` não insere.

### 13.3 "NIF deve conter apenas dígitos"

`consulta_nif.py:98` rejeita antes de rede. Verificar `nifs.txt` não tem espaços, traços ou `PT`.

### 13.4 "database is locked" (SQLite)

`importar_nif_sqlite.py:40` já usa `PRAGMA journal_mode=WAL`. Se persistir: garantir só um processo escreve de cada vez; considerar `PRAGMA busy_timeout=5000`.

### 13.5 Erro de ligação Azure SQL

1. `Test-Path config/.env` e `AZURE_USER`/`AZURE_PALAVRA_CHAVE` preenchidos.
2. IP whitelist no Portal Azure → SQL → Networking.
3. `ODBC Driver 18 for SQL Server` instalado (`Get-OdbcDriver` em PowerShell).
4. `Encrypt=yes;TrustServerCertificate=no;` em `importar_nif.py:34` — se erro SSL, verificar `TrustServerCertificate`.

### 13.6 Validação Mod-11 não bloqueia request

`validar_nif()` (`consulta_nif.py:26`) só afeta campo `valido`; `main():98` só valida `isdigit()`. NIF `123456789` (dígito errado) **ainda faz request** e gasta crédito. Para filtrar antes:

```bash
python -c "from consulta_nif import validar_nif; import sys; sys.exit(0 if validar_nif('123456789') else 1)" && python consulta_nif.py 123456789
# ou no código: if not validar_nif(nif): print(...); sys.exit(1)
```

Correção futura: `if not validar_nif(nif): return {"erro":"NIF inválido (dígito controlo)"}` antes de `requests.get`.

### 13.7 "`timeout:1000` demora 16 minutos"

`config.yaml:3` `timeout:1000` são **segundos** (`requests` espera segundos). Mudar para `timeout: 10` ou `15`:

```yaml
default:
  timeout: 10
```

### 13.8 "`tee` não funciona em PowerShell"

`tee >( )` é Bash. Em PowerShell usar variável ou `Tee-Object` (ver §6.4).

### 13.9 `ModuleNotFoundError: No module named 'yaml'`

`requirements.txt` antigo tinha `yaml` (pacote placeholder). Atual:

```bash
pip uninstall yaml -y
pip install pyyaml python-dotenv pyodbc
# ou
pip install -r requirements.txt  # v0.2.1+
```

### 13.10 `pyodbc` falha a instalar

Requer *Build Tools* (Windows) ou `unixODBC` (Linux). Em Windows instalar via `pip install pyodbc` com *wheel* pré-compilado (Python 3.11 `pyodbc.cp311-win_amd64.pyd` incluído).

---

## 14. FAQ

**1. A consulta tem custo?**
Plano `free` limitado (`creditos.left`); `paid` ilimitado. Ver `creditos.used` no JSON.

**2. Quantos créditos tenho?**
`creditos.left` é `dict` (`month/day/hour/minute/paid`) quando `paid`, `[]` quando `free` (§9.4). `importar_nif.py` mapeia para `creditos_left_*` (NULL se `[]`).

**3. Diferença SQLite vs Azure SQL?**
SQLite guarda JSON bruto (flexível, 4 cols); Azure normaliza 36 cols (analítico, 40 cols staging). ADR-001 em §2.4.

**4. Fórmula Mod-11?**
`Σ d[i]*(9-i) %11 → 0 se resto 0/1 senão 11-resto` == `d[8]`. `consulta_nif.py:26`.

**5. Posso consultar NIFs em lote?**
Sim, ver §12.5. Respeitar `sleep 1` para não exceder rate-limit.

**6. `main.py` serve para quê?**
Stub legado (7L). Será `cli.py` com `argparse` em `v0.3`.

**7. Preciso de Azure SQL?**
Não. `importar_nif_sqlite.py` funciona standalone.

**8. O que é `stg_nunotome`?**
Schema pessoal (`config.yaml:25`). Mudar para `stg` ou `dbo` se partilhar BD.

**9. Como sei se NIF é válido sem consultar API?**
`python -c "from consulta_nif import validar_nif; print(validar_nif('509442013'))"`

**10. Onde vejo o histórico?**
`SELECT * FROM nif_pt ORDER BY data_consulta DESC` (SQLite) ou `SELECT * FROM stg_nunotome.nif_pt_stg WHERE processado=0` (Azure).

---

## 15. Anexos

### 15.1 Glossário

Ver [docs/glossary.md](docs/glossary.md).

| Termo | Definição |
|-------|-----------|
| NIF | Número de Identificação Fiscal (9 dígitos, PT) |
| Mod-11 | Algoritmo dígito de controlo AT |
| CAE | Classificação Portuguesa de Atividades Económicas |
| WAL | Write-Ahead Logging (SQLite) |
| ODBC | Open Database Connectivity |
| `stg` | Staging (área temporária) |
| `creditos.left` | Créditos restantes da API `nif.pt` |

### 15.2 Estrutura de ficheiros

```
nif-pt/
├── consulta_nif.py            # 110L — consulta API nif.pt
├── importar_nif.py            # 213L — 36 cols → Azure SQL
├── importar_nif_sqlite.py     # 88L  — JSON bruto → SQLite
├── main.py                    # 7L  — stub (será cli.py)
├── config/
│   ├── config.py              # 40L — get_config()
│   ├── config.yaml            # 27L — default + 3 blocos
│   ├── .env.example           # template commitado
│   └── .env                   # segredos (NÃO versionar)
├── sql/01_criar_tabelas.sql   # 157L — DDL nif_pt + nif_pt_stg
├── Logging/logging_template.py# 579L — template rotação (não integrado)
├── api/__init__.py            # vazio, reservado FastAPI
├── models/__init__.py         # vazio, reservado Pydantic
├── scrapers/__init__.py       # vazio, reservado fallback HTML
├── utils/__init__.py          # vazio, reservado helpers
├── docs/                      # documentação técnica
│   ├── architecture/
│   ├── database/
│   ├── api/
│   ├── guides/
│   └── glossary.md
├── data/nif_pt.db             # gerado, ignorado
├── requirements.txt           # requests, pyyaml, python-dotenv, pyodbc
├── README.md                  # porta de entrada
├── CHANGELOG.md               # histórico versões
├── CONTRIBUTING.md
├── SECURITY.md
└── MANUAL.md                  # este ficheiro
```

### 15.3 Changelog resumido

Ver [CHANGELOG.md](CHANGELOG.md) completo.

### 15.4 Licença e contactos

* Repositório: https://github.com/nunoetome/nif-pt
* Chave API: http://www.nif.pt/contactos/api/
* Autor template logging: `Nuno Tomé` — https://github.com/nunoetome/my_python_starter_kit

### 15.5 Referências

* `nif.pt` API: `GET http://www.nif.pt/?json=1&q=<NIF>&key=<KEY>` (`consulta_nif.py:48`)
* `config/config.py:17` `get_config()`
* `sql/01_criar_tabelas.sql:21` DDL
* [docs/architecture/diagrams.md](docs/architecture/diagrams.md) — todos os diagramas Mermaid
