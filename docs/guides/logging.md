# Guia de Logging — nif-pt

> Template: `Logging/logging_template.py` (579L). **Não integrado** — este guia descreve estado e integração futura.

## 1. Estado Atual

* Nenhum script faz `import logging` ou `from Logging.logging_template import setup_logging`.
* Erros vão para `stderr` via `print(..., file=sys.stderr)` com `exit 1`.
* `log_files/` não existe; `LOG_FOLDER='log_files'` em `logging_template.py:39`.
* Prefixo `LOG_OUTPUT_PREFIX='<<eqs>>'` legado (`eqs`/`Base.gov.pt`) — deve ser `<<nif-pt>>`.

## 2. Funcionalidades do Template

* **Níveis:** `LOG_LEVEL_GLOBAL=INFO`, `LOG_LEVEL_FILE=INFO`, `LOG_LEVEL_CONSOLE=INFO` (`logging_template.py:34`).
* **Saída:** `log_files/general_app.log` (`logging_template.py:40`), `RotatingFileHandler` custom (não `logging.handlers.RotatingFileHandler`).
* **Rotação:** `LOG_MAX_BYTES=10485760` (10 MB), `LOG_MAX_RECORDS=5000`, `LOG_MAX_BACKUP=10` (`logging_template.py:64`), cascata `_archive_name(i)=base_idx.ext`.
* **Formatos:** `LOG_FORMAT_FILE='<<eqs>> %(asctime)s - %(name)s - %(levelname)s - %(message)s'` + ultra-debug `%(filename)s - %(funcName)s - %(lineno)d` se `FILE_ULTRA_DEBUG=True`.
* **API:** `LOGGER=logging.getLogger(__name__)`, `ini_logging()` legacy, `setup_logging()` wrapper, idempotente `if LOGGER.handlers: return`.

## 3. Livro de Estilo (9 estilos, `logging_template.py:234`)

| # | Estilo | Char | Width | Nível | Uso |
|---|--------|------|-------|-------|-----|
| 1 | `BANNER_APP_START` | `=` | 49 | INFO | Início app |
| 2 | `BANNER_APP_END` | `=` | 49 | INFO | Fim app |
| 3 | `BANNER_SECTION_START` | `-` | 49 | INFO | Secção |
| 4 | `BANNER_SECTION_END` | `-` | 49 | INFO | Fim secção |
| 5 | `BANNER_FUNCTION` | `~` | 49 | DEBUG | Função crítica |
| 6 | `TAG` | `[tag]` | — | herda | `[api]`, `[db]` |
| 7 | `SEPARATOR` | `-`/`.` | 49 | DEBUG | Separador |
| 8 | `BOX` | `-\|` | 49 | INFO | Tabela/resumo |
| 9 | `TIMING` | `%.2fs` | — | INFO/DEBUG | `time.perf_counter()` |

Regras globais: `R1 WIDTH=49 ≤79`, `R4 [tag] lowercase`, `R6 f"{' title ':=^49}"`, `R9 %.2fs` sempre `time.perf_counter()`.

## 4. Integração Futura (roadmap `v0.3`)

### 4.1 Código

```python
from Logging.logging_template import setup_logging
import time

logger = setup_logging()
logger.info("=" * 49)
logger.info(f"{' nif-pt a iniciar ':=^49}")
logger.info("=" * 49)

t = time.perf_counter()
# ... consultar_nif / importar ...
logger.info("Consulta concluída em %.2fs", time.perf_counter() - t)

logger.info("=" * 49)
logger.info(f"{' nif-pt finalizado ':=^49}")
logger.info("=" * 49)
```

### 4.2 Configuração

```python
# Logging/logging_template.py — corrigir:
LOG_OUTPUT_PREFIX = '<<nif-pt>>'
LOG_FOLDER = 'log_files'
LOG_OUTPUT_FILE = 'log_files/nif_pt.log'
LOG_LEVEL_GLOBAL = logging.INFO
```

### 4.3 Exemplo de saída

```
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - =============== nif-pt a iniciar ===============
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - [api] GET nif.pt?q=509442013 -> 200 OK
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - [db] NIF 509442013 guardado em nif_pt
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - Consulta concluída em 0.85s
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ============== nif-pt finalizado ===============
<<nif-pt>> 2026-09-10 02:15:32 - __main__ - INFO - ===================================================
```

## 5. Referências

* `Logging/logging_template.py:90` `RotatingFileHandler` + `logging_template.py:168` `ini_logging()`
* https://github.com/nunoetome/my_python_starter_kit — origem do template (v2.1, 2026-06-19)
