# Glossário — nif-pt v1.2.0

| Termo | Definição | Ficheiro |
|-------|-----------|----------|
| **NIF** | Número de Identificação Fiscal — 9 dígitos PT. Validado por Mod-11 (`consulta_nif.py:99` `validar_nif()`). | `consulta_nif.py:99` |
| **Mod-11** | Algoritmo dígito controlo AT: `Σ d[i]*(9-i) %11 → 0 se resto 0/1 senão 11-resto` == `d[8]`. | `consulta_nif.py:99` |
| **nif.pt** | Portal agregador `http://www.nif.pt` — fonte `GET ?json=1&q=<NIF>&key=<KEY>` (`consulta_nif.py:272` `requests.get` com `cache` antes). | `consulta_nif.py:272` |
| **NIF-PT-KEY** | Chave API `nif.pt` (`.env`, `config/config.py:120` `os.getenv("NIF-PT-KEY")`). Com hífen — frágil. | `config/config.py:120` |
| **CAE** | Classificação Portuguesa Atividades Económicas — `dados.cae` lista em `nif_pt.dados` JSON. | `docs/database/schema.md` |
| **WAL** | Write-Ahead Logging — `PRAGMA journal_mode=WAL` em `importar_nif_sqlite.py:95`, `utils/error_handler.py:110` e `utils/cache_validator.py:142` mitiga `database is locked`. | `importar_nif_sqlite.py:95` |
| **cache_ativo** | Flag `config/config.yaml:15` `cache_ativo: true` — liga validação cache antes de API. | `config/config.yaml:15` |
| **cache_antiguidade_dias** | Janela recenticidade `config/config.yaml:15` `30` dias — `utils/cache_validator.py:113` `_get_cache_config()`. | `utils/cache_validator.py:113` |
| **cache_tabela_ignorados** | Nome tabela ignorados `config/config.yaml:15` `"nif_ignorados"` (sanitizado `alnum+_`). | `utils/cache_validator.py:119` |
| **nif_ignorados** | Tabela cache 6c (`id, nif, data_tentativa, data_ultima_consulta, dias_desde_ultima, motivo`) — `utils/cache_validator.py:43` `DDL_IGNORADOS` + 2 índices `idx_nif_ignorados_*` + `init_cache_tables()` idempotente. | `utils/cache_validator.py:43` |
| **is_nif_recente** | `utils/cache_validator.py:225` `is_nif_recente(nif, dias) -> (bool, str\|None)` — `SELECT data_consulta FROM nif_pt WHERE nif=? ORDER BY datetime(...) DESC LIMIT 1` + `total_seconds/86400 < dias`. | `utils/cache_validator.py:225` |
| **registar_ignorado** | `utils/cache_validator.py:329` `registar_ignorado(nif, data_ultima_consulta, motivo="cache_recente") -> int\|None` — `INSERT nif_ignorados` com `dias_desde_ultima` calculado. | `utils/cache_validator.py:329` |
| **cache_recente** | Motivo `DEFAULT 'cache_recente'` em `nif_ignorados.motivo`; payload `consulta_nif.py:556` `{ignorado:true, motivo:"cache_recente", data_ultima_consulta, cache_antiguidade_dias}` + `sys.exit(0)` sem API. | `consulta_nif.py:547` |
| **ignorado** | Campo `bool` no JSON de `consulta_nif.py:556` quando cache hit; `importar_nif_sqlite.py:194` faz `if resultado.get("ignorado"): skip INSERT + BOX skip`. | `importar_nif_sqlite.py:194` |
| **creditos.left** | Créditos API: `dict` (`month/day/hour/minute/paid`) se `paid`, `[]` lista vazia se `free` (real 2026-09-10). | `docs/api/nif-pt-api.md` §5 |
| **nif_valido_formato** | `data.get("nif_validation")` da API → `bool` em JSON. | `consulta_nif.py:429` |
| **get_config** | `config/config.py:30` funde `default` + bloco script + `.env` + `***` mascarado; documenta `cache_*`. | `config/config.py:30` |
| **RotatingFileHandler** | Handler custom `Logging/logging_orchestrator.py:74` com rotação 10 MB / 5000 recs / 10 backups → `log_files/nif_pt.log`. | `Logging/logging_orchestrator.py:74` |
| **BANNER/TAG/BOX/TIMING** | Estilos R1–R9 `logging_orchestrator.py:235` (`WIDTH=49`, `%.2fs` `perf_counter`, `[api][valid][cfg][db][sqlite][io][map][erro][rate-limit][cache][run]`). | `Logging/logging_orchestrator.py:235` |
| **nif_api_erros** | Tabela auditoria 15c (`id, nif, data_erro, tipo_erro, codigo_erro, mensagem, left_*, dados_json, acao, run_id, resolvido`) — só SQLite WAL (`utils/error_handler.py:46`). | `utils/error_handler.py:46` |
| **nif_pt** | Tabela SQLite 5c (`id, nif, dados TEXT JSON, data_consulta, run_id`) — `importar_nif_sqlite.py:55` `SQL_DDL` + `PRAGMA WAL` + `idx_nif_pt_run_id`. | `importar_nif_sqlite.py:55` |
| **rate_limit_*** | Tipos `utils/error_handler.py:69` `TIPO_RATE_LIMIT_MINUTE/HOUR/DAY/MONTH/PAID` + `UNKNOWN/GENERIC_ERROR` — classificados por `classificar_erro()` (`:196`). | `utils/error_handler.py:196` |
| **tratar_erro / handle_error** | `utils/error_handler.py:515` decide `retry` `60s/3600s` vs `abort` com `tentativas_por_tipo` + `tentativa_global` + `guardar_erro(...,run_id)`. Alias `handle_error()` (`:787`). | `utils/error_handler.py:515` |
| **run_id** | UUID v4 por execução `utils/run_id.py:41` `generate_run_id()` + `ContextVar` + `ensure_run_id(CLI>payload>ctx>gen)` + `--run-id` + propagação JSON + índices `run_id`. | `utils/run_id.py:41` |
| **ADR** | Architecture Decision Record — 10 ADRs em `docs/technical.md` §12 + `docs/architecture/architecture.md` §7 (ADR-010 cache). | `docs/technical.md` §12 |
| **C4** | Modelo C4 (Contexto, Contentores, Componentes) — `docs/technical.md` §2 + `docs/architecture/architecture.md` §1-2. | `docs/technical.md` §2 |
