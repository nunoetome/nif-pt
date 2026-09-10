# Requisitos — nif-pt v1.0.0

## 1. Atores

| Ator | Descrição | Ficheiro |
|------|-----------|----------|
| Utilizador | Executa CLI com NIF, configura `.env`, consulta histórico, lê `help()` | `consulta_nif.py:271` `main()` |
| Sistema `nif.pt` | API externa `GET http://www.nif.pt/?json=1&q=&key=` `timeout 10s` | `consulta_nif.py:113` |
| `utils/error_handler` | Classifica `rate_limit_*`, persiste `nif_api_erros`, decide `retry 60s/3600s` vs `abort` | `utils/error_handler.py:346` |
| SQLite | `data/nif_pt.db` WAL — `nif_pt` 4c + `nif_api_erros` 14c | `importar_nif_sqlite.py:42` + `utils/error_handler.py:46` |
| Azure SQL | `kiwa-pt-operations/stg_nunotome` — `nif_pt` 37c + `nif_pt_stg` 40c + `nif_api_erros` 14c | `sql/01_criar_tabelas.sql` + `sql/02_criar_tabela_erros.sql` |
| Logging | `log_files/nif_pt.log` `RotatingFileHandler` 10MB/5000/10 R1–R9 `<<nif-pt>>` | `Logging/logging_orchestrator.py:226` |

## 2. Casos de Uso

### UC-01 — Consultar NIF

* **Ator:** Utilizador
* **Pré:** `config/.env` com `NIF-PT-KEY` (hífen)
* **Fluxo:** `python consulta_nif.py <NIF>` → valida `isdigit` → `init_error_table()` → `validar_nif()` Mod-11 → `GET nif.pt ?json=1` com `timeout 10s` + loop `max_global+1` com `tratar_erro()` → JSON `stdout` → `exit 0/1` + BOX/TAG/TIMING `stderr`
* **Pós:** JSON `{nif,valido,fonte,erro,dados,nif_valido_formato,creditos,tipo_erro}`

### UC-02 — Guardar em SQLite

* **Pré:** UC-01 sucesso (`erro is None`)
* **Fluxo:** `... | python importar_nif_sqlite.py` → `sys.stdin.read()` → `json.loads` → valida `erro==null` → `get_db()` WAL → `INSERT (nif, dados, data_consulta)` → `commit` → BOX `Guardado em SQLite`
* **Pós:** `stderr` `<<nif-pt>> [sqlite] INSERT nif_pt nif=... -> 1 row`

### UC-03 — Guardar em Azure SQL

* **Pré:** UC-01 sucesso + `AZURE_USER/PALAVRA_CHAVE` + ODBC 18 + `nif_pt_stg` + `nif_api_erros` criadas
* **Fluxo:** `... | python importar_nif.py` → `mapear_registo()` 36c → `connection_string()` → `INSERT INTO stg_nunotome.nif_pt_stg (36 cols) VALUES (36 ?)` parametrizado → `commit/rollback` → BOX `Inserido em Azure SQL`
* **Pós:** `stderr` `[db] INSERT stg_nunotome.nif_pt_stg nif=... -> 1 row`

### UC-04 — Tratar erro de quota (v1.0.0)

* **Ator:** `utils/error_handler` (chamado por `consultar_nif`)
* **Fluxo:** `result != "success"` → `classificar_erro()` → `rate_limit_minute/hour` → `guardar_erro()` 14c WAL → `tratar_erro()` decide `retry 60s/3600s` se `tenta_tipo < max_tipo && tenta_global < max_global` senão `abort` → `consulta_nif` faz `sleep(espera)` + retry ou devolve `erro+tipo_erro`
* **Pós:** `nif_api_erros` com `acao=retry_60s/abort_day`, log `[rate-limit]`, `exit 1` se abort

### UC-05 — Consultar histórico / auditoria

* **Fluxo:** `SELECT * FROM nif_pt ORDER BY data_consulta DESC` (SQLite) · `SELECT * FROM nif_api_erros WHERE tipo_erro='rate_limit_minute'` (auditoria) · `SELECT * FROM stg_nunotome.nif_pt_stg WHERE processado=0` (Azure staging)

## 3. Requisitos Funcionais

