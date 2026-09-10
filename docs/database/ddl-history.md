# Histórico DDL — nif-pt v1.2.0

> Evolução de `importar_nif_sqlite.py:55` (`nif_pt` 5c) + `utils/error_handler.py:46` (`nif_api_erros` 15c) + `utils/cache_validator.py:43` (`nif_ignorados` 6c). Sem Azure desde v1.2.0.

## v0.1.0-alpha (2026-06-26) — Fundação

* `stg_nunotome.nif_pt` — `nif BIGINT PK`, ~37c (`seo_url`, `title`, `place_*`, `geo_*`, `contacts_*`, `structure_*`, `cae`, `creditos_*`).
* `stg_nunotome.nif_pt_stg` — `PRIMARY KEY (nif, data_staging)`, `processado BIT DEFAULT 0`, `data_staging DEFAULT GETDATE()`.
* `IF OBJECT_ID(...) IS NOT NULL DROP TABLE` destrutivo.

## v0.2.0-beta (2026-06-26) — Refactor

* **`b085cf2`:** `nif_pt_stg` → `id BIGINT IDENTITY(1,1)` + `CONSTRAINT pk_nif_pt_stg PRIMARY KEY CLUSTERED (id)`.
* **`069f356`:** SQLite `nif_pt` → 4c JSON (`id AUTOINCREMENT, nif, dados TEXT, data_consulta`).
* **`3821c03`:** `config.yaml` 156→27L; DDL adiciona `IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name='stg_nunotome') EXEC('CREATE SCHEMA stg_nunotome')`.

## v1.0.0 (2026-09-10) — Stable

* **`d812901` + `cd83aa8`:** Nova tabela `nif_api_erros` (14c → 15c com `run_id` em v1.1.0) — dual SQLite/Azure:
  * SQLite: `utils/error_handler.py:46` `DDL_ERROS` (`CREATE TABLE IF NOT EXISTS nif_api_erros` 15c + 3 índices `nif`/`tipo_erro`/`run_id`/`data`) + `PRAGMA WAL`, `init_error_table()` idempotente.
  * Azure: `sql/02_criar_tabela_erros.sql:20` (removido em v1.2.0).
* **`808f837`:** `config.yaml` 27→37L — adiciona 8 chaves de resiliência (`tempo_espera_minuto 60`, `tempo_espera_hora 3600`, `max_tentativas_global 5 / minuto 3 / hora 2 / dia 0 / mes 0 / paid 0`) + `timeout 1000→10s`, `retry_count 0→1`.

## v1.1.0 (2026-09-11) — Rastreabilidade `run_id`

* **`feature/add_runid`:** Coluna `run_id TEXT` (SQLite) / `NVARCHAR(36)` (Azure) em `nif_pt` (5c), `nif_api_erros` (15c) + `sql/03_migracao_run_id.sql` (39L) idempotente `ALTER TABLE ... ADD run_id` + `CREATE INDEX ...run_id` para `nif_pt`/`nif_pt_stg`/`nif_api_erros`; SQLite migração runtime `PRAGMA table_info` → `ALTER TABLE ADD COLUMN` idempotente (`importar_nif_sqlite.py:102` / `utils/error_handler.py:153`).

## v1.2.0 (unreleased) — Cache + remoção Azure

* **Removido:** `importar_nif.py` (576L, `pyodbc` + 37c `mapear_registo`), `sql/01_criar_tabelas.sql` (169L), `sql/02_criar_tabela_erros.sql` (47L), `sql/03_migracao_run_id.sql` (39L), `pyodbc>=5.0.0` de `requirements.txt`, bloco `importar_nif` de `config/config.yaml`, `AZURE_USER`/`AZURE_PALAVRA_CHAVE` de `config/config.py` + `config/.env.example`.
* **Adicionado — `nif_ignorados` 6c (`utils/cache_validator.py:43`):**

  ```sql
  CREATE TABLE IF NOT EXISTS nif_ignorados (
      id                    INTEGER PRIMARY KEY AUTOINCREMENT,
      nif                   INTEGER NOT NULL,
      data_tentativa        TEXT NOT NULL DEFAULT (datetime('now')),
      data_ultima_consulta  TEXT,
      dias_desde_ultima     INTEGER,
      motivo                TEXT NOT NULL DEFAULT 'cache_recente'
  );
  CREATE INDEX IF NOT EXISTS idx_nif_ignorados_nif ON nif_ignorados(nif);
  CREATE INDEX IF NOT EXISTS idx_nif_ignorados_data ON nif_ignorados(data_tentativa);
  ```

  * Criada via `_get_connection()` (`utils/cache_validator.py:126`) com `PRAGMA WAL` + `executescript(DDL)` + 2 índices, idempotente; `init_cache_tables()` (`:163`) chamada por `consulta_nif.py:536`.
  * `config/config.yaml:15` adiciona `cache_ativo: true`, `cache_antiguidade_dias: 30`, `cache_tabela_ignorados: "nif_ignorados"`.

* **Inalterado:** `nif_pt` 5c (`id, nif, dados, data_consulta, run_id` + `idx_nif_pt_run_id`) — `importar_nif_sqlite.py:55`; `nif_api_erros` 15c — `utils/error_handler.py:46`.
* **Stack final:** só SQLite WAL `data/nif_pt.db` com 3 tabelas — sem `sql/` local, sem Azure.

## Recomendação v1.2.0

```sql
-- Auditoria cache
SELECT nif, data_ultima_consulta, dias_desde_ultima, motivo, data_tentativa
FROM nif_ignorados ORDER BY data_tentativa DESC LIMIT 20;

-- Histórico por NIF (última consulta vs tentativas ignoradas)
SELECT nif, data_consulta FROM nif_pt WHERE nif=509442013 ORDER BY datetime(data_consulta) DESC LIMIT 3;
SELECT COUNT(*) FROM nif_ignorados WHERE nif=509442013;

-- Limpar cache para forçar refresh (local dev)
DELETE FROM nif_ignorados WHERE nif=509442013;
-- ou desligar: config.yaml cache_ativo: false / cache_antiguidade_dias: 0

-- Verificar DDL
SELECT name, sql FROM sqlite_master WHERE type='table' AND name IN ('nif_pt','nif_api_erros','nif_ignorados');
SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='nif_ignorados';
```

Ver [schema.md](schema.md) para catálogo 5/15/6c atual.
