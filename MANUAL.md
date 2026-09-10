# Manual de Instruções — nif-pt v1.2.0 (cache + run_id)

> Ferramenta Python para consulta de NIFs portugueses via [nif.pt](http://www.nif.pt) (`?json=1`) com validação Mod-11, pipeline Unix e persistência SQLite WAL + validação cache (`nif_ignorados`) + camada resiliente de rate-limit + **rastreabilidade `run_id` (UUID v4) por execução**.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-v1.2.0-blue.svg)](CHANGELOG.md)

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

`nif-pt` consulta a base pública do portal `nif.pt` (`GET ?json=1&q=<NIF>&key=<KEY>`) e guarda o resultado localmente em SQLite WAL. Destina-se a pessoas coletivas com registo público; NIFs de pessoas singulares ou recentes podem devolver `No records found`.

Novidade `v1.0.0`: camada `utils/error_handler.py` (806L) classifica erros de quota, persiste em `nif_api_erros` (SQLite WAL, 15c com `run_id`) e aplica `retry 60s` (minuto) / `3600s` (hora) com limites `max_tentativas_global 5 / minuto 3 / hora 2 / dia 0 / mes 0`.
Novidade `v1.1.0`: **rastreabilidade `run_id`** — `utils/run_id.py` (191L) `generate_run_id()` UUID v4 + `ContextVar` + `ensure_run_id(CLI>payload>ctx>gen)`, `consulta_nif.py:consultar_nif(nif, run_id)` inclui `run_id` em todos os JSON, `importar_nif_sqlite.py` persiste `run_id` (5c/15c) com `ALTER TABLE` idempotente + `INDEX run_id`, CLI `--run-id` determinístico.
Novidade `v1.2.0`: **validação cache SQLite** — `utils/cache_validator.py` (407L) `is_nif_recente(nif, dias)` verifica `nif_pt` antes de API; se NIF consultado há < `cache_antiguidade_dias` (default 30d) → regista `nif_ignorados` 6c (`id, nif, data_tentativa, data_ultima_consulta, dias_desde_ultima, motivo='cache_recente'`) + `stdout` JSON `{ignorado:true, motivo:cache_recente, data_ultima_consulta, cache_antiguidade_dias}` + `sys.exit(0)` sem gastar créditos; `importar_nif_sqlite.py:194` faz early skip se `ignorado`; configuração `config/config.yaml:15` `cache_ativo/cache_antiguidade_dias/cache_tabela_ignorados`; TAG `[cache]` + `BOX NIF ignorado`.

### 1.2 Funcionalidades

| ID | Funcionalidade | Estado | Ficheiro |
|----|----------------|--------|----------|
| RF-01 | Validar NIF Mod-11 | ✅ | `consulta_nif.py:99` `validar_nif()` |
| RF-02 | Consultar `nif.pt` (`?json=1&q=&key=`, timeout 10s) | ✅ | `consulta_nif.py:272` `requests.get` |
| RF-03 | JSON normalizado (`valido/fonte/erro/dados/creditos/tipo_erro/run_id`) + `ignorado/motivo/data_ultima_consulta/cache_antiguidade_dias` se cache | ✅ | `consulta_nif.py:237` + `:547` + `utils/cache_validator.py:225` |
| RF-04 | Guardar JSON bruto SQLite WAL (5c com `run_id`) + early skip `ignorado` | ✅ | `importar_nif_sqlite.py:55` `get_db()` + `:194` |
| RF-05 | Pipeline `stdin/stdout` + `exit 0/1` com `run_id` + `ignorado` | ✅ | `sys.stdin.read()` + `utils/run_id.py:132` `--run-id` + `utils/cache_validator.py:329` |
| RF-06 | Camada `error_handler` (6 tipos, retry/abort, `nif_api_erros` 15c `run_id`) | ✅ | `utils/error_handler.py:515` `tratar_erro(...,run_id)` |
| RF-07 | Validação cache `nif_ignorados` 6c (`is_nif_recente` + `registar_ignorado` + `init_cache_tables`) | ✅ | `utils/cache_validator.py:225` + `consulta_nif.py:529` |
| RF-08 | Logging R1-R9 `<<nif-pt>>` `RotatingFileHandler` 10MB/5000/10 + TAG `[cache][run]` | ✅ | `Logging/logging_orchestrator.py:226` |
| RF-09 | `help()` PEP 257 em todos os módulos | ✅ | `docs/api/help.md` |
| RF-10 | Rastreabilidade `run_id` UUID v4 por execução + `nif_ignorados` cache | ✅ | `utils/run_id.py:41` + `utils/cache_validator.py:43` |

### 1.3 Requisitos não-funcionais

* **Performance:** `timeout 10s` (`config.yaml:3`), `WAL`, `sleep 60s/3600s` em retry, índices `run_id` + `idx_nif_ignorados_*`, cache evita API para NIFs recentes.
* **Segurança:** segredos só em `config/.env` (`.gitignore`), `NIF-PT-KEY` mascarada `***XXXX` em todos os logs.
* **Portabilidade:** `pathlib`, só `sqlite3` stdlib (sem `pyodbc`/`ODBC`), dual PowerShell 5.1 / Bash, `ContextVar` para `run_id`.
* **Observabilidade:** `log_files/nif_pt.log` com BOX `| NIF : ... |` + `| run_id : ... |` + `| Ultima : ... |` + TAG `[api][valid][cfg][db][sqlite][io][cache][erro][rate-limit][run]` + TIMING `%.2fs` + `run_id` em `nif_pt`/`nif_api_erros` + `nif_ignorados` com `motivo`.

### 1.4 Público-alvo e limitações

Operações, compliance, data engineering. `nif.pt` é agregadora — pode estar desatualizada, com `rate-limit` (`creditos.left`) ou sem registo (`No records found` não indica NIF inválido). Cache de 30d por defeito evita re-consulta dentro da janela; use `cache_ativo: false` ou `cache_antiguidade_dias: 0` para forçar refresh.

### 1.5 Histórico de versões

| Versão | Data | Destaque |
|--------|------|----------|
| `v.0.1.0-alpha` | 2026-06-26 | Fundação `consulta_nif` + SQLite + DDL |
| `v0.2.0-beta` | 2026-06-26 | Config centralizada, SQLite JSON bruto, `MANUAL` 310L |
| `v1.0.0` | 2026-09-10 | `error_handler` 806L + `nif_api_erros` + `logging_orchestrator` 580L + `timeout 10s` + `max_tentativas_*` |
| `v1.1.0` | 2026-09-11 | `run_id` UUID v4 191L + `consulta_nif(nif,run_id)` + `importar_nif_sqlite` 5c + `error_handler` 15c `run_id` + `--run-id` |
| `v1.2.0` **(esta)** | 2026-09-10 | `cache_validator` 407L + `nif_ignorados` 6c + `is_nif_recente/registar_ignorado` + payload `ignorado` + early skip + `TAG [cache]` + remoção Azure/`pyodbc`/`sql/0*` |

Ver [CHANGELOG.md](CHANGELOG.md) completo.

---

## 2. Arquitetura e Pipeline

### 2.1 Diagrama de pipeline

```mermaid
graph LR
    U[Utilizador<br/>NIF 9 dígitos --run-id] --> C[consulta_nif.py<br/>validar_nif + cache is_nif_recente<br/>+ requests + run_id UUID v4]
    C -->|cache hit<br/>ignorado:true motivo:cache_recente| IG[(nif_ignorados<br/>6c cache_recente WAL)]
    C -->|stdout JSON run_id<br/>ensure_ascii=False| S[importar_nif_sqlite.py<br/>JSON bruto WAL 5c<br/>early skip ignorado run_id]
    C -->|erro classificado run_id| E[(nif_api_erros<br/>SQLite 15c run_id)]
    C -->|cache miss| API[(nif.pt<br/>GET ?json=1&q=&key=)]
    S --> DB[(data/nif_pt.db<br/>nif_pt 5c + nif_api_erros 15c<br/>+ nif_ignorados 6c<br/>PRAGMA WAL)]
    IG --> DB
    E --> DB
    CV[utils/cache_validator.py<br/>DDL 6c 2 índices + is_nif_recente<br/>+ registar_ignorado] -. cache .-> C
    R[utils/run_id.py<br/>generate_run_id + ContextVar<br/>ensure CLI>payload>ctx>gen] -. run_id .-> C & S & E
    CFG[config.yaml 31L + .env<br/>get_config merge cache_*] -.-> C & S & E & CV
    LOG[logging_orchestrator<br/>R1-R9 <<nif-pt>> [cache][run]] -.-> C & S & E & CV
```

Fonte única: [docs/technical.md](docs/technical.md) + [docs/architecture/diagrams.md](docs/architecture/diagrams.md).

### 2.2 Pipeline `stdin`/`stdout`

```
consulta_nif.py  ──JSON run_id──────────>  importar_nif_sqlite.py  (SQLite WAL 5c, INSERT)
                 ──JSON ignorado:true──>  importar_nif_sqlite.py  (skip INSERT, BOX skip)
                 ──erro run_id─────────>  nif_api_erros           (auditoria 15c)
                 ──cache hit───────────>  nif_ignorados           (6c, sem API)
```
Precedência `run_id`: `CLI --run-id` > `payload JSON run_id` > `ContextVar` > `uuid4` (`utils/run_id.py:87` `ensure_run_id()`); `main.py:60` `ensure_run_id()` por execução.

* `consulta_nif.py` só JSON em `stdout` (`consulta_nif.py:585` `json.dumps(..., indent=2, ensure_ascii=False)`) com campo `run_id` + opcional `ignorado/motivo/data_ultima_consulta/cache_antiguidade_dias`; humanos em `stderr` (`<<nif-pt>>` + `[cache][run]`).
* Cache: `consulta_nif.py:529` `is_nif_recente(nif, dias=30)` se `cache_ativo==true`; se `recente==True` → `registar_ignorado(nif, data_ultima)` → `stdout` JSON `ignorado:true` + `BOX NIF ignorado - cache recente` + `sys.exit(0)` sem `requests.get`.
* Importador `sys.stdin.read()` → `json.loads` → `ensure_run_id(CLI>payload>ctx>gen)` (`importar_nif_sqlite.py:185`) → `if ignorado: INFO [cache] skip + BOX skip + exit 0` else `if erro: exit 1` else `INSERT (nif,dados,data_consulta,run_id)`; `nif_api_erros` persiste **sempre** antes de decidir `retry/abort` com `run_id` (`utils/error_handler.py:368`).
* `nif_ignorados` persiste tentativas ignoradas com `data_tentativa DEFAULT datetime('now')` + `dias_desde_ultima` calculado.

### 2.3 Centralização de configuração

`config/config.py:53` `get_config(script_name)`:

1. `default` (`config.yaml:1` — 14 chaves `retry_count`, `timeout 10`, `tempo_*`, `max_tentativas_*`, `cache_*`)
2. Bloco do script (`consulta_nif` / `importar_nif_sqlite`)
3. `.env` (`NIF-PT-KEY` com hífen, `API_TOKEN`)

```python
cfg = get_config("consulta_nif")
API_BASE = cfg.get("api_base", "http://www.nif.pt")
API_KEY  = cfg.get("NIF_PT_KEY")  # os.getenv("NIF-PT-KEY")
TIMEOUT  = cfg.get("timeout", 10)
CACHE_ATIVO = cfg.get("cache_ativo", True)
CACHE_DIAS  = cfg.get("cache_antiguidade_dias", 30)
MAX_GLOBAL = cfg.get("max_tentativas_global", 5)
```

### 2.4a Rastreabilidade `run_id` (v1.1.0)

`utils/run_id.py` (191L):

| Função | Linha | Descrição |
|--------|-------|-----------|
| `generate_run_id()` | `:41` | `str(uuid.uuid4())` — 36 chars, 4 hífens, `logger.debug [run]` |
| `set_run_id` / `get_run_id` | `:59` / `:78` | `ContextVar[str|None] _run_id_ctx` thread-safe |
| `ensure_run_id(cli_value, payload_value)` | `:87` | Precedência `CLI > payload > ContextVar > geração` + `set_run_id` |
| `extract_cli_run_id(argv)` | `:132` | Parse `--run-id UUID` e `--run-id=UUID` sem `argparse` |
| `remove_run_id_args(argv)` | `:163` | Cópia `argv` sem `--run-id` para `isdigit` posicional |

**Fluxo por script:**

* `consulta_nif.py:481` `main()` → `cli_run_id=extract_cli_run_id()` → `_run_id=ensure_run_id(cli_value)` → `logger_main.info("[run] run_id=%s", _run_id)` → `is_nif_recente` / `consultar_nif(nif, run_id=_run_id)` (`:237` resolve `run_id or get_run_id() or generate_run_id()` e inclui `run_id` em todos os `return`).
* `importar_nif_sqlite.py:158` → `cli_run_id=extract_cli_run_id()` → `if cli_run_id: set_run_id(...)` → após `json.loads` → `ensure_run_id(cli_value, payload_value=resultado.get("run_id"))` → `if ignorado: skip` else `INSERT (...,run_id)` + fallback se coluna falta (`:238`).
* `utils/error_handler.py:368` `guardar_erro(...,run_id)` + `:515` `tratar_erro(...,run_id)` — propagam `run_id` (ou `get_run_id()` se `None`) para `nif_api_erros` 15c.
* `main.py:60` `ensure_run_id(cli_value=extract_cli_run_id())` por execução.

**Persistência:** DDL `run_id TEXT` + `CREATE INDEX ...run_id` + migração idempotente (`PRAGMA table_info` + `ALTER TABLE ADD COLUMN`) — ver §7.4.

### 2.4b Validação cache (v1.2.0) — `utils/cache_validator.py` 407L

| Função | Linha | Descrição |
|--------|-------|-----------|
| `is_nif_recente(nif, dias)` | `:225` | `SELECT data_consulta FROM nif_pt WHERE nif=? ORDER BY datetime(data_consulta) DESC LIMIT 1` + `_parse_data_consulta` (YYYY-MM-DD HH:MM:SS/ISO/Z) + `total_seconds/86400 < dias` + `INFO [cache] recente=True/False (%.2fs)`; fail-open `(False,None)` se erro BD |
| `registar_ignorado(nif, data_ultima, motivo="cache_recente")` | `:329` | `INSERT nif_ignorados (nif, data_ultima_consulta, dias_desde_ultima, motivo)` + `dias_desde = (now - data_ultima).days` + `INFO [cache] Ignorado registado id=...` |
| `init_cache_tables()` | `:163` | DDL `nif_ignorados` 6c + 2 índices WAL idempotente (chamado `consulta_nif.py:536`) |
| `_get_cache_config()` | `:101` | Lê `cache_ativo`, `cache_antiguidade_dias`, `cache_tabela_ignorados` (sanitizado `alnum+_`) do YAML |
| `_parse_data_consulta(val)` | `:188` | Converte `YYYY-MM-DD HH:MM:SS` / `ISO` / `Z` → `datetime` |
| `_get_connection()` | `:126` | `PRAGMA WAL` + `executescript(DDL_IGNORADOS)` + 2 índices + sanitiza nome tabela |

**DDL `nif_ignorados` 6c (`utils/cache_validator.py:43`):**

```sql
CREATE TABLE IF NOT EXISTS nif_ignorados (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    nif                     INTEGER NOT NULL,
    data_tentativa          TEXT NOT NULL DEFAULT (datetime('now')),
    data_ultima_consulta    TEXT,
    dias_desde_ultima       INTEGER,
    motivo                  TEXT NOT NULL DEFAULT 'cache_recente'
);
CREATE INDEX IF NOT EXISTS idx_nif_ignorados_nif ON nif_ignorados(nif);
CREATE INDEX IF NOT EXISTS idx_nif_ignorados_data ON nif_ignorados(data_tentativa);
```

**Fluxo `consulta_nif.py:529` `main()` (antes de API):**

```python
cache_ativo, cache_dias, _ = _get_cache_config()
if cache_ativo:
    init_cache_tables()  # fail-open
    recente, data_ultima = is_nif_recente(nif, dias=cache_dias)  # fail-open False,None
    if recente:
        registar_ignorado(nif, data_ultima)  # fail-open warning
        payload = {"nif": nif, "valido": ..., "fonte": None, "erro": None,
                   "ignorado": True, "motivo": "cache_recente",
                   "data_ultima_consulta": data_ultima, "cache_antiguidade_dias": cache_dias,
                   "run_id": _run_id}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        # BOX NIF ignorado - cache recente + sys.exit(0) sem requests.get
```

**Payload `ignorado` → `importar_nif_sqlite.py:194`:**

```python
if resultado.get("ignorado"):
    logger.info("[cache] NIF %s ignorado (cache_recente) ultima=%s run_id=%s - skip INSERT", ...)
    # BOX NIF ignorado - skip SQLite + sys.exit(0) sem INSERT
```

**Exemplo:**

```powershell
# 1ª consulta — cache miss, vai à API
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
# log: [cache] NIF 509442013 ... recente=False -> GET -> INSERT -> nif_ignorados vazio

# 2ª consulta em <30d — cache hit, sem API
python consulta_nif.py 509442013
# stdout: {"nif":"509442013","ignorado":true,"motivo":"cache_recente","data_ultima_consulta":"2026-09-10 12:00:00","cache_antiguidade_dias":30,"run_id":"..."}
# stderr: [cache] NIF 509442013 ignorado - ultima consulta 2026-09-10 12:00:00 dentro de 30 dias
#         | NIF ignorado - cache recente | + run_id + sys.exit(0)
# sqlite: SELECT * FROM nif_ignorados WHERE nif=509442013;

# Pipe com ignorado — skip INSERT
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
# stderr: [cache] NIF 509442013 ignorado (cache_recente) ultima=... - skip INSERT
#         | NIF ignorado - skip SQLite | + sys.exit(0)

# Forçar refresh — desligar cache ou dias=0
# config.yaml: cache_ativo: false  ou  cache_antiguidade_dias: 0
# ou: sqlite3 data/nif_pt.db "DELETE FROM nif_ignorados WHERE nif=509442013; DELETE FROM nif_pt WHERE nif=509442013;"
```

Ver `docs/technical.md` §10c e `docs/database/schema.md` §4 (`nif_ignorados` 6c).

### 2.4c Camada de erros (v1.0.0 + run_id)

`utils/error_handler.py` (806L):

* `classificar_erro(data)` → `rate_limit_minute/hour/day/month/paid` / `generic_error` / `unknown` (mensagem `Limit per ...` + `credits.left` com `0`).
* `tratar_erro(nif, data, tentativas_por_tipo, tentativa_global, run_id)` → `{tipo, acao: retry|abort|none, espera: 60|3600|0, deve_retry, max_tipo, max_global}` com lógica `deve_retry = tenta_tipo < max_tipo && tenta_global < max_global`.
* `guardar_erro(...,run_id)` → `INSERT nif_api_erros` (15c, WAL) sempre.
* `init_error_table()` idempotente no arranque de `consulta_nif.py:486` (antes de cache).
* `get_tempo_espera()` / `get_max_tentativas()` lidos do `config.yaml`.

Fluxo `consulta_nif.py:171` `consultar_nif()`:

```
for tentativa_global in range(max_global+1):
    try: requests.get(...)
    except Timeout/RequestException: sleep 60s retry se <max_global
    if result != "success": tratar_erro(...,run_id) -> if retry: sleep 60s/3600s continue
                                          -> if abort: return erro+tipo_erro+run_id
    else: return sucesso
```

Ver [docs/technical.md §10](docs/technical.md#10-camada-de-erros).

### 2.5 Decisões técnicas (ADRs)

| ADR | Decisão | Justificação |
|-----|---------|--------------|
| ADR-001 | SQLite JSON bruto único (3 tabelas WAL) | Sem Azure; `sqlite3` stdlib, 3 deps |
| ADR-002 | `WAL` em `nif_pt` + `nif_api_erros` + `nif_ignorados` | Mitiga `database is locked` |
| ADR-007 | `error_handler` + `nif_api_erros` 15c `run_id` | Auditoria + retry `60s/3600s` vs abort + rastreabilidade |
| ADR-009 | `run_id` UUID v4 + `ContextVar` + `ensure_run_id` | `CLI>payload>ctx>gen`, `--run-id` replay, índices `run_id` |
| ADR-010 | Cache `nif_ignorados` 6c + `is_nif_recente` + `registar_ignorado` + payload `ignorado` + early skip | Evita créditos para NIFs recentes (30d), audita com 2 índices, fail-open, `TAG [cache]` |

Ver [docs/technical.md §12](docs/technical.md#12-adrs) e [docs/architecture/architecture.md](docs/architecture/architecture.md) (10 ADRs).

---

## 3. Pré-requisitos

### 3.1 Matriz de dependências

| Dependência | Versão | Instalação | Obrigatória |
|-------------|--------|------------|-------------|
| Python | `>=3.11` | https://www.python.org/downloads/ | ✅ |
| `requests` | `>=2.31.0` | `pip install -r requirements.txt` | ✅ |
| `pyyaml` | `>=6.0.1` | idem | ✅ |
| `python-dotenv` | `>=1.0.0` | idem | ✅ |
| Chave `nif.pt` | — | http://www.nif.pt/contactos/api/ | ✅ |
| `sqlite3` | stdlib | — | ✅ |

> Sem `pyodbc`, sem `ODBC Driver 18`, sem Azure.

### 3.2 Chave `NIF-PT-KEY`

1. Solicitar em http://www.nif.pt/contactos/api/ (1-2 dias por email).
2. `config/.env` → `NIF-PT-KEY=xxxxx` **com hífen** (`config/config.py:120` `os.getenv("NIF-PT-KEY")`).

---

## 4. Instalação

### 4.1 Clonar

```bash
git clone https://github.com/nunoetome/nif-pt.git
cd nif-pt
git checkout v1.2.0   # stable; dev para desenvolvimento
```

### 4.2 Criar `venv`

**PowerShell (Windows — o teu caso):**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
# se bloquear: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# verificar:
Get-Command python | Format-List Source  # ...\nif-pt\.venv\Scripts\python.exe
```

**Git Bash (MINGW64):**

```bash
python -m venv .venv
source .venv/Scripts/activate
which python  # .../nif-pt/.venv/Scripts/python.exe
```

> `venv/Scripts/activate` é Windows; `venv/bin/activate` só Linux. `Activate.ps1` só PS.

### 4.3 Instalar dependências

```bash
pip install -r requirements.txt
# requests>=2.31.0
# pyyaml>=6.0.1
# python-dotenv>=1.0.0
```

### 4.4 Verificar

```bash
python -c "from config.config import get_config; print(get_config('consulta_nif').keys())"
python -c "import consulta_nif; help(consulta_nif.validar_nif)"
python -c "from utils.cache_validator import is_nif_recente; help(is_nif_recente)"
python -c "from utils.cache_validator import init_cache_tables; init_cache_tables(); print('nif_ignorados OK')"
python consulta_nif.py 509442013  # requer NIF-PT-KEY
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
python consulta_nif.py 509442013  # 2ª vez -> ignorado:true se <30d
```

---

## 5. Configuração

### 5.1 `config/config.yaml` (31L)

```yaml
default:
  retry_count: 1
  timeout: 10
  tempo_de_espera: 60
  tempo_espera_minuto: 60
  tempo_espera_hora: 3600
  max_tentativas_global: 5
  max_tentativas_minuto: 3
  max_tentativas_hora: 2
  max_tentativas_dia: 0
  max_tentativas_mes: 0
  max_tentativas_paid: 0
  cache_ativo: true
  cache_antiguidade_dias: 30
  cache_tabela_ignorados: "nif_ignorados"
consulta_nif:
  api_base: "http://www.nif.pt"
importar_nif_sqlite:
  db_path: "data/nif_pt.db"
  tabela: "nif_pt"
```

| Chave | Onde usada | Descrição |
|-------|------------|-----------|
| `timeout` | `consulta_nif.py:79` `requests.get(timeout=10)` | segundos (10s) |
| `tempo_de_espera` | `consulta_nif.py:81` | retry rede/Timeout genérico 60s |
| `tempo_espera_minuto/hora` | `utils/error_handler.py:272` `get_tempo_espera()` | 60s / 3600s por janela rate-limit |
| `max_tentativas_global` | `consulta_nif.py:86` `MAX_TENTATIVAS_GLOBAL` | limite total (5) |
| `max_tentativas_minuto/hora/dia/mes` | `utils/error_handler.py:296` | 3 / 2 / 0 / 0 (0=abort) |
| `cache_ativo` | `consulta_nif.py:532` + `utils/cache_validator.py:113` | `true` liga cache antes de API |
| `cache_antiguidade_dias` | `consulta_nif.py:539` `is_nif_recente(nif, dias)` | janela dias (30); `<=0` desliga |
| `cache_tabela_ignorados` | `utils/cache_validator.py:119` | nome tabela ignorados (sanitizado) |
| `api_base` | `consulta_nif.py:77` | `http://www.nif.pt` |
| `db_path` | `importar_nif_sqlite.py:52` | `data/nif_pt.db` |

### 5.2 `config/.env` (+ `.env.example`)

```env
# NIF-PT — http://www.nif.pt/contactos/api/
NIF-PT-KEY=coloque_aqui

# Opcional futuro
# API_TOKEN=...
```

* `Copy-Item config\.env.example config\.env` e editar — **nunca** commitar (`.gitignore`).
* Nome **exato** `NIF-PT-KEY` com hífen — `NIF_PT_KEY` não é lido (`config.py:120`).

### 5.3 Precedência

`default` < bloco do script < `.env` — `config.py:115` `config.update(script_config)` (shallow merge).

---

## 6. Utilização — Modos de Operação

### 6.1 Modo 1 — Só consulta (sem gravar)

```powershell
python consulta_nif.py 509442013
python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000  # replay determinístico
```

* Valida `isdigit` + `validar_nif()` Mod-11 (`consulta_nif.py:99`) — log `WARN` se falha mas **não bloqueia** cache/API.
* `run_id` gerado em `consulta_nif.py:481` `ensure_run_id(cli_value=extract_cli_run_id())`; `run_id` incluído em **todos** os JSON (`consultar_nif(nif, run_id)` `consulta_nif.py:237` + cache `ignorado`), log `[run] run_id=...` e `BOX | run_id |`.
* Se `NIF-PT-KEY` falta → `{"erro":"NIF-PT-KEY não encontrada","run_id":"..."} ` + `exit 1` (`consulta_nif.py:248`).
* Senão verifica cache: `cache_ativo==true` → `init_cache_tables()` → `is_nif_recente(nif, dias=30)`; se `recente==True` → `registar_ignorado(nif, data_ultima)` → JSON `{ignorado:true, motivo:cache_recente, data_ultima_consulta, cache_antiguidade_dias, run_id}` + `BOX NIF ignorado - cache recente` + `exit 0` **sem** `GET`.
* Senão `GET http://www.nif.pt/?json=1&q=<NIF>&key=<KEY>` com `timeout 10s` e loop `max_global+1` com `tratar_erro(...,run_id)` + `guardar_erro(...,run_id)`.

### 6.2 Modo 2 — SQLite local

```powershell
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000 | python importar_nif_sqlite.py --run-id 550e8400-e29b-41d4-a716-446655440000
# se cache miss:
# stderr: [sqlite] INSERT nif_pt nif=509442013 run_id=550e8400 -> 1 row em 0.02s
#         | Guardado em SQLite | + run_id
# se cache hit (ignorado):
# stderr: [cache] NIF 509442013 ignorado (cache_recente) ultima=... run_id=550e8400 - skip INSERT
#         | NIF ignorado - skip SQLite |
```

* `get_db()` cria `data/nif_pt.db` + `nif_pt` (`CREATE TABLE IF NOT EXISTS` 5c `run_id TEXT`, `PRAGMA WAL`) + `idx_nif_pt_run_id` e `nif_api_erros`/`nif_ignorados` via `init_*_tables()`; migração idempotente `ALTER TABLE ADD COLUMN run_id TEXT`.
* `INSERT (nif, dados=JSON completo, data_consulta=datetime.now(), run_id)` (`importar_nif_sqlite.py:238`) herdado do JSON via `ensure_run_id(CLI>payload>ctx>gen)` (`:185`) com fallback se coluna falta; se `resultado.get("ignorado")==True` → skip INSERT + `exit 0` (audita só `nif_ignorados`).

### 6.3 Modo 3 — Batch (múltiplos NIFs) + cache

**PowerShell:**

```powershell
Get-Content nifs.txt | ForEach-Object {
    python consulta_nif.py $_ | python importar_nif_sqlite.py
    Start-Sleep -Seconds 1  # respeitar rate-limit minuto; cache evita re-pedido <30d
}
```

**Bash:**

```bash
while read nif; do
    python consulta_nif.py "$nif" | python importar_nif_sqlite.py
    sleep 1
done < nifs.txt
```

Cache evita API para NIFs já em `nif_pt` há <30d; `nif_ignorados` regista tentativas ignoradas.

### 6.4 Modo 4 — Forçar refresh (ignorar cache)

```powershell
# Opção 1: desligar temporariamente via config
# config.yaml -> cache_ativo: false  ou  cache_antiguidade_dias: 0
python consulta_nif.py 509442013 | python importar_nif_sqlite.py

# Opção 2: apagar histórico (local dev)
# sqlite3 data/nif_pt.db "DELETE FROM nif_ignorados WHERE nif=509442013;"
# sqlite3 data/nif_pt.db "DELETE FROM nif_pt WHERE nif=509442013;"

# Opção 3: janela curta
# config.yaml -> cache_antiguidade_dias: 1  (só considera recente se <1 dia)
```

### 6.5 Modo 5 — Ficheiro intermédio

```powershell
python consulta_nif.py 509442013 > resultado.json
# se ignorado: resultado.json tem {"ignorado": true, ...} -> importar faz skip
python importar_nif_sqlite.py < resultado.json
```

### 6.6 Modo 6 — Pipe e `tee` (PowerShell vs Bash)

**PowerShell (correção — `tee >( )` não existe):**

```powershell
$json = python consulta_nif.py 509442013          # inclui run_id + ignorado se cache
$json | python importar_nif_sqlite.py             # herda run_id; skip se ignorado
# ou determinístico:
$rid = "550e8400-e29b-41d4-a716-446655440000"
$json = python consulta_nif.py 509442013 --run-id $rid
$json | python importar_nif_sqlite.py             # mesmo $rid
# ou ficheiro:
python consulta_nif.py 509442013 | Tee-Object -FilePath temp.json | python importar_nif_sqlite.py
```

**Bash (WSL/Git Bash):**

```bash
python consulta_nif.py 509442013 | tee resultado.json | python importar_nif_sqlite.py
```

### 6.7 Help Python (v1.2.0)

```powershell
python -c "import consulta_nif; help(consulta_nif.validar_nif)"
python -c "import consulta_nif; help(consulta_nif.consultar_nif)"
python -c "from utils.cache_validator import is_nif_recente, registar_ignorado; help(is_nif_recente)"
python -c "from utils.error_handler import classificar_erro, tratar_erro; help(tratar_erro)"
python -c "from config.config import get_config; help(get_config)"
python -m pydoc consulta_nif
python -m pydoc utils.cache_validator
```

Ver `docs/api/help.md` — transcrições verificadas.

---

## 7. Esquemas de Base de Dados

### 7.1 Visão comparativa v1.2.0

| Aspeto | `nif_pt` 5c | `nif_api_erros` 15c | `nif_ignorados` 6c |
|--------|-------------|---------------------|-------------------|
| Ficheiro | `data/nif_pt.db` SQLite WAL | `data/nif_pt.db` | `data/nif_pt.db` |
| Cols | 5 (`id, nif, dados, data_consulta, run_id`) | 15 (14 + `run_id`) | 6 (`id, nif, data_tentativa, data_ultima_consulta, dias_desde_ultima, motivo`) |
| PK | `id AUTOINCREMENT` | `id AUTOINCREMENT` | `id AUTOINCREMENT` |
| Histórico | Sim (sem `UNIQUE nif`) | Sim (`resolvido`) | Sim |
| DDL | `importar_nif_sqlite.py:55` | `utils/error_handler.py:46` | `utils/cache_validator.py:43` |
| Índices | `idx_nif_pt_run_id` | `idx_nif_api_erros_*` + `idx_run_id` | `idx_nif_ignorados_nif` + `idx_nif_ignorados_data` |
| Uso | JSON bruto + `run_id` | Auditoria `rate_limit_*` + `run_id` | Cache `is_nif_recente` + `registar_ignorado` |

> Sem Azure desde v1.2.0 (removido `pyodbc`, `ODBC Driver 18`, `kiwa-pt-operations/stg_nunotome`, `sql/0*`).

### 7.2 SQLite — `nif_pt` (5c: 4+`run_id`)

```sql
CREATE TABLE IF NOT EXISTS nif_pt (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nif           INTEGER NOT NULL,
    dados         TEXT NOT NULL,          -- json.dumps(resultado, ensure_ascii=False) inclui run_id
    data_consulta TEXT NOT NULL DEFAULT (datetime('now')),
    run_id        TEXT                    -- UUID v4 da execução (utils/run_id.py:41)
);
CREATE INDEX IF NOT EXISTS idx_nif_pt_run_id ON nif_pt(run_id);
-- Migração idempotente (importar_nif_sqlite.py:102): PRAGMA table_info -> ALTER TABLE ADD COLUMN run_id TEXT
```

### 7.3 SQLite — `nif_api_erros` (15c: 14+`run_id`)

```sql
-- SQLite (utils/error_handler.py:46)
CREATE TABLE IF NOT EXISTS nif_api_erros (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nif           INTEGER,
    data_erro     TEXT NOT NULL DEFAULT (datetime('now')),
    tipo_erro     TEXT NOT NULL,          -- rate_limit_minute/hour/day/month/paid/unknown
    codigo_erro   TEXT,                   -- result da API
    mensagem      TEXT,                   -- message da API
    left_month    INTEGER, left_day INTEGER, left_hour INTEGER,
    left_minute   INTEGER, left_paid INTEGER,
    dados_json    TEXT NOT NULL,          -- JSON completo
    acao          TEXT,                   -- retry_60s / abort_day / none
    run_id        TEXT,                   -- UUID v4 da execução (utils/run_id.py:41)
    resolvido     INTEGER NOT NULL DEFAULT 0
);
-- Índices: idx_nif_api_erros_nif, idx_nif_api_erros_tipo, idx_nif_api_erros_run_id
-- Migração idempotente (utils/error_handler.py:153): PRAGMA table_info -> ALTER TABLE ADD COLUMN run_id TEXT
```

### 7.4 SQLite — `nif_ignorados` (6c) — novo v1.2.0

```sql
-- SQLite (utils/cache_validator.py:43)
CREATE TABLE IF NOT EXISTS nif_ignorados (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    nif                     INTEGER NOT NULL,
    data_tentativa          TEXT NOT NULL DEFAULT (datetime('now')),
    data_ultima_consulta    TEXT,         -- data_consulta da linha mais recente em nif_pt
    dias_desde_ultima       INTEGER,      -- (now - data_ultima).days
    motivo                  TEXT NOT NULL DEFAULT 'cache_recente'
);
CREATE INDEX IF NOT EXISTS idx_nif_ignorados_nif ON nif_ignorados(nif);
CREATE INDEX IF NOT EXISTS idx_nif_ignorados_data ON nif_ignorados(data_tentativa);
-- DDL via _get_connection() (utils/cache_validator.py:126) + init_cache_tables() (consulta_nif.py:536)
-- Nome configurável via cache_tabela_ignorados (sanitizado alnum+_)
```

| # | Coluna | Tipo | Default | Descrição |
|---|--------|------|---------|-----------|
| 1 | `id` | `INTEGER PK` | `AUTOINCREMENT` | PK WAL |
| 2 | `nif` | `INTEGER` | — | NIF ignorado |
| 3 | `data_tentativa` | `TEXT` | `datetime('now')` | Timestamp tentativa ignorada |
| 4 | `data_ultima_consulta` | `TEXT` | `NULL` | `data_consulta` mais recente em `nif_pt` (`is_nif_recente` `:314`) |
| 5 | `dias_desde_ultima` | `INTEGER` | `NULL` | `diff.days` (`registar_ignorado` `:362`) |
| 6 | `motivo` | `TEXT` | `'cache_recente'` | Motivo (único default) |

* `PRAGMA journal_mode=WAL` + `executescript(DDL)` + 2 índices em `_get_connection()`; `init_cache_tables()` idempotente (fail-open).
* `is_nif_recente(nif, dias)` → `SELECT data_consulta FROM nif_pt WHERE nif=? ORDER BY datetime(data_consulta) DESC LIMIT 1` + `_parse_data_consulta` (`YYYY-MM-DD HH:MM:SS`/`ISO`/`Z`) + `total_seconds/86400 < dias`.

Ver `docs/database/schema.md` para catálogo completo + ER Mermaid 5/15/6c.

---

## 8. Referência CLI

| Comando | Argumentos | stdin | stdout | stderr | Exit |
|---------|------------|-------|--------|--------|------|
| `consulta_nif.py` | `<NIF>` 9 dígitos `[--run-id UUID]` | — | JSON + `run_id` + opcional `ignorado/motivo/data_ultima_consulta/cache_antiguidade_dias` | `<<nif-pt>>` BOX/TAG/TIMING `[cache][run]` | `0` ok/ignorado, `1` erro |
| `importar_nif_sqlite.py` | `[--run-id UUID]` | JSON + `run_id`/`ignorado` | — | `BOX Guardado em SQLite run_id` / `BOX NIF ignorado - skip SQLite` | `0` ok/skip, `1` erro |

### 8.1 `consulta_nif.py`

```
Uso: python consulta_nif.py <NIF> [--run-id <uuid>]
Exemplo: python consulta_nif.py 509442013
         python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000
         python consulta_nif.py 509442013 --run-id=550e8400-e29b-41d4-a716-446655440000
```

* `TIMEOUT 10s` + `max_tentativas_global 5` + `retry 60s/3600s` via `error_handler` com `run_id` + `cache is_nif_recente` antes de API.
* `run_id` UUID v4 gerado por `utils/run_id.py:41` + `ensure_run_id(CLI>payload>ctx>gen)` (`consulta_nif.py:481`); `remove_run_id_args` mantém `isdigit` posicional; `--run-id` suportado como `UUID` e `=UUID` (`utils/run_id.py:132`).
* `help(consulta_nif.validar_nif)` / `help(utils.cache_validator.is_nif_recente)` / `help(utils.run_id.generate_run_id)` para PEP 257.

### 8.2 `importar_nif_sqlite.py`

```
Uso: python consulta_nif.py 509442013 | python importar_nif_sqlite.py [--run-id UUID]
     python importar_nif_sqlite.py < ficheiro.json
     python importar_nif_sqlite.py --run-id 550e8400-e29b-41d4-a716-446655440000 < ficheiro.json
```

* Precedência `run_id`: `CLI --run-id` > `JSON payload run_id` > `ContextVar` > `uuid4` (`importar_nif_sqlite.py:185` `ensure_run_id`); herança automática via JSON é o recomendado.
* Se `resultado.get("ignorado")==True` → `INFO [cache] skip INSERT` + `BOX NIF ignorado - skip SQLite` + `exit 0` sem `INSERT`.

---

## 9. Referência de Dados e JSON

### 9.1 Exemplo JSON sucesso (509442013, 2026-09-10) — com `run_id`

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
    "pc4": "4000", "pc3": "457", "city": "Porto",
    "place": { "address": "Rua ...", "pc4": "4000", "pc3": "457", "city": "Porto" },
    "geo": { "region": "Porto", "county": "Porto", "parish": "Cedofeita" },
    "contacts": { "email": "info@nex.pt", "phone": "220 198 228", "website": "www.nex.pt", "fax": "224 905 459" },
    "structure": { "nature": "UNI", "capital": "248000.00", "capital_currency": "EUR" },
    "cae": ["62010", "63120", "62020", "46510"],
    "racius": "https://www.racius.com/nexperience-lda/",
    "portugalio": null
  },
  "nif_valido_formato": true,
  "creditos": { "used": "free", "left": [] },
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```
`run_id` gerado por `utils/run_id.py:41` e propagado via `stdout` → `stdin` importador.

### 9.2 Exemplo JSON cache hit — `ignorado:true` (novo v1.2.0)

```json
{
  "nif": "509442013",
  "valido": true,
  "fonte": null,
  "erro": null,
  "dados": null,
  "nif_valido_formato": null,
  "creditos": null,
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "ignorado": true,
  "motivo": "cache_recente",
  "data_ultima_consulta": "2026-09-10 12:00:00",
  "cache_antiguidade_dias": 30
}
```

* `ignorado: true` distingue cache hit de erro; `motivo: "cache_recente"` (default `nif_ignorados.motivo`); `data_ultima_consulta` é `data_consulta` mais recente em `nif_pt` (`utils/cache_validator.py:314`); `cache_antiguidade_dias` é `config.yaml:15` janela (30).
* Persistido em `nif_ignorados` 6c com `dias_desde_ultima` + `motivo` (`utils/cache_validator.py:329` `registar_ignorado`); `importar_nif_sqlite.py:194` não insere `nif_pt`.
* `exit 0` (não erro) — `importar_nif_sqlite.py` faz skip mas com `exit 0`.

### 9.3 Exemplo JSON erro rate-limit (com `run_id`)

```json
{
  "nif": "509442013",
  "valido": true,
  "fonte": "nif.pt",
  "erro": "Limit per minute exceeded",
  "dados": {
    "result": "error",
    "message": "Limit per minute exceeded",
    "credits": { "left": { "minute": 0, "hour": 9, "day": 99, "month": 999 } }
  },
  "tipo_erro": "rate_limit_minute",
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Persistido em `nif_api_erros` 15c com `run_id` e `acao=retry_60s` (`utils/error_handler.py:368` `guardar_erro(...,run_id)`) e retry automático 60s (max 3).

### 9.4 Exemplo JSON `No records` (com `run_id`)

```json
{
  "nif": "999999999",
  "valido": false,
  "fonte": "nif.pt",
  "erro": "No records found",
  "dados": { "result": "No records found", "nif_validation": false },
  "tipo_erro": "generic_error",
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 9.5 Caso `creditos.left`

* **Pago:** `{"month":999,"day":99,"hour":9,"minute":0,"paid":0}` → `dados.creditos`.
* **Free (real 2026-09-10):** `[]` → `[]` em JSON bruto (sem crash).

### 9.6 Validação Mod-11

```python
total = sum(int(d) * (9 - i) for i, d in enumerate(nif[:8]))
resto = total % 11
digito = 0 if resto in (0, 1) else 11 - resto
return digito == int(nif[8])
```

`help(consulta_nif.validar_nif)` para docstring completa.

### 9.7 Campo `run_id` (v1.1.0)

* **Tipo:** `str` UUID v4 `xxxxxxxx-xxxx-4xxx-xxxx-xxxxxxxxxxxx` (36c, 4 hífens) gerado por `utils/run_id.py:41`.
* **Presença:** sempre em `stdout` JSON (sucesso, erro, `ignorado`).
* **Propagação:** `stdout` JSON `run_id` → `stdin` importador via `ensure_run_id(CLI>payload>ctx>gen)`; precedência `CLI --run-id` > `payload` > `ContextVar` > `uuid4`.
* **Persistência:** `nif_pt.run_id TEXT` + `nif_api_erros.run_id TEXT` + índices `run_id`.

### 9.8 Campo `ignorado` (v1.2.0)

* **Tipo:** `bool` (`true` se cache hit) — só quando `cache_ativo==true` e `is_nif_recente(nif, dias)==True`.
* **Campos adicionais quando `ignorado==true`:** `motivo: "cache_recente"`, `data_ultima_consulta: str` (ISO `YYYY-MM-DD HH:MM:SS` de `nif_pt.data_consulta`), `cache_antiguidade_dias: int` (de `config.yaml:15`).
* **Comportamento:** `consulta_nif.py` faz `sys.exit(0)` sem `requests.get`; `importar_nif_sqlite.py:194` faz `sys.exit(0)` sem `INSERT` em `nif_pt` (mas `nif_ignorados` já tem `INSERT`).
* **Desligar:** `config.yaml` `cache_ativo: false` ou `cache_antiguidade_dias: 0` ou `DELETE FROM nif_ignorados/nif_pt WHERE nif=...`.

---

## 10. Códigos de Erro e Saída

| `erro` / `ignorado` | `tipo_erro` / `motivo` | `exit` | Significado | Ação | Retry/Cache |
|--------|-------------|--------|-------------|------|-------------|
| `null` | — | `0` | Sucesso (cache miss) | `INSERT nif_pt` 5c | — |
| `ignorado:true` | `motivo:cache_recente` | `0` | Cache hit — NIF consultado há < `cache_antiguidade_dias` | `INSERT nif_ignorados` 6c, sem API, `importar` skip | Cache `nif_ignorados` |
| `Uso: ... <NIF>` | — | `1` | Sem argv | — | — |
| `NIF deve conter apenas dígitos` | — | `1` | `isdigit` fail | — | — |
| `NIF-PT-KEY não encontrada` | — | `1` | sem chave | — | — |
| `Timeout na consulta` | — | `1` | `requests.Timeout` | `retry` | `sleep 60s` se `<max_global` |
| `Erro de rede: ...` | — | `1` | `RequestException` | `retry` | idem |
| `Resposta inválida (não JSON)` | — | `1` | `JSONDecodeError` | — | — |
| `Limit per minute` | `rate_limit_minute` | `1` | quota minuto | `retry_60s` | 60s, max 3 + global 5 |
| `Limit per hour` | `rate_limit_hour` | `1` | quota hora | `retry_3600s` | 3600s, max 2 |
| `Limit per day` | `rate_limit_day` | `1` | quota dia | `abort_day` BOX fatal | 0 (abort) |
| `Limit per month` | `rate_limit_month` | `1` | quota mês | `abort_month` BOX fatal | 0 |
| `Limit per ... paid` | `rate_limit_paid` | `1` | sem créditos pagos | `abort_paid` | 0 |
| `No records found` / `error` | `generic_error` | `1` | sem registo público | `none` auditoria | 0 |
| `Nenhum JSON no stdin` | — | `1` | pipe vazio | — | — |

`ignorado:true` tem `exit 0` (não erro) mas `importar_nif_sqlite.py` não insere `nif_pt`; `tipo_erro` só em erros classificados, `motivo` só em ignorados.

---

## 11. Logging

### 11.1 Configuração v1.2.0 (cache + run_id)

`Logging/logging_orchestrator.py` (580L) — **integrado** em todos os scripts (`setup_logging()`) com TAG `[cache][run]`:

* `LOG_LEVEL_GLOBAL/FILE/CONSOLE = INFO` · `FILE_ULTRA_DEBUG/CONSOLE_ULTRA_DEBUG = True`.
* `LOG_FOLDER='log_files'`, `LOG_OUTPUT_FILE='log_files/nif_pt.log'`, prefixo `<<nif-pt>>`.
* `LOG_FORMAT_FILE='<<nif-pt>> %(asctime)s - %(name)s - %(levelname)s - %(message)s'` + ultra-debug `%(filename)s - %(funcName)s - %(lineno)d` em `DEBUG`.
* `RotatingFileHandler` 10 MB / 5000 recs / 10 backups (`logging_orchestrator.py:64`).

### 11.2 Livro de estilo R1–R9

| # | Estilo | Char | Width | Nível | Uso |
|---|--------|------|-------|-------|-----|
| 1 | `BANNER_APP_START/END` | `=` | 49 | INFO | `nif-pt consulta_nif a iniciar/finalizado` |
| 3 | `BANNER_SECTION` | `-` | 49 | INFO | `Inserir staging` |
| 5 | `BANNER_FUNCTION` | `~` | 49 | DEBUG | `validar_nif()` `is_nif_recente()` `registar_ignorado()` |
| 6 | `TAG` | `[tag]` | — | herda | `[api][valid][cfg][db][sqlite][io][cache][erro][rate-limit][cli][run]` |
| 7 | `SEPARATOR` | `-` | 49 | DEBUG | `---------------------------------------------------` |
| 8 | `BOX` | `-\|` | 49 | INFO | `| NIF : 509442013 |` `| NIF ignorado - cache recente |` `| NIF ignorado - skip SQLite |` `| run_id : 550e8400-... |` |
| 9 | `TIMING` | `%.2fs` | — | INFO/DEBUG | `Aplicação concluída em 0.92s` `is_nif_recente -> 0.02s` |

Regras: `R1 WIDTH=49 ≤79`, `R4 [tag] lowercase`, `R6 f"{' title ':=^49}"`, `R9 %.2fs` via `time.perf_counter()`.

**Nova TAG v1.2.0:** `[cache]` — `is_nif_recente` (`utils/cache_validator.py:304`), `registar_ignorado` (`:384`), `consulta_nif.py:546` `NIF ... ignorado`, `importar_nif_sqlite.py:195` `... skip INSERT`.

### 11.3 Exemplo de saída — cache hit

```
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ========= nif-pt consulta_nif a iniciar =========
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - [run] run_id=550e8400-e29b-41d4-a716-446655440000
<<nif-pt>> 2026-09-10 02:15:32 - utils.cache_validator - INFO - [cache] NIF 509442013 ultima=2026-09-10 12:00:00 dias_desde=0 antiguidade=30 recente=True (0.02s)
<<nif-pt>> 2026-09-10 02:15:32 - utils.cache_validator - INFO - [cache] Ignorado registado id=1 nif=509442013 ultima=2026-09-10 12:00:00 dias_desde=0 (0.01s)
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - [cache] NIF 509442013 ignorado - ultima consulta 2026-09-10 12:00:00 dentro de 30 dias
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ---------------------------------------------------
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | NIF ignorado - cache recente                 |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | NIF         : 509442013                    |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | Ultima      : 2026-09-10 12:00:00            |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | Antiguidade : 30 dias                      |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | run_id      : 550e8400-e29b-41d4-a716-...  |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ---------------------------------------------------
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - [run] run_id=550e8400-e29b-41d4-a716-446655440000
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - Aplicação concluída em 0.05s
```

Ver `docs/guides/logging.md` + `docs/technical.md` §11 (logging) + §10c (cache).

---

## 12. Exemplos Práticos (PowerShell & Bash)

### 12.1 Consultar + SQLite

| PowerShell | Bash |
|------------|------|
| `python consulta_nif.py 509442013 \| python importar_nif_sqlite.py` | idem |

### 12.2 Cache hit — 2ª consulta <30d

| PowerShell | Bash |
|------------|------|
| `python consulta_nif.py 509442013` → `{"ignorado":true,...}` | idem |
| `python consulta_nif.py 509442013 \| python importar_nif_sqlite.py` → `skip INSERT` | idem |

### 12.3 Ambos (pipe)

| PowerShell | Bash |
|------------|------|
| `$j = python consulta_nif.py 509442013`<br>`$j \| python importar_nif_sqlite.py` | `python consulta_nif.py 509442013 \| python importar_nif_sqlite.py` |

### 12.4 Batch

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
while read nif; do echo "A consultar $nif"; python consulta_nif.py "$nif" | python importar_nif_sqlite.py; sleep 1; done < nifs.txt
```

### 12.5 Histórico SQLite (com `run_id` + `cache`)

```powershell
python -c "import sqlite3,json; conn=sqlite3.connect('data/nif_pt.db'); [print(f'{r[0]}: {r[1]} - {json.loads(r[2])[\"dados\"][\"title\"]} run_id={r[3][:8]}') for r in conn.execute('SELECT id,nif,dados,run_id FROM nif_pt ORDER BY data_consulta DESC LIMIT 5')]"
sqlite3 data/nif_pt.db "SELECT id,nif,substr(run_id,1,8),data_consulta FROM nif_pt ORDER BY data_consulta DESC LIMIT 5;"
sqlite3 data/nif_pt.db "SELECT tipo_erro,COUNT(*) FROM nif_api_erros GROUP BY tipo_erro;"
sqlite3 data/nif_pt.db "SELECT run_id, COUNT(*) FROM nif_pt GROUP BY run_id ORDER BY data_consulta DESC LIMIT 5;"
sqlite3 data/nif_pt.db "SELECT nif, data_tentativa, data_ultima_consulta, dias_desde_ultima FROM nif_ignorados ORDER BY data_tentativa DESC LIMIT 5;"
sqlite3 data/nif_pt.db "SELECT COUNT(*) AS sucessos FROM nif_pt; SELECT COUNT(*) AS ignorados FROM nif_ignorados; SELECT COUNT(*) AS erros FROM nif_api_erros;"
```

### 12.6 Validar sem créditos + `cache` + `run_id`

```powershell
python -c "from consulta_nif import validar_nif; print(validar_nif('509442013'))"  # True
python -c "from utils.cache_validator import is_nif_recente; print(is_nif_recente('509442013', dias=30))"
python -c "from utils.cache_validator import _parse_data_consulta; print(_parse_data_consulta('2026-09-10 12:00:00'))"
python -c "from utils.run_id import generate_run_id, ensure_run_id; print(generate_run_id()); print(ensure_run_id(payload_value='550e8400-e29b-41d4-a716-446655440000'))"
python consulta_nif.py 509442013 --run-id 550e8400-e29b-41d4-a716-446655440000 | ConvertFrom-Json | Select-Object nif, run_id, ignorado, motivo
```

---

## 13. Resolução de Problemas (Troubleshooting)

### 13.1 `NIF-PT-KEY não encontrada`

1. `Test-Path config\.env` + `Get-Content config\.env` → deve ter `NIF-PT-KEY=xxxxx` com hífen, sem espaços.
2. `os.getenv("NIF-PT-KEY")` em `config.py:120` — `NIF_PT_KEY` não funciona.
3. Solicitar chave em http://www.nif.pt/contactos/api/.

### 13.2 `Limit per minute/hour` — rate-limit com retry

* `utils/error_handler.py:515` aguarda `60s` (minuto, max 3) ou `3600s` (hora, max 2) com limite global 5. Log: `[rate-limit] Limite por minuto nif=... espera 60s retry tipo 1/3 global 1/5`.
* Ver `SELECT * FROM nif_api_erros WHERE tipo_erro='rate_limit_minute' ORDER BY data_erro DESC` + `log_files/nif_pt.log`.

### 13.3 `Limit per day/month` — quota fatal

* `max_tentativas_dia/mes = 0` → `abort` imediato + BOX `Erro fatal - quota diária/mensal excedida` + `exit 1`.
* Persistido com `acao=abort_day/month` — consultar `nif_api_erros`.

### 13.4 `No records found`

NIF válido sem registo público — não é erro de código; `importar_nif_sqlite.py` não insere `nif_pt` mas `nif_api_erros` com `generic_error`; `exit 1`.

### 13.5 `database is locked` (SQLite)

`importar_nif_sqlite.py:95` / `utils/cache_validator.py:142` `PRAGMA journal_mode=WAL` já mitiga; se persistir: `PRAGMA busy_timeout=5000` ou serializar writes.

### 13.6 Validação Mod-11 não bloqueia request

`validar_nif()` só afeta `valido`; `main()` só valida `isdigit`. `123456789` (dígito errado) faz `is_nif_recente` check + request e gasta crédito (se fora da janela). Filtrar antes:

```powershell
python -c "from consulta_nif import validar_nif; import sys; sys.exit(0 if validar_nif('123456789') else 1)" -and python consulta_nif.py 123456789
```

### 13.7 `NIF ignorado - cache recente` — não é erro

* É **cache hit** — NIF já em `nif_pt` há < `cache_antiguidade_dias` (30d default). `exit 0`, sem API, regista `nif_ignorados`.
* Para forçar refresh: `config.yaml` → `cache_ativo: false` ou `cache_antiguidade_dias: 0` ou `DELETE FROM nif_pt WHERE nif=509442013; DELETE FROM nif_ignorados WHERE nif=...;`.
* Auditoria: `SELECT nif, data_tentativa, data_ultima_consulta, dias_desde_ultima FROM nif_ignorados WHERE nif=509442013 ORDER BY data_tentativa DESC;`.
* `importar_nif_sqlite.py` faz `skip INSERT` quando recebe `ignorado:true` — log `[cache] ... skip INSERT`.

### 13.8 `tee` não funciona em PowerShell

`tee >( )` é Bash; em PS usar variável `$json` ou `Tee-Object`.

### 13.9 `ModuleNotFoundError: yaml`

`pip uninstall yaml -y; pip install pyyaml python-dotenv` ou `pip install -r requirements.txt` (fix v1.0.0; v1.2.0 sem `pyodbc`).

---

## 14. FAQ

**1. Custo?** Free limitado (`credits.left: []`); paid com `left: {month/day/hour/minute/paid}`.

**2. Créditos?** `creditos.left` dict se `paid`, `[]` se `free`.

**3. SQLite cache?** `nif_ignorados` 6c audita `is_nif_recente` → se `recente==True` evita `GET` e regista `ignorado`; `importar_nif_sqlite.py` faz skip.

**4. Mod-11?** `Σ d*(9-i)%11 → 0 se resto 0/1 senão 11-resto` == `d[8]` (`consulta_nif.py:99`, `help(validar_nif)`).

**5. Batch?** Sim, `sleep 1` + retry automático `60s/3600s` + cache evita re-pedido <30d; cada iteração tem `run_id` único — agrupar por `run_id`.

**6. `nif_api_erros` vs `nif_ignorados`?** `nif_api_erros` 15c quota/erros API; `nif_ignorados` 6c cache hit (sem API) — ambas em `data/nif_pt.db` WAL.

**7. `main.py`?** `92L` `ensure_run_id()` por execução + stub `BANNER+BOX`; futuro `cli.py --nif --to sqlite --no-cache`.

**8. Help Python?** `help(consulta_nif.validar_nif)`, `help(utils.cache_validator.is_nif_recente)`, `help(utils.run_id.generate_run_id)` (ver `docs/api/help.md`).

**9. Histórico?** `SELECT * FROM nif_pt ORDER BY data_consulta DESC`; `SELECT * FROM nif_ignorados ORDER BY data_tentativa DESC` (cache); filtrar por `WHERE run_id='...'` para uma execução.

**10. `run_id`?** UUID v4 por execução (`utils/run_id.py:41`); `python consulta_nif.py 509442013 --run-id <uuid>` determinístico; propagação `CLI>payload>ctx>gen` via JSON `run_id`.

**11. `cache`?** `config.yaml:15` `cache_ativo: true`, `cache_antiguidade_dias: 30`, `cache_tabela_ignorados: "nif_ignorados"`; `python -c "from utils.cache_validator import is_nif_recente; print(is_nif_recente('509442013', 30))"`; ver `docs/technical.md` §10c.

---

## 15. Anexos

### 15.1 Glossário

Ver [docs/glossary.md](docs/glossary.md). Termos: NIF, Mod-11, CAE, WAL, `creditos.left`, `nif_valido_formato`, `get_config`, `RotatingFileHandler`, `BOX/TAG/TIMING`, `rate_limit_*`, ADR, C4, `run_id`, `ContextVar`, `ensure_run_id`, `is_nif_recente`, `registar_ignorado`, `nif_ignorados`, `cache_recente`, `ignorado`.

### 15.2 Estrutura de ficheiros (v1.2.0)

```
nif-pt/
├── consulta_nif.py               # 626L — validar + cache is_nif_recente + GET + retry per-tipo+global + run_id + --run-id + BOX cache
├── importar_nif_sqlite.py        # 285L — JSON → SQLite WAL 5c + early skip ignorado + run_id + --run-id + migração
├── utils/cache_validator.py      # 407L — DDL nif_ignorados 6c + 2 índices + is_nif_recente + registar_ignorado + init_cache_tables
├── utils/run_id.py               # 191L — generate_run_id UUID v4 + ContextVar + ensure_run_id + --run-id parse
├── utils/error_handler.py        # 806L — classificar + tratar(...,run_id) + guardar(...,run_id) + init 15c run_id
├── main.py                       # 92L — ensure_run_id por execução + stub
├── Logging/logging_orchestrator.py # 580L — R1-R9, <<nif-pt>>, 10MB/5000/10, TAG [cache][run]
├── config/config.py              # 134L — get_config() + *** + cache_* documentado
├── config/config.yaml            # 31L — default 14 chaves (11 resiliência + 3 cache) + 2 blocos
├── docs/technical.md             # v1.2.0 — C4 + sequência cache + ER 5/15/6c + catálogo + ADRs (ADR-010 cache)
├── docs/api/help.md              # help() verificado (validar_nif, is_nif_recente, tratar_erro, generate_run_id)
├── docs/architecture/            # C4 + diagramas Mermaid v1.2.0 + ADR-009/010
├── docs/database/schema.md       # ER 5/15/6c + nif_ignorados 6c + índices cache
├── docs/api/nif-pt-api.md        # contrato nif.pt + payload ignorado + cache
├── data/nif_pt.db                # WAL, ignorado (auto-cria nif_ignorados)
├── log_files/nif_pt.log          # RotatingFileHandler, ignorado (BOX cache/run_id)
├── requirements.txt              # requests, pyyaml, dotenv (sem pyodbc)
├── README.md                     # porta de entrada v1.2.0
├── CHANGELOG.md                  # v1.2.0
└── MANUAL.md                     # este ficheiro
```

### 15.3 Changelog resumido

Ver [CHANGELOG.md](CHANGELOG.md) — `v1.2.0` adiciona `cache_validator` + remove Azure; `v1.1.0` adiciona `run_id`; `v1.0.0` promove `beta` com `error_handler` + `logging_orchestrator` + `max_tentativas_*`.

### 15.4 Referências

* `nif.pt` API: `GET http://www.nif.pt/?json=1&q=<NIF>&key=<KEY>` (`consulta_nif.py:272`)
* `config/config.py:53` `get_config()` · `utils/cache_validator.py:225` `is_nif_recente` / `:329` `registar_ignorado` / `:163` `init_cache_tables` · `utils/error_handler.py:515` `tratar_erro(...,run_id)` · `utils/run_id.py:41` `generate_run_id` / `:87` `ensure_run_id` · `Logging/logging_orchestrator.py:226` `setup_logging()` + TAG `[cache][run]`
* `utils/cache_validator.py:43` DDL `nif_ignorados` 6c · `importar_nif_sqlite.py:194` early skip `ignorado` · `consulta_nif.py:529` cache check
* [docs/technical.md](docs/technical.md) §10c cache · [docs/architecture/diagrams.md](docs/architecture/diagrams.md) · [docs/api/help.md](docs/api/help.md) · [docs/database/schema.md](docs/database/schema.md) 5/15/6c