| ID | Requisito | Critério de aceitação | Estado v1.0.0 | Ficheiro |
|----|-----------|----------------------|---------------|----------|
| RF-01 | Validar NIF Mod-11 | `validar_nif("509442013")==True`, `validar_nif("123456789")==False` | ✅ | `consulta_nif.py:48` |
| RF-02 | Consultar `nif.pt` | `GET ?json=1&q=<NIF>&key=<KEY>` `timeout 10s` + `raise_for_status` + `resp.json()` + loop `max_global+1` | ✅ | `consulta_nif.py:113` |
| RF-03 | Normalizar JSON | Sempre `{nif,valido,fonte,erro,dados,nif_valido_formato,creditos,tipo_erro}` | ✅ | `consulta_nif.py:257` |
| RF-04 | Tratar erros rede/JSON/result | `Timeout/RequestException/JSONDecodeError/result!="success"` → `erro+exit 1` + `tipo_erro` | ✅ | `consulta_nif.py:123` + `utils/error_handler.py:139` |
| RF-05 | Classificar rate-limit | `Limit per minute/hour/day/month/paid` → `rate_limit_*` via `message` + `left` | ✅ | `utils/error_handler.py:139` |
| RF-06 | Persistir `nif_api_erros` dual | `guardar_erro()` 14c com `left_*`, `dados_json`, `acao` em SQLite WAL + Azure | ✅ | `utils/error_handler.py:261` + `sql/02_criar_tabela_erros.sql` |
| RF-07 | Retry/abort por tipo+global | `retry 60s` minuto (3) / `3600s` hora (2) / `abort` dia/mes (0) com `&&` global 5 | ✅ | `utils/error_handler.py:346` |
| RF-08 | Guardar SQLite JSON bruto | `nif_pt` 4c `PRAGMA WAL` + `INSERT (nif,dados,data_consulta)` | ✅ | `importar_nif_sqlite.py:42` |
| RF-09 | Normalizar 36c Azure | `mapear_registo()` + `parse_date/capital/int` + `extrair_cae` | ✅ | `importar_nif.py:103` |
| RF-10 | Pipeline `stdin/stdout` | `sys.stdin.read()` → `json.loads` → `INSERT ?` + `commit/rollback` + `stdout` só JSON | ✅ | `importar_nif.py:193` |
| RF-11 | Config centralizada | `get_config(script_name)` merge `default< script <.env` + `***` | ✅ | `config/config.py:30` |
| RF-12 | Logging R1-R9 | `RotatingFileHandler` 10MB/5000/10 + `BOX/TAG/TIMING` + `<<nif-pt>>` + `stderr` | ✅ | `Logging/logging_orchestrator.py:226` |
| RF-13 | Help PEP 257 | `help(validar_nif)`, `help(tratar_erro)`, `help(get_config)` | ✅ | `docs/api/help.md` |

## 4. Requisitos Não-Funcionais

| ID | Requisito | Métrica | Estado v1.0.0 |
|----|-----------|---------|---------------|
| RNF-01 | Performance | `timeout 10s`, `sleep 60s/3600s` em retry, `WAL`, `sleep 1` batch | ✅ |
| RNF-02 | Fiabilidade | `exit 0/1`, `commit/rollback`, `WAL`, dual `nif_api_erros`, `&&` per-tipo+global | ✅ |
| RNF-03 | Segurança | `.env` ignorado, `NIF-PT-KEY ***XXXX`, `PWD` nunca logado | ✅ |
| RNF-04 | Portabilidade | `pathlib`, `pyodbc` ODBC 18, PowerShell 5.1 + Bash | ✅ |
| RNF-05 | Manutenibilidade | `MANUAL.md` 15 caps, `CHANGELOG.md` v1.0.0, `docs/technical.md` + `api/help.md` | ✅ |
| RNF-06 | Observabilidade | `RotatingFileHandler` 10MB/5000/10 + `BOX` + `TAG [rate-limit]` + `TIMING` + `nif_api_erros` | ✅ |
| RNF-07 | Testabilidade | `help()` + `file:line` em `docs/technical.md` §8 | ✅ |

## 5. Requisitos Futuros (Roadmap)

| ID | Requisito | Versão |
|----|-----------|--------|
| RF-14 | `cli.py --nif --to {sqlite,azure,both} --file` | `v1.1` |
| RF-15 | `usp_merge_nif_pt` `nif_pt_stg→nif_pt` + `UPDATE nif_api_erros.resolvido` | `v1.1` |
| RF-16 | `api/` FastAPI + `models/` Pydantic | `v1.2` |
| RF-17 | `scrapers/` fallback HTML + `tests/` + `mkdocs` | `v1.2` |

## 6. Restrições

* `nif.pt` agregadora — não oficial AT; `No records found` não indica NIF inválido (→ `generic_error`).
* `NIF-PT-KEY` hífen — `os.getenv("NIF-PT-KEY")` frágil; futuro `NIF_PT_KEY` normalizado.
* `DROP TABLE` em `sql/01_criar_tabelas.sql` destrutivo — usar `IF NOT EXISTS` em prod.
* `rate_limit` depende de `message` da API + `left`; se API mudar mensagem, `classificar_erro()` precisa atualizar.

## 7. Glossário

Ver [../glossary.md](../glossary.md) + [../technical.md](../technical.md) §6.
