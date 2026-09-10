# Glossário — nif-pt v1.0.0

| Termo | Definição | Ficheiro |
|-------|-----------|----------|
| **NIF** | Número de Identificação Fiscal — 9 dígitos PT. Validado por Mod-11 (`consulta_nif.py:48` `validar_nif()`). | `consulta_nif.py:48` |
| **Mod-11** | Algoritmo dígito controlo AT: `Σ d[i]*(9-i) %11 → 0 se resto 0/1 senão 11-resto` == `d[8]`. | `consulta_nif.py:60` |
| **nif.pt** | Portal agregador `http://www.nif.pt` — fonte `GET ?json=1&q=<NIF>&key=<KEY>` (`consulta_nif.py:98`). | `consulta_nif.py:98` |
| **NIF-PT-KEY** | Chave API `nif.pt` (`.env`, `config/config.py:55` `os.getenv("NIF-PT-KEY")`). Com hífen — frágil. | `config/config.py:55` |
| **CAE** | Classificação Portuguesa Atividades Económicas — `dados.cae` lista → `cae` CSV (`importar_nif.py:54` `extrair_cae()`). | `importar_nif.py:54` |
| **WAL** | Write-Ahead Logging — `PRAGMA journal_mode=WAL` em `importar_nif_sqlite.py:50` e `utils/error_handler.py:110` mitiga `database is locked`. | `importar_nif_sqlite.py:50` |
| **ODBC** | Open Database Connectivity — `ODBC Driver 18 for SQL Server` (`config.yaml:35`) + `pyodbc` (`importar_nif.py:24`). | `config/config.yaml:35` |
| **stg** | Staging — `stg_nunotome.nif_pt_stg` (40c, `id IDENTITY`, `processado`) staging para `nif_pt` (37c, PK `nif`). | `sql/01_criar_tabelas.sql:93` |
| **creditos.left** | Créditos API: `dict` (`month/day/hour/minute/paid`) se `paid`, `[]` lista vazia se `free` (real 2026-09-10). `or {}` em `importar_nif.py:116`. | `docs/api/nif-pt-api.md` §5 |
| **nif_valido_formato** | `data.get("nif_validation")` da API → `BIT` em SQL, `bool` em JSON. | `consulta_nif.py:264` |
| **get_config** | `config/config.py:30` funde `default` + bloco script + `.env` + `***` mascarado. | `config/config.py:30` |
| **RotatingFileHandler** | Handler custom `Logging/logging_orchestrator.py:74` com rotação 10 MB / 5000 recs / 10 backups → `log_files/nif_pt.log`. | `Logging/logging_orchestrator.py:74` |
| **BANNER/TAG/BOX/TIMING** | Estilos R1–R9 `logging_orchestrator.py:235` (`WIDTH=49`, `%.2fs` `perf_counter`, `[api][valid][cfg][db][sqlite][io][map][erro][rate-limit]`). | `Logging/logging_orchestrator.py:235` |
| **nif_api_erros** | Tabela auditoria 14c (`id`, `nif`, `data_erro`, `tipo_erro`, `codigo_erro`, `mensagem`, `left_*`, `dados_json`, `acao`, `resolvido`) — dual SQLite (`utils/error_handler.py:46`) + Azure (`sql/02_criar_tabela_erros.sql:20`). | `utils/error_handler.py:46` |
| **rate_limit_*** | Tipos `utils/error_handler.py:69` `TIPO_RATE_LIMIT_MINUTE/HOUR/DAY/MONTH/PAID` + `UNKNOWN/GENERIC_ERROR` — classificados por `classificar_erro()` (`:139`). | `utils/error_handler.py:69` |
| **tratar_erro / handle_error** | `utils/error_handler.py:346` decide `retry` `60s/3600s` vs `abort` com `tentativas_por_tipo` + `tentativa_global` + `guardar_erro()`. Alias `handle_error()` (`:609`). | `utils/error_handler.py:346` |
| **ADR** | Architecture Decision Record — 8 ADRs em `docs/technical.md` §12 + `docs/architecture/architecture.md` §7. | `docs/technical.md` §12 |
| **C4** | Modelo C4 (Contexto, Contentores, Componentes) — `docs/technical.md` §2 + `docs/architecture/architecture.md` §1-2. | `docs/technical.md` §2 |
