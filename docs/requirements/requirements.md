# Requisitos — nif-pt v1.2.0

## 1. Atores

| Ator | Descrição | Ficheiro |
|------|-----------|----------|
| Utilizador | Executa CLI com NIF, configura `.env`, consulta histórico, lê `help()` | `consulta_nif.py:442` `main()` |
| Sistema `nif.pt` | API externa `GET http://www.nif.pt/?json=1&q=&key=` `timeout 10s` | `consulta_nif.py:272` |
| `utils/cache_validator` | Verifica `is_nif_recente()` + `registar_ignorado()` em `nif_ignorados` antes de API | `utils/cache_validator.py:225` |
| `utils/error_handler` | Classifica `rate_limit_*`, persiste `nif_api_erros`, decide `retry 60s/3600s` vs `abort` | `utils/error_handler.py:515` |
| SQLite | `data/nif_pt.db` WAL — `nif_pt` 5c + `nif_api_erros` 15c + `nif_ignorados` 6c | `importar_nif_sqlite.py:55` + `utils/cache_validator.py:43` + `utils/error_handler.py:46` |
| Logging | `log_files/nif_pt.log` `RotatingFileHandler` 10MB/5000/10 R1–R9 `<<nif-pt>>` + TAG `[cache][run]` | `Logging/logging_orchestrator.py:226` |

## 2. Casos de Uso

### UC-01 — Consultar NIF

* **Ator:** Utilizador
* **Pré:** `config/.env` com `NIF-PT-KEY` (hífen)
* **Fluxo:** `python consulta_nif.py <NIF>` → valida `isdigit` → `init_error_table()` + `init_cache_tables()` → `validar_nif()` Mod-11 → `is_nif_recente(nif, dias)` se `cache_ativo` e recente → `registar_ignorado()` + JSON `{ignorado:true, motivo:cache_recente}` + `exit 0` (sem API) senão `GET nif.pt ?json=1` com `timeout 10s` + loop `max_global+1` com `tratar_erro()` → JSON `stdout` → `exit 0/1` + BOX/TAG/TIMING `stderr`
* **Pós:** JSON `{nif,valido,fonte,erro,dados,nif_valido_formato,creditos,tipo_erro,run_id}` ou `{ignorado:true, motivo, data_ultima_consulta, cache_antiguidade_dias, run_id}`

### UC-02 — Guardar em SQLite

* **Pré:** UC-01 sucesso (`erro is None` e `ignorado != true`)
* **Fluxo:** `... | python importar_nif_sqlite.py` → `sys.stdin.read()` → `json.loads` → se `ignorado==true` → `INFO [cache] skip INSERT` + `BOX NIF ignorado - skip SQLite` + `exit 0` sem `INSERT`; senão valida `erro==null` → `get_db()` WAL → `INSERT (nif, dados, data_consulta, run_id)` → `commit` → BOX `Guardado em SQLite`
* **Pós:** `stderr` `<<nif-pt>> [sqlite] INSERT nif_pt nif=... -> 1 row` + `data/nif_pt.db` com `run_id`

### UC-03 — Validação cache (v1.2.0)

* **Ator:** `utils/cache_validator` (chamado por `consulta_nif.main` antes de `consultar_nif`)
* **Fluxo:** `cache_ativo==true` → `_get_cache_config()` lê `cache_antiguidade_dias` + `cache_tabela_ignorados` → `init_cache_tables()` DDL `nif_ignorados` 6c + 2 índices WAL → `is_nif_recente(nif, dias)` → `SELECT data_consulta FROM nif_pt WHERE nif=? ORDER BY datetime(...) DESC LIMIT 1` → parse `YYYY-MM-DD HH:MM:SS`/`ISO` → `total_seconds/86400 < dias && >=0` (ou futuro → recente) → se `recente==True` → `registar_ignorado(nif, data_ultima, "cache_recente")` → `nif_ignorados` com `dias_desde_ultima` → `stdout` JSON `ignorado` + `stderr` `BOX NIF ignorado` + `exit 0` sem API; se `recente==False` → prossegue para API (fail-open em erro BD)
* **Pós:** `nif_ignorados` com auditoria + créditos não consumidos; log `[cache] NIF ... recente=True/False (%.2fs)`

