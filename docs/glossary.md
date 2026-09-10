# Glossário — nif-pt

| Termo | Definição |
|-------|-----------|
| **NIF** | Número de Identificação Fiscal — 9 dígitos, PT. Validado por Mod-11 (`consulta_nif.py:26`). |
| **Mod-11** | Algoritmo dígito de controlo AT: `Σ d[i]*(9-i) %11 → 0 se resto 0/1 senão 11-resto`. |
| **nif.pt** | Portal agregador `http://www.nif.pt` — fonte via `GET ?json=1&q=<NIF>&key=<KEY>` (`consulta_nif.py:48`). |
| **NIF-PT-KEY** | Chave API `nif.pt` (`.env`, `config.py:38` `os.getenv("NIF-PT-KEY")`). Com hífen — frágil. |
| **CAE** | Classificação Portuguesa de Atividades Económicas — `dados.cae` lista → `cae` CSV (`extrair_cae`). |
| **WAL** | Write-Ahead Logging — `PRAGMA journal_mode=WAL` em `importar_nif_sqlite.py:40` mitiga `database is locked`. |
| **ODBC** | Open Database Connectivity — `ODBC Driver 18 for SQL Server` (`config.yaml:26`), `pyodbc` (`importar_nif.py:20`). |
| **stg** | Staging — `stg_nunotome.nif_pt_stg` (40 cols, `id IDENTITY`, `processado`) staging para `nif_pt` (37 cols, PK `nif`). |
| **creditos.left** | Créditos API: `dict` (`month/day/hour/minute/paid`) se `paid`, `[]` se `free` (real 2026-09-10). |
| **nif_valido_formato** | `data.get("nif_validation")` da API → `BIT` em SQL, `bool` em JSON. |
| **get_config** | `config/config.py:17` funde `default` + bloco do script + `.env`. |
| **RotatingFileHandler** | Handler custom `Logging/logging_template.py:73` com rotação 10 MB / 5000 recs / 10 backups. |
| **BANNER/TAG/TIMING** | Estilos de log `logging_template.py:234` (9 estilos, `WIDTH=49`, `%.2fs` com `perf_counter`). |
| **ADR** | Architecture Decision Record — decisões em `docs/architecture/architecture.md` §6. |
| **C4** | Modelo C4 (Contexto, Contentores, Componentes) — `docs/architecture/architecture.md` §1-2. |
