# Guia de Logging — nif-pt v1.2.0

> `Logging/logging_orchestrator.py` (580L) — **integrado** em todos os scripts via `setup_logging()`. Prefixo `<<nif-pt>>`, `log_files/nif_pt.log`.

## 1. Estado v1.2.0

* Todos os scripts (`consulta_nif.py:442`, `importar_nif_sqlite.py:123`, `utils/error_handler.py`, `utils/cache_validator.py:34`, `config/config.py`) fazem `from Logging.logging_orchestrator import setup_logging` + `logger = setup_logging()`.
* `stderr` com TAGs + `stdout` só JSON → pipe não quebra.
* `LOG_FOLDER='log_files'`, `LOG_OUTPUT_FILE='log_files/nif_pt.log'` (`logging_orchestrator.py:40`), `LOG_OUTPUT_PREFIX='<<nif-pt>>'` (`:42`).

## 2. Funcionalidades

* **Níveis:** `LOG_LEVEL_GLOBAL=INFO`, `LOG_LEVEL_FILE/CONSOLE=INFO` (`:35`).
* **Rotação:** `RotatingFileHandler` custom (`:74`) — não `logging.handlers.RotatingFileHandler` — com `LOG_MAX_BYTES=10485760` (10 MB), `LOG_MAX_RECORDS=5000`, `LOG_MAX_BACKUP=10` (`:64`), cascata `_archive_name(i)=base_idx.ext`.
* **Formatos:** `LOG_FORMAT_FILE='<<nif-pt>> %(asctime)s - %(name)s - %(levelname)s - %(message)s'` + ultra-debug `%(filename)s - %(funcName)s - %(lineno)d` se `FILE_ULTRA_DEBUG=True` (`:52`).
* **API:** `LOGGER=logging.getLogger()`, `ini_logging()` legacy (`:169`), `setup_logging()` wrapper (`:226`), idempotente `if LOGGER.handlers: return`.
* **`stderr` seguro:** `StreamHandler(sys.stderr)` (`:205`) — não quebra `| python importar_nif_sqlite.py`.

## 3. Livro de Estilo R1–R9 (`logging_orchestrator.py:235`)

| # | Estilo | Char | Width | Nível | Uso | Código |
|---|--------|------|-------|-------|-----|--------|
| 1 | `BANNER_APP_START` | `=` | 49 | INFO | Início app | `logger.info("="*49); logger.info(f"{' nif-pt consulta_nif a iniciar ':=^49}")` |
| 2 | `BANNER_APP_END` | `=` | 49 | INFO | Fim app + TIMING | `logger.info("Aplicação concluída em %.2fs", time.perf_counter()-t)` |
| 3 | `BANNER_SECTION_START` | `-` | 49 | INFO | Secção | `logger.info(f"{' Inserir staging ':-^49}")` |
| 5 | `BANNER_FUNCTION` | `~` | 49 | DEBUG | Função crítica | `logger.debug(f"{' validar_nif() ':~^49}")` `logger.debug(f"{' is_nif_recente() ':~^49}")` |
| 6 | `TAG` | `[tag]` | — | herda | Componente | `logger.info("[api] GET ...")` `logger.info("[cache] NIF ... recente=True")` |
| 7 | `SEPARATOR` | `-` | 49 | DEBUG | Separador | `logger.debug("-"*49)` |
| 8 | `BOX` | `-\|` | 49 | INFO | Resumo | `| NIF : 509442013 |` `| NIF ignorado - cache recente |` `| Consulta com sucesso |` |
| 9 | `TIMING` | `%.2fs` | — | INFO/DEBUG | `perf_counter` | `logger.debug("[valid] validar_nif -> %.2fs", elapsed)` `logger.info("[cache] ... (0.02s)")` |

Regras: `R1 WIDTH=49 ≤79`, `R4 [tag] lowercase ≤12 chars`, `R6 f-string alignment`, `R9 %.2fs` sempre `time.perf_counter()`.

**TAGs v1.2.0:** `[api]` `[valid]` `[cfg]` `[db]` `[sqlite]` `[io]` `[map]` `[erro]` `[rate-limit]` `[cache]` `[cli]` `[run]`.