### UC-04 — Tratar erro de quota (v1.0.0 + run_id)

* **Ator:** `utils/error_handler` (chamado por `consultar_nif`)
* **Fluxo:** `result != "success"` → `classificar_erro()` → `rate_limit_minute/hour` → `guardar_erro(...,run_id)` 15c WAL → `tratar_erro()` decide `retry 60s/3600s` se `tenta_tipo < max_tipo && tenta_global < max_global` senão `abort` → `consulta_nif` faz `sleep(espera)` + retry ou devolve `erro+tipo_erro+run_id`
* **Pós:** `nif_api_erros` com `acao=retry_60s/abort_day`, log `[rate-limit]`, `exit 1` se abort

### UC-05 — Consultar histórico / auditoria

* **Fluxo:** `SELECT * FROM nif_pt ORDER BY data_consulta DESC` (SQLite) · `SELECT * FROM nif_api_erros WHERE tipo_erro='rate_limit_minute'` (auditoria erros) · `SELECT * FROM nif_ignorados WHERE motivo='cache_recente' ORDER BY data_tentativa DESC` (auditoria cache) · `SELECT tipo_erro, COUNT(*) FROM nif_api_erros GROUP BY run_id`

## 3. Requisitos Funcionais

| ID | Requisito | Critério de aceitação | Estado v1.2.0 | Ficheiro |
|----|-----------|----------------------|---------------|----------|
| RF-01 | Validar NIF Mod-11 | `validar_nif("509442013")==True`, `validar_nif("123456789")==False` | ✅ | `consulta_nif.py:99` |
| RF-02 | Consultar `nif.pt` | `GET ?json=1&q=<NIF>&key=<KEY>` `timeout 10s` + `raise_for_status` + `resp.json()` + loop `max_global+1` | ✅ | `consulta_nif.py:272` |
| RF-03 | Normalizar JSON | Sempre `{nif,valido,fonte,erro,dados,nif_valido_formato,creditos,tipo_erro,run_id}` + opcional `ignorado/motivo/data_ultima_consulta/cache_antiguidade_dias` se cache | ✅ | `consulta_nif.py:237` + `:547` |
| RF-04 | Tratar erros rede/JSON/result | `Timeout/RequestException/JSONDecodeError/result!="success"` → `erro+exit 1` + `tipo_erro` | ✅ | `consulta_nif.py:284` + `utils/error_handler.py:196` |
| RF-05 | Classificar rate-limit | `Limit per minute/hour/day/month/paid` → `rate_limit_*` via `message` + `left` | ✅ | `utils/error_handler.py:196` |
| RF-06 | Persistir `nif_api_erros` SQLite | `guardar_erro(...,run_id)` 15c com `left_*`, `dados_json`, `acao` em SQLite WAL | ✅ | `utils/error_handler.py:368` |
| RF-07 | Retry/abort por tipo+global | `retry 60s` minuto (3) / `3600s` hora (2) / `abort` dia/mes (0) com `&&` global 5 | ✅ | `utils/error_handler.py:515` |
| RF-08 | Guardar SQLite JSON bruto | `nif_pt` 5c `PRAGMA WAL` + `INSERT (nif,dados,data_consulta,run_id)` | ✅ | `importar_nif_sqlite.py:55` |
| RF-09 | Pipeline `stdin/stdout` | `sys.stdin.read()` → `json.loads` → `INSERT` + `commit` + `stdout` só JSON + early skip `ignorado` | ✅ | `importar_nif_sqlite.py:123` |
| RF-10 | Config centralizada | `get_config(script_name)` merge `default< script <.env` + `***` + `cache_*` documentado | ✅ | `config/config.py:53` |
| RF-11 | Logging R1-R9 | `RotatingFileHandler` 10MB/5000/10 + `BOX/TAG/TIMING` + `<<nif-pt>>` + `[cache][run]` + `stderr` | ✅ | `Logging/logging_orchestrator.py:226` |
| RF-12 | Help PEP 257 | `help(validar_nif)`, `help(is_nif_recente)`, `help(tratar_erro)`, `help(get_config)` | ✅ | `docs/api/help.md` |
| RF-13 | Rastreabilidade `run_id` | `generate_run_id()` + `ensure_run_id(CLI>payload>ctx>gen)` + `--run-id` + persistência 5/15c | ✅ | `utils/run_id.py:41` |
| RF-14 | Validação cache SQLite | `is_nif_recente(nif,dias)` + `registar_ignorado()` + `init_cache_tables()` + `nif_ignorados` 6c + `stdout` `{ignorado:true}` + early skip importador | ✅ | `utils/cache_validator.py:225` |

