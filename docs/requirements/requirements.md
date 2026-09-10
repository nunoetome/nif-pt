# Requisitos — nif-pt

## 1. Atores

| Ator | Descrição |
|------|-----------|
| Utilizador | Executa CLI com NIF, configura `.env`, consulta histórico |
| Sistema `nif.pt` | API externa `http://www.nif.pt/?json=1&q=&key=` |
| SQLite | BD local `data/nif_pt.db` |
| Azure SQL | BD remota `kiwa-pt-operations.stg_nunotome.*` |

## 2. Casos de Uso

### UC-01 — Consultar NIF

* **Ator:** Utilizador
* **Pré:** `config/.env` com `NIF-PT-KEY`
* **Fluxo:** `python consulta_nif.py <NIF>` → valida `isdigit` → `validar_nif()` → `GET nif.pt` → JSON stdout → `exit 0/1`
* **Pós:** JSON com `valido`, `dados`, `creditos` ou `erro`

### UC-02 — Guardar em SQLite

* **Pré:** UC-01 sucesso
* **Fluxo:** `... | python importar_nif_sqlite.py` → `sys.stdin.read()` → valida `erro==null` → `INSERT (nif, dados, data_consulta)` com `WAL`
* **Pós:** `stderr` “NIF x guardado em nif_pt.”

### UC-03 — Guardar em Azure SQL

* **Pré:** UC-01 sucesso + `AZURE_USER`/`AZURE_PALAVRA_CHAVE` + ODBC 18 + tabela `nif_pt_stg`
* **Fluxo:** `... | python importar_nif.py` → `mapear_registo()` 36 cols → `INSERT INTO stg_nunotome.nif_pt_stg (36 cols) VALUES (36 ?)` parametrizado → `commit`
* **Pós:** `stderr` “NIF x inserido em stg_nunotome.nif_pt_stg.”

### UC-04 — Consultar histórico

* **Fluxo:** `SELECT * FROM nif_pt ORDER BY data_consulta DESC` (SQLite) ou `SELECT * FROM nif_pt_stg WHERE processado=0` (Azure)

## 3. Requisitos Funcionais

| ID | Requisito | Critério de aceitação | Estado |
|----|-----------|----------------------|--------|
| RF-01 | Validar NIF Mod-11 | `validar_nif("509442013")==True`, `validar_nif("123456789")==False` | ✅ `consulta_nif.py:26` |
| RF-02 | Consultar `nif.pt` | `GET ?json=1&q=<NIF>&key=<KEY>` com `timeout`, `raise_for_status`, `resp.json()` | ✅ `consulta_nif.py:48` |
| RF-03 | Normalizar JSON | Retornar `{nif,valido,fonte,erro,dados,nif_valido_formato,creditos}` sempre | ✅ `consulta_nif.py:77` |
| RF-04 | Tratar erros | `Timeout`/`RequestException`/`JSONDecodeError`/`result!="success"` → `erro` + `exit 1` | ✅ `consulta_nif.py:54` |
| RF-05 | Guardar SQLite JSON bruto | `CREATE TABLE IF NOT EXISTS nif_pt (id,nif,dados,data_consulta)` + `PRAGMA WAL` + `INSERT` | ✅ `importar_nif_sqlite.py:27` |
| RF-06 | Normalizar 36 cols Azure | `mapear_registo()` desembrulha `place/geo/contacts/structure/creditos` + `parse_*` | ✅ `importar_nif.py:83` |
| RF-07 | Pipeline `stdin`/`stdout` | `sys.stdin.read()` → `json.loads` → `INSERT` parametrizado `?` + `commit/rollback` | ✅ |
| RF-08 | Config centralizada | `get_config(script_name)` merge `default< script <.env` | ✅ `config/config.py:17` |

## 4. Requisitos Não-Funcionais

| ID | Requisito | Métrica | Estado |
|----|-----------|---------|--------|
| RNF-01 | Performance | `timeout` configurável, `sleep 1` em batch | ⚠️ `timeout:1000` excessivo |
| RNF-02 | Fiabilidade | `exit 0/1`, `commit/rollback`, `WAL` | ✅ |
| RNF-03 | Segurança | `.env` ignorado, `NIF-PT-KEY` não logado | ✅ |
| RNF-04 | Portabilidade | `pathlib`, `pyodbc` ODBC 18, PowerShell+Bash | ✅ |
| RNF-05 | Manutenibilidade | `MANUAL.md` 15 caps, `CHANGELOG.md`, `docs/` | ✅ `v0.3.0-docs` |
| RNF-06 | Observabilidade | Logging `RotatingFileHandler` 10MB/5000 recs | 🚧 template não integrado |

## 5. Requisitos Futuros (Roadmap)

| ID | Requisito | Versão |
|----|-----------|--------|
| RF-09 | `cli.py` com `argparse` (`--nif`, `--to {sqlite,azure,both}`, `--file`) | `v0.3.0` |
| RF-10 | `retry_count`/`tempo_de_espera` em `consulta_nif.py` | `v0.3.0` |
| RF-11 | Logging integrado `setup_logging()` | `v0.3.0` |
| RF-12 | `MERGE` `nif_pt_stg→nif_pt` (`usp_merge_nif_pt`) | `v0.4.0` |
| RF-13 | `api/` FastAPI + `models/` Pydantic | `v0.4.0` |
| RF-14 | `scrapers/` fallback HTML + `tests/` | `v0.4.0` |

## 6. Restrições

* Fonte `nif.pt` agregadora — não oficial AT; `No records found` não indica NIF inválido.
* `NIF-PT-KEY` com hífen — `os.getenv("NIF-PT-KEY")` frágil em Docker/systemd.
* `DROP TABLE` em `sql/01_criar_tabelas.sql` destrutivo — migrations futuras devem usar `IF NOT EXISTS`.

## 7. Glossário

Ver [../glossary.md](../glossary.md).
