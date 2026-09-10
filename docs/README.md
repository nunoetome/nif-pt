# Documentação Técnica — nif-pt v1.2.0

Índice para além do [MANUAL.md](../MANUAL.md) (manual de utilizador) e [README.md](../README.md) (porta de entrada).

## Estrutura v1.2.0

| Pasta / Ficheiro | Descrição | Linhas |
|------------------|-----------|--------|
| [technical.md](technical.md) | **Documentação técnica consolidada** — C4 1-2, sequência cache, atividades cache, classes, ER 5/15/6c, componentes, catálogo file:line, config cache, camada de erros, cache, logging R1-R9, ADRs, pipeline, help | 500+ |
| [api/help.md](api/help.md) | **Help Python PEP 257** — `help(validar_nif)`, `help(is_nif_recente)`, `help(tratar_erro)` verificado | 200+ |
| [architecture/architecture.md](architecture/architecture.md) | Arquitetura C4 + 10 ADRs (ADR-010 cache) | 200+ |
| [architecture/diagrams.md](architecture/diagrams.md) | Fonte Mermaid de todos os diagramas (pipeline cache, sequência cache, atividades cache, classes, ER 5/15/6c, estados cache, contentores) | 300+ |
| [database/schema.md](database/schema.md) | ER + catálogo 5c/15c/6c — `nif_pt`, `nif_api_erros`, `nif_ignorados` | 350+ |
| [database/ddl-history.md](database/ddl-history.md) | Evolução DDL — `nif_pt` 5c + `nif_api_erros` 15c + `nif_ignorados` 6c + remoção Azure | 50+ |
| [api/nif-pt-api.md](api/nif-pt-api.md) | Contrato `nif.pt` + tabela classificação `rate_limit_*` + retry `60s/3600s` | 176 |
| [requirements/requirements.md](requirements/requirements.md) | Requisitos funcionais/não-funcionais, casos de uso (UC-06 cache), roadmap | 120+ |
| [guides/installation.md](guides/installation.md) | Instalação dual PowerShell/Bash (só SQLite, sem ODBC) | 100 |
| [guides/logging.md](guides/logging.md) | Logging `logging_orchestrator` R1-R9, `<<nif-pt>>`, `nif_pt.log` + TAG `[cache]` | 120 |
| [glossary.md](glossary.md) | Glossário PT — NIF, Mod-11, CAE, WAL, `nif_ignorados`, `cache_recente`, `run_id` | 30+ |

## Leitura recomendada (ordem)

1. [README.md](../README.md) — quickstart 3 comandos + badges v1.2.0
2. [MANUAL.md](../MANUAL.md) — manual 15 capítulos (instalação, pipeline cache, payload ignorado, troubleshooting)
3. [technical.md](technical.md) — visão técnica com Mermaid (C4, ER 5/15/6c, sequência cache)
4. [api/help.md](api/help.md) — `help()` Python verificado
5. [architecture/architecture.md](architecture/architecture.md) — ADRs (incl. ADR-010 cache)
6. [database/schema.md](database/schema.md) — ER 5/15/6c + `nif_ignorados` 6c
7. [api/nif-pt-api.md](api/nif-pt-api.md) — contrato + `rate_limit_*`

## Convenções

* Markdown + Mermaid versionados (sem gerador externo; `mkdocs` opcional v1.3).
* `architecture/diagrams.md` + `technical.md` são fonte única — importados por referência.
* Caminhos relativos à raiz `nif-pt/`; `file:line` em `technical.md` §8.
* Docstrings PEP 257 em todos os módulos — `help(xxx)` funciona (ver `api/help.md`).
* Logging R1–R9 com `WIDTH=49`, `<<nif-pt>>`, `RotatingFileHandler` 10MB/5000/10, TAG `[cache][run]`.

## Help Python (v1.2.0)

```python
python -c "import consulta_nif; help(consulta_nif.validar_nif)"
python -c "from utils.cache_validator import is_nif_recente, registar_ignorado; help(is_nif_recente)"
python -c "from utils.error_handler import tratar_erro; help(tratar_erro)"
python -m pydoc consulta_nif
python -m pydoc utils.cache_validator
python -m pydoc utils.error_handler
python -m pydoc config.config
```

Ver [api/help.md](api/help.md) para transcrições verificadas.

## Histórico

* `v1.2.0` (unreleased) — validação cache `utils/cache_validator.py` 407L + `nif_ignorados` 6c + remoção total Azure (`importar_nif.py`, `sql/0*`, `pyodbc`, `AZURE_*`).
* `v1.1.0` (2026-09-11) — `run_id` UUID v4 + `ContextVar` + `--run-id` + 5/15c `run_id`.
* `v1.0.0` (2026-09-10) — `error_handler` + `nif_api_erros` 15c + `logging_orchestrator`.
* Ver [CHANGELOG.md](../CHANGELOG.md) e tags `v.0.1.0-alpha` / `v0.2.0-beta` / `v1.0.0` / `v1.1.0`.

## Como contribuir

Ver [CONTRIBUTING.md](../CONTRIBUTING.md) e [SECURITY.md](../SECURITY.md).
