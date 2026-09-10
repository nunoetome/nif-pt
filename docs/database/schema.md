# Esquemas de Base de Dados — nif-pt v1.0.0

> Fonte: `sql/01_criar_tabelas.sql` (157L) + `sql/02_criar_tabela_erros.sql` (44L) + `importar_nif_sqlite.py:32` + `utils/error_handler.py:46` + `importar_nif.py:169` `colunas_tabela()`.

## 1. Visão Geral v1.0.0

```mermaid
erDiagram
    sqlite_nif_pt {
        INTEGER id PK
        INTEGER nif
        TEXT dados
        TEXT data_consulta
    }
    nif_api_erros {
        INTEGER id PK
        INTEGER nif
        TEXT data_erro
        TEXT tipo_erro
        TEXT codigo_erro
        TEXT mensagem
        INTEGER left_month
        INTEGER left_day
        INTEGER left_hour
        INTEGER left_minute
        INTEGER left_paid
        TEXT dados_json
        TEXT acao
        INTEGER resolvido
    }
    nif_pt {
        BIGINT nif PK
        BIT nif_valido_formato
        DATETIME2 data_consulta
        NVARCHAR title
        NVARCHAR cae
        INT creditos_left_minute
    }
    nif_pt_stg {
        BIGINT id PK
        BIGINT nif
        DATETIME2 data_staging
        BIT processado
        NVARCHAR title
    }
    nif_pt_stg ||--o{ nif_pt : "MERGE WHERE processado=0"
    sqlite_nif_pt ||--o{ nif_api_erros : "mesma DB WAL"
```

| BD | Tabela | Cols | PK | Histórico | Estratégia | DDL |
|----|--------|------|----|-----------|------------|-----|
| SQLite | `nif_pt` | 4 | `id AUTOINCREMENT` | Sim | JSON bruto | `importar_nif_sqlite.py:32` |
| SQLite | `nif_api_erros` | 14 | `id AUTOINCREMENT` | Sim | Auditoria | `utils/error_handler.py:46` |
| Azure | `nif_pt` | 37 | `nif` | Não (ouro) | 36c normalizadas | `sql/01_criar_tabelas.sql:21` |
| Azure | `nif_pt_stg` | 40 | `id IDENTITY` | Sim (`processado`) | Staging + merge | `sql/01_criar_tabelas.sql:93` |
| Azure | `nif_api_erros` | 14 | `id IDENTITY` | Sim (`resolvido`) | Auditoria | `sql/02_criar_tabela_erros.sql:20` |

## 2. SQLite — `nif_pt` (4c)

### 2.1 DDL (`importar_nif_sqlite.py:32`)

```sql
CREATE TABLE IF NOT EXISTS nif_pt (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nif           INTEGER NOT NULL,
    dados         TEXT NOT NULL,          -- json.dumps(resultado, ensure_ascii=False)
    data_consulta TEXT NOT NULL DEFAULT (datetime('now'))
);
```

| # | Coluna | Tipo | Nulo | Default | Descrição |
|---|--------|------|------|---------|-----------|
| 1 | `id` | `INTEGER` | `NOT NULL` | `AUTOINCREMENT` | PK WAL |
| 2 | `nif` | `INTEGER` | `NOT NULL` | — | NIF 9 dígitos |
| 3 | `dados` | `TEXT` | `NOT NULL` | — | JSON completo `resultado` |
| 4 | `data_consulta` | `TEXT` | `NOT NULL` | `datetime('now')` | `YYYY-MM-DD HH:MM:SS` (`datetime.now()` em `importar_nif_sqlite.py:118`) |

* `PRAGMA journal_mode=WAL` (`importar_nif_sqlite.py:50`) · `DB_PATH = Path(...) / cfg.get("db_path", "data/nif_pt.db")` (`:29`) · sem `UNIQUE(nif)` → histórico; último com `ORDER BY data_consulta DESC LIMIT 1` · `json_extract(dados, '$.dados.title')` (SQLite 3.38+).

## 3. SQLite/Azure — `nif_api_erros` (14c)

### 3.1 DDL SQLite (`utils/error_handler.py:46`)

```sql
CREATE TABLE IF NOT EXISTS nif_api_erros (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nif           INTEGER,
    data_erro     TEXT NOT NULL DEFAULT (datetime('now')),
    tipo_erro     TEXT NOT NULL,      -- rate_limit_minute/hour/day/month/paid/unknown/generic_error
    codigo_erro   TEXT,               -- result da API
    mensagem      TEXT,               -- message da API
    left_month    INTEGER, left_day INTEGER, left_hour INTEGER,
    left_minute   INTEGER, left_paid INTEGER,
    dados_json    TEXT NOT NULL,      -- JSON completo
    acao          TEXT,               -- retry_60s / retry_3600s / abort_day / abort_month / none
    resolvido     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_nif_api_erros_nif ON nif_api_erros(nif);
CREATE INDEX IF NOT EXISTS idx_nif_api_erros_tipo ON nif_api_erros(tipo_erro);
```

### 3.2 DDL Azure (`sql/02_criar_tabela_erros.sql:20`)

