# Histórico DDL — nif-pt v1.0.0

> Evolução de `sql/01_criar_tabelas.sql` (157L) + `sql/02_criar_tabela_erros.sql` (44L).

## v0.1.0-alpha (2026-06-26) — Fundação

* `stg_nunotome.nif_pt` — `nif BIGINT PK`, ~37c (`seo_url`, `title`, `place_*`, `geo_*`, `contacts_*`, `structure_*`, `cae`, `creditos_*`).
* `stg_nunotome.nif_pt_stg` — `PRIMARY KEY (nif, data_staging)`, `processado BIT DEFAULT 0`, `data_staging DEFAULT GETDATE()`.
* `IF OBJECT_ID(...) IS NOT NULL DROP TABLE` destrutivo.

## v0.2.0-beta (2026-06-26) — Refactor

* **`b085cf2`:** `nif_pt_stg` → `id BIGINT IDENTITY(1,1)` + `CONSTRAINT pk_nif_pt_stg PRIMARY KEY CLUSTERED (id)`.
* **`069f356`:** SQLite `nif_pt` → 4c JSON (`id AUTOINCREMENT, nif, dados TEXT, data_consulta`).
* **`3821c03`:** `config.yaml` 156→27L; DDL adiciona `IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name='stg_nunotome') EXEC('CREATE SCHEMA stg_nunotome')`.

## v1.0.0 (2026-09-10) — Stable

* **`d812901` + `cd83aa8`:** Nova tabela `stg_nunotome.nif_api_erros` (14c) — `sql/02_criar_tabela_erros.sql` (44L) — dual:
  * SQLite: `utils/error_handler.py:46` `DDL_ERROS` (`CREATE TABLE IF NOT EXISTS nif_api_erros` 14c + 2 índices) + `PRAGMA WAL`, `init_error_table()` idempotente.
  * Azure: `sql/02_criar_tabela_erros.sql:20` `CREATE TABLE stg_nunotome.nif_api_erros` (`BIGINT IDENTITY`, 3 índices `nif`/`tipo_erro`/`data_erro`).
* **`808f837`:** `config.yaml` 27→37L — adiciona 8 chaves de resiliência (`tempo_espera_minuto 60`, `tempo_espera_hora 3600`, `max_tentativas_global 5 / minuto 3 / hora 2 / dia 0 / mes 0 / paid 0`) + `timeout 1000→10s`, `retry_count 0→1`.
* **Sem breaking DDL** em `01_criar_tabelas.sql` (37c/40c mantidos); `02_criar_tabela_erros.sql` é aditivo.

## Recomendação v1.1

```sql
-- Índice para MERGE
CREATE INDEX ix_nif_pt_stg_nif_processado
ON stg_nunotome.nif_pt_stg (nif, processado) WHERE processado=0;

-- Evitar DROP destrutivo
IF OBJECT_ID('stg_nunotome.nif_pt', 'U') IS NULL
    CREATE TABLE stg_nunotome.nif_pt (...);
-- Para nif_api_erros: resolver pendentes
UPDATE stg_nunotome.nif_api_erros SET resolvido=1 WHERE tipo_erro='rate_limit_minute' AND resolvido=0;
```

Ver [schema.md](schema.md) para catálogo 37/40/14c atual.
