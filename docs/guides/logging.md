# Guia de Logging — nif-pt v1.0.0

> `Logging/logging_orchestrator.py` (580L) — **integrado** em todos os scripts via `setup_logging()`. Prefixo `<<nif-pt>>`, `log_files/nif_pt.log`.

## 1. Estado v1.0.0

* Todos os scripts (`consulta_nif.py:272`, `importar_nif.py:194`, `importar_nif_sqlite.py:63`, `utils/error_handler.py`, `config/config.py`) fazem `from Logging.logging_orchestrator import setup_logging` + `logger = setup_logging()`.
* `stderr` com TAGs + `stdout` só JSON → pipe não quebra.
* `LOG_FOLDER='log_files'`, `LOG_OUTPUT_FILE='log_files/nif_pt.log'` (`logging_orchestrator.py:40`), `LOG_OUTPUT_PREFIX='<<nif-pt>>'` (`:42`).

## 2. Funcionalidades

* **Níveis:** `LOG_LEVEL_GLOBAL=INFO`, `LOG_LEVEL_FILE/CONSOLE=INFO` (`:35`).
* **Rotação:** `RotatingFileHandler` custom (`:74`) — não `logging.handlers.RotatingFileHandler` — com `LOG_MAX_BYTES=10485760` (10 MB), `LOG_MAX_RECORDS=5000`, `LOG_MAX_BACKUP=10` (`:64`), cascata `_archive_name(i)=base_idx.ext`.
* **Formatos:** `LOG_FORMAT_FILE='<<nif-pt>> %(asctime)s - %(name)s - %(levelname)s - %(message)s'` + ultra-debug `%(filename)s - %(funcName)s - %(lineno)d` se `FILE_ULTRA_DEBUG=True` (`:52`).
* **API:** `LOGGER=logging.getLogger()`, `ini_logging()` legacy (`:169`), `setup_logging()` wrapper (`:226`), idempotente `if LOGGER.handlers: return`.
* **`stderr` seguro:** `StreamHandler(sys.stderr)` (`:205`) — não quebra `| python importar_*.py`.

## 3. Livro de Estilo R1–R9 (`logging_orchestrator.py:235`)

| # | Estilo | Char | Width | Nível | Uso | Código |
|---|--------|------|-------|-------|-----|--------|
| 1 | `BANNER_APP_START` | `=` | 49 | INFO | Início app | `logger.info("="*49); logger.info(f"{' nif-pt consulta_nif a iniciar ':=^49}")` |
| 2 | `BANNER_APP_END` | `=` | 49 | INFO | Fim app + TIMING | `logger.info("Aplicação concluída em %.2fs", time.perf_counter()-t)` |
| 3 | `BANNER_SECTION_START` | `-` | 49 | INFO | Secção | `logger.info(f"{' Inserir staging ':-^49}")` |
| 5 | `BANNER_FUNCTION` | `~` | 49 | DEBUG | Função crítica | `logger.debug(f"{' validar_nif() ':~^49}")` |
| 6 | `TAG` | `[tag]` | — | herda | Componente | `logger.info("[api] GET ...")` `logger.warning("[rate-limit] ...")` |
| 7 | `SEPARATOR` | `-` | 49 | DEBUG | Separador | `logger.debug("-"*49)` |
| 8 | `BOX` | `-\|` | 49 | INFO | Resumo | `| NIF : 509442013 |` `| Consulta com sucesso |` |
| 9 | `TIMING` | `%.2fs` | — | INFO/DEBUG | `perf_counter` | `logger.debug("[valid] validar_nif -> %.2fs", elapsed)` |

Regras: `R1 WIDTH=49 ≤79`, `R4 [tag] lowercase ≤12 chars`, `R6 f-string alignment`, `R9 %.2fs` sempre `time.perf_counter()`.

**TAGs v1.0.0:** `[api]` `[valid]` `[cfg]` `[db]` `[sqlite]` `[io]` `[map]` `[erro]` `[rate-limit]` `[cli]`.

## 4. Integração (já ativa)

```python
from Logging.logging_orchestrator import setup_logging
import time

logger = setup_logging()
logger.info("=" * 49)
logger.info(f"{' nif-pt consulta_nif a iniciar ':=^49}")
logger.info("=" * 49)
t = time.perf_counter()
# ... consultar_nif / tratar_erro / importar ...
logger.info("Aplicação concluída em %.2fs", time.perf_counter() - t)
logger.info("=" * 49)
logger.info(f"{' nif-pt consulta_nif finalizado ':=^49}")
logger.info("=" * 49)
```

## 5. Exemplo de saída (`log_files/nif_pt.log` + `stderr`)

```
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ========= nif-pt consulta_nif a iniciar =========
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - consulta_nif - INFO - [api] GET http://www.nif.pt?q=509442013 key=***XXXX timeout=10s
<<nif-pt>> 2026-09-10 02:15:32 - consulta_nif - INFO - [api] GET nif.pt?q=509442013 -> 200 OK em 0.85s
<<nif-pt>> 2026-09-10 02:15:32 - consulta_nif - WARNING - [rate-limit] Limite por minuto nif=509442013 left_minute=0 — espera 60s retry tipo 1/3 global 1/5
<<nif-pt>> 2026-09-10 02:15:32 - consulta_nif - INFO - [api] NIF 509442013 válido=True credits used=free left=[] (0.85s)
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ---------------------------------------------------
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | Consulta com sucesso                          |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - | NIF         : 509442013                    |
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ---------------------------------------------------
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - Aplicação concluída em 0.92s
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ============ nif-pt consulta_nif finalizado ============
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
```

BOX erro quota `day/month`:

```
<<nif-pt>> ... - ERROR - [rate-limit] Limite por dia atingido nif=509442013 left_day=0 tipo 0/0 global 1/5 — a encerrar app
<<nif-pt>> ... - INFO - ---------------------------------------------------
<<nif-pt>> ... - INFO - | Erro fatal - quota diária excedida               |
<<nif-pt>> ... - INFO - | NIF         : 509442013                    |
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
* `docs/technical.md` §11 · `MANUAL.md` §11
* Origem template: https://github.com/nunoetome/my_python_starter_kit (v2.1, 2026-06-19) — adaptado para `<<nif-pt>>` + `nif_pt.log`.