Nova TAG `v1.2.0`: `[cache]` — `is_nif_recente()` (`utils/cache_validator.py:304` `INFO [cache] NIF ... recente=...`), `registar_ignorado()` (`:384` `INFO [cache] Ignorado registado`), `consulta_nif.py:546` `INFO [cache] NIF ... ignorado`, `importar_nif_sqlite.py:195` `INFO [cache] NIF ... ignorado - skip INSERT`.

## 4. Integração (já ativa)

```python
from Logging.logging_orchestrator import setup_logging
import time

logger = setup_logging()
logger.info("=" * 49)
logger.info(f"{' nif-pt consulta_nif a iniciar ':=^49}")
logger.info("=" * 49)
t = time.perf_counter()
# ... is_nif_recente / consultar_nif / tratar_erro / importar ...
logger.info("[cache] NIF 509442013 ultima=2026-09-10 12:00:00 dias_desde=0 antiguidade=30 recente=True (0.02s)")
logger.info("Aplicação concluída em %.2fs", time.perf_counter() - t)
logger.info("=" * 49)
logger.info(f"{' nif-pt consulta_nif finalizado ':=^49}")
logger.info("=" * 49)
```

## 5. Exemplo de saída (`log_files/nif_pt.log` + `stderr`)

**Cache hit (sem API):**

```
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ========= nif-pt consulta_nif a iniciar =========
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - [run] run_id=550e8400-e29b-41d4-a716-446655440000
<<nif-pt>> 2026-09-10 02:15:32 - utils.cache_validator - INFO - [cache] NIF 509442013 ultima=2026-09-10 12:00:00 dias_desde=0 antiguidade=30 recente=True (0.02s)
<<nif-pt>> 2026-09-10 02:15:32 - utils.cache_validator - INFO - [cache] Ignorado registado id=1 nif=509442013 ultima=2026-09-10 12:00:00 dias_desde=0 (0.01s)
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - [cache] NIF 509442013 ignorado - ultima consulta 2026-09-10 12:00:00 dentro de 30 dias
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ---------------------------------------------------
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | NIF ignorado - cache recente                 |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | NIF         : 509442013                    |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | Ultima      : 2026-09-10 12:00:00            |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | Antiguidade : 30 dias                      |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ---------------------------------------------------
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - [run] run_id=550e8400-e29b-41d4-a716-446655440000
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - Aplicação concluída em 0.05s
```

**Sucesso com API:**

```
<<nif-pt>> 2026-09-10 02:15:32 - consulta_nif - INFO - [api] GET http://www.nif.pt?q=509442013 key=***XXXX timeout=10s
<<nif-pt>> 2026-09-10 02:15:32 - consulta_nif - INFO - [api] NIF 509442013 válido=True credits used=free left=[] (0.85s)
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ---------------------------------------------------
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | Consulta com sucesso                          |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | NIF         : 509442013                    |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | run_id      : 550e8400-e29b-41d4-a716-...  |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - Aplicação concluída em 0.92s
```

BOX quota `day/month` + `[cache]` skip:

```
<<nif-pt>> ... - ERROR - [rate-limit] Limite por dia atingido nif=509442013 left_day=0 tipo 0/0 global 1/5 — a encerrar app
<<nif-pt>> ... - INFO - [cache] NIF 509442013 ignorado (cache_recente) ultima=2026-09-10 12:00:00 run_id=550e8400 - skip INSERT
```

## 6. Rotação

```
log_files/nif_pt.log       ← atual
log_files/nif_pt_1.log     ← arquivo mais recente (10 MB ou 5000 recs)
...
log_files/nif_pt_10.log    ← mais antigo (removido no próximo ciclo)
```

## 7. Referências

* `Logging/logging_orchestrator.py:74` `RotatingFileHandler` · `:169` `ini_logging()` · `:226` `setup_logging()`
* `utils/cache_validator.py:225` `is_nif_recente()` · `:329` `registar_ignorado()` + TAG `[cache]`
* `docs/technical.md` §11 · `MANUAL.md` §11
* Origem template: https://github.com/nunoetome/my_python_starter_kit (v2.1, 2026-06-19) — adaptado para `<<nif-pt>>` + `nif_pt.log`.
