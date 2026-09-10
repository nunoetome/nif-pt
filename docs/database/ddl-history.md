# Histórico DDL — nif-pt

> Evolução de `sql/01_criar_tabelas.sql` (157L) por versão.

## v0.1.0-alpha (2026-06-26) — Fundação

* `stg_nunotome.nif_pt` — `nif BIGINT PK`, ~40 cols (`seo_url`, `title`, `place_*`, `geo_*`, `contacts_*`, `structure_*`, `cae`, `creditos_*`).
* `stg_nunotome.nif_pt_stg` — `PRIMARY KEY (nif, data_staging)`, `processado BIT DEFAULT 0`, `data_staging DEFAULT GETDATE()`.
* Estilo: `IF OBJECT_ID(...) IS NOT NULL DROP TABLE` destrutivo.

## v0.2.0-beta (2026-06-26) — Refactor

* **`b085cf2` feat:** `nif_pt_stg` → `id BIGINT IDENTITY(1,1) NOT NULL` + `CONSTRAINT pk_nif_pt_stg PRIMARY KEY CLUSTERED (id)`. Resolve colisão `nif+data_staging` no mesmo segundo.
* **`069f356` refactor:** SQLite `nif_pt` passa a 4 cols JSON (`id AUTOINCREMENT, nif, dados TEXT, data_consulta`); remove normalização SQLite.
* **`3821c03` refactor:** `config.yaml` 156→27L; DDL adiciona `IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name='stg_nunotome') EXEC('CREATE SCHEMA stg_nunotome')` (`01_criar_tabelas.sql:9`).

## Unreleased → v0.2.1

* Sem alteração DDL; `requirements.txt` fix apenas.

## Recomendação v0.3.0

```sql
-- Índice para MERGE
CREATE INDEX ix_nif_pt_stg_nif_processado
ON stg_nunotome.nif_pt_stg (nif, processado)
WHERE processado = 0;

-- Evitar DROP destrutivo: usar IF NOT EXISTS CREATE + ALTER
IF OBJECT_ID('stg_nunotome.nif_pt', 'U') IS NULL
    CREATE TABLE stg_nunotome.nif_pt (...);
```

Ver [schema.md](schema.md) para catálogo atual.