## 4. Requisitos Não-Funcionais

| ID | Requisito | Métrica | Estado v1.2.0 |
|----|-----------|---------|---------------|
| RNF-01 | Performance | `timeout 10s`, `sleep 60s/3600s` em retry, `WAL`, `sleep 1` batch, cache evita API para NIFs recentes | ✅ |
| RNF-02 | Fiabilidade | `exit 0/1`, `commit/rollback`, `WAL`, `nif_api_erros` + `nif_ignorados`, `&&` per-tipo+global, fail-open cache | ✅ |
| RNF-03 | Segurança | `.env` ignorado, `NIF-PT-KEY ***XXXX`, sem `AZURE_*` | ✅ |
| RNF-04 | Portabilidade | `pathlib`, PowerShell 5.1 + Bash, só `sqlite3` stdlib (sem ODBC) | ✅ |
| RNF-05 | Manutenibilidade | `MANUAL.md` 15 caps, `CHANGELOG.md` v1.2.0, `docs/technical.md` + `api/help.md` | ✅ |
| RNF-06 | Observabilidade | `RotatingFileHandler` 10MB/5000/10 + `BOX` + `TAG [cache][rate-limit][run]` + `TIMING` + `nif_api_erros` + `nif_ignorados` | ✅ |
| RNF-07 | Testabilidade | `help()` + `file:line` em `docs/technical.md` §8 + `is_nif_recente` unitável | ✅ |

## 5. Requisitos Futuros (Roadmap)

| ID | Requisito | Versão |
|----|-----------|--------|
| RF-15 | `cli.py --nif --to {sqlite} --file` + `--no-cache` | `v1.3` |
| RF-16 | `api/` FastAPI + `models/` Pydantic | `v1.3` |
| RF-17 | `scrapers/` fallback HTML + `tests/` + `mkdocs` | `v1.4` |
| RF-18 | `NIF_PT_KEY` normalizado (sem hífen) + `cache --refresh` | `v1.3` |

## 6. Restrições

* `nif.pt` agregadora — não oficial AT; `No records found` não indica NIF inválido (→ `generic_error`).
* `NIF-PT-KEY` hífen — `os.getenv("NIF-PT-KEY")` frágil; futuro `NIF_PT_KEY` normalizado.
* `nif_pt` sem `UNIQUE(nif)` — histórico; `is_nif_recente` usa `ORDER BY datetime(data_consulta) DESC LIMIT 1`.
* `rate_limit` depende de `message` da API + `left`; se API mudar mensagem, `classificar_erro()` precisa atualizar.
* `cache_antiguidade_dias <=0` desliga recenticidade (sempre `False`) — forçar refresh com `0` ou `cache_ativo: false`.

## 7. Glossário

Ver [../glossary.md](../glossary.md) + [../technical.md](../technical.md) §6.