```sql
CREATE TABLE stg_nunotome.nif_api_erros (
    id            BIGINT IDENTITY(1,1) NOT NULL,
    nif           BIGINT NULL,
    data_erro     DATETIME2 NOT NULL DEFAULT GETDATE(),
    tipo_erro     NVARCHAR(50) NOT NULL,
    codigo_erro   NVARCHAR(50) NULL,
    mensagem      NVARCHAR(500) NULL,
    left_month    INT NULL, left_day INT NULL, left_hour INT NULL,
    left_minute   INT NULL, left_paid INT NULL,
    dados_json    NVARCHAR(MAX) NOT NULL,
    acao          NVARCHAR(50) NULL,
    resolvido     BIT NOT NULL DEFAULT 0,
    CONSTRAINT pk_nif_api_erros PRIMARY KEY CLUSTERED (id)
);
CREATE INDEX ix_nif_api_erros_nif ON stg_nunotome.nif_api_erros(nif);
CREATE INDEX ix_nif_api_erros_tipo ON stg_nunotome.nif_api_erros(tipo_erro);
CREATE INDEX ix_nif_api_erros_data ON stg_nunotome.nif_api_erros(data_erro);
```

### 3.3 Catálogo `nif_api_erros`

| Grupo | Colunas | Tipos | Fonte |
|-------|---------|-------|-------|
| Chave | `id`, `nif`, `data_erro`, `resolvido` | `BIGINT/INTEGER`, `DATETIME2/TEXT`, `BIT/INTEGER` | `nif`, `GETDATE()`/`datetime('now')`, `0` |
| Classificação | `tipo_erro`, `codigo_erro`, `mensagem`, `acao` | `NVARCHAR(50)/TEXT` | `classificar_erro()` + `tratar_erro()` |
| Quota | `left_month/day/hour/minute/paid` | `INT/INTEGER` | `data["credits"]["left"]` |
| Auditoria | `dados_json` | `NVARCHAR(MAX)/TEXT` | `json.dumps(data, ensure_ascii=False)` |

Consultas úteis:

```sql
-- Últimos erros por tipo
SELECT tipo_erro, COUNT(*) FROM nif_api_erros GROUP BY tipo_erro;
-- Rate-limit minuto com retry
SELECT nif, mensagem, left_minute, acao, data_erro FROM nif_api_erros WHERE tipo_erro='rate_limit_minute' ORDER BY data_erro DESC;
-- Por resolver
SELECT * FROM stg_nunotome.nif_api_erros WHERE resolvido=0;
UPDATE stg_nunotome.nif_api_erros SET resolvido=1 WHERE id=123;
```

## 4. Azure SQL — `nif_pt` (37c, PK `nif`)

### 4.1 DDL (`sql/01_criar_tabelas.sql:21`)

```sql
CREATE TABLE stg_nunotome.nif_pt (
    nif                     BIGINT NOT NULL,
    nif_valido_formato      BIT NULL,
    data_consulta           DATETIME2 NOT NULL DEFAULT GETDATE(),
    consulta_origem         NVARCHAR(50) NULL DEFAULT 'nif.pt',
    seo_url                 NVARCHAR(255) NULL, title NVARCHAR(500) NULL,
    alias                   NVARCHAR(500) NULL, status NVARCHAR(50) NULL,
    start_date              DATE NULL, activity NVARCHAR(MAX) NULL,
    place_address           NVARCHAR(500) NULL, place_pc4 NVARCHAR(10) NULL,
    place_pc3               NVARCHAR(10) NULL, place_city NVARCHAR(100) NULL,
    address                 NVARCHAR(500) NULL, pc4 NVARCHAR(10) NULL,
    pc3                     NVARCHAR(10) NULL, city NVARCHAR(100) NULL,
    geo_region              NVARCHAR(100) NULL, geo_county NVARCHAR(100) NULL,
    geo_parish              NVARCHAR(100) NULL,
    contacts_email          NVARCHAR(255) NULL, contacts_phone NVARCHAR(50) NULL,
    contacts_website        NVARCHAR(255) NULL, contacts_fax NVARCHAR(50) NULL,
    structure_nature        NVARCHAR(50) NULL, structure_capital DECIMAL(18,2) NULL,
    structure_capital_currency NVARCHAR(10) NULL,
    cae                     NVARCHAR(500) NULL, racius NVARCHAR(500) NULL,
    portugalio              NVARCHAR(500) NULL,
    creditos_used           NVARCHAR(50) NULL, creditos_left_month INT NULL,
    creditos_left_day       INT NULL, creditos_left_hour INT NULL,
    creditos_left_minute    INT NULL, creditos_left_paid INT NULL,
    CONSTRAINT pk_nif_pt PRIMARY KEY CLUSTERED (nif)
);
```

### 4.2 Catálogo por grupo (ver `docs/technical.md` §6 para condensado)

| Grupo | Colunas | Fonte API |
|-------|---------|-----------|
| Chave/controlo | `nif`, `nif_valido_formato`, `data_consulta`, `consulta_origem` | `resultado.nif`, `nif_validation`, `GETDATE()`, `fonte` |
| Identificação | `seo_url`, `title`, `alias`, `status`, `start_date`, `activity` | `dados.*` + `parse_date` |
| Morada place/address | `place_address/pc4/pc3/city`, `address/pc4/pc3/city` | `dados.place.*`, `dados.address` |
| Geo | `geo_region/county/parish` | `dados.geo.*` |
| Contactos | `contacts_email/phone/website/fax` | `dados.contacts.*` |
| Estrutura | `structure_nature/capital/capital_currency` | `dados.structure.*` + `parse_capital` |
| CAE | `cae` | `dados.cae` → `extrair_cae` `",".join` |
| Links | `racius`, `portugalio` | `dados.racius/portugalio` |
| Créditos | `creditos_used`, `left_month/day/hour/minute/paid` | `creditos.*` + `parse_int` |

*PK `nif` único → só ouro. `DROP TABLE IF EXISTS` destrutivo — ver ddl-history.*

## 5. Azure SQL — `nif_pt_stg` (40c, PK `id`)

### 5.1 DDL (`sql/01_criar_tabelas.sql:93`)

```sql
CREATE TABLE stg_nunotome.nif_pt_stg (
    id            BIGINT IDENTITY(1,1) NOT NULL,
    -- ... mesmos 37c do nif_pt mas com data_staging + processado ...
    data_staging  DATETIME2 NOT NULL DEFAULT GETDATE(),
    processado    BIT NOT NULL DEFAULT 0,
    CONSTRAINT pk_nif_pt_stg PRIMARY KEY CLUSTERED (id)
);
```

### 5.2 Diferença `nif_pt` vs `nif_pt_stg`

| Coluna | `nif_pt` | `nif_pt_stg` | Notas |
|--------|----------|--------------|-------|
| `id` | ❌ | ✅ `IDENTITY` | histórico |
| `data_staging` | ❌ | ✅ `GETDATE()` | timestamp staging |
| `processado` | ❌ | ✅ `DEFAULT 0` | flag merge |
| Restantes 37 | ✅ | ✅ | — |
| Restantes 36 (sem `data_consulta`) | — | — | `colunas_tabela()` omite `id/data_*` |

### 5.3 Coerência Python ↔ SQL

`importar_nif.py:169` `colunas_tabela()` → 36:

```python
["nif", "nif_valido_formato", "consulta_origem",
 "seo_url", "title", "alias", "status", "start_date", "activity",
 "place_address", "place_pc4", "place_pc3", "place_city",
 "address", "pc4", "pc3", "city",
 "geo_region", "geo_county", "geo_parish",
 "contacts_email", "contacts_phone", "contacts_website", "contacts_fax",
 "structure_nature", "structure_capital", "structure_capital_currency",
 "cae", "racius", "portugalio",
 "creditos_used", "creditos_left_month", "creditos_left_day",
 "creditos_left_hour", "creditos_left_minute", "creditos_left_paid"]
```

36 = 37 (`nif_pt`) -1 (`data_consulta` DEFAULT) = 40 (`nif_pt_stg`) -4 (`id`+`data_consulta`+`data_staging`+`processado`). **Match 100%**.

## 6. Tipos e Tamanhos

| Tipo | Uso | Exemplo |
|------|-----|---------|
| `NVARCHAR(10/50/100/255/500/MAX)` | Texto | `title NVARCHAR(500)` |
| `DECIMAL(18,2)` | Capital | `structure_capital` |
| `BIT` | Boolean | `nif_valido_formato`, `resolvido` |
| `INT` | Créditos/left | `creditos_left_month` |
| `DATE` | Data | `start_date` `2010-05-18` |
| `DATETIME2` | Timestamp | `data_consulta`, `data_erro` |
| `BIGINT` | NIF/ID | `nif` 9 dígitos, `id IDENTITY` |
| `TEXT/INTEGER` | SQLite | `dados TEXT`, `resolvido INTEGER` |

## 7. Estratégia Staging → Prod (futuro)

```sql
CREATE INDEX ix_nif_pt_stg_nif_processado
ON stg_nunotome.nif_pt_stg (nif, processado) WHERE processado=0;

MERGE stg_nunotome.nif_pt AS target
USING (SELECT * FROM stg_nunotome.nif_pt_stg WHERE processado=0) AS source
ON target.nif = source.nif
WHEN MATCHED THEN UPDATE SET title=source.title, data_consulta=GETDATE(), ...
WHEN NOT MATCHED THEN INSERT (nif, ...) VALUES (source.nif, ...);
UPDATE stg_nunotome.nif_pt_stg SET processado=1 WHERE processado=0;
```

## 8. Histórico DDL

Ver [ddl-history.md](ddl-history.md). `v1.0.0` adiciona `nif_api_erros` 14c (`sql/02_criar_tabela_erros.sql`).

## 9. Referências

* `sql/01_criar_tabelas.sql:8` `CREATE SCHEMA stg_nunotome`
* `importar_nif.py:103` `mapear_registo()` · `utils/error_handler.py:46` `DDL_ERROS`
* `docs/technical.md` §6 ER condensado
