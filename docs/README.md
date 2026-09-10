# Documentação Técnica — nif-pt v1.0.0

Índice para além do [MANUAL.md](../MANUAL.md) (manual de utilizador) e [README.md](../README.md) (porta de entrada).

## Estrutura v1.0.0

| Pasta / Ficheiro | Descrição | Linhas |
|------------------|-----------|--------|
| [technical.md](technical.md) | **Documentação técnica consolidada** — C4 1-2, sequência, atividades, classes, ER, componentes, catálogo file:line, config, camada de erros, logging R1-R9, ADRs, pipeline, help | 400+ |
| [api/help.md](api/help.md) | **Help Python PEP 257** — `help(validar_nif)`, `help(tratar_erro)` verificado com `python -m pydoc` | 150+ |
| [architecture/architecture.md](architecture/architecture.md) | Arquitetura C4 + 8 ADRs | 161 |
| [architecture/diagrams.md](architecture/diagrams.md) | Fonte Mermaid de todos os diagramas (pipeline, sequência, atividades, classes, ER, estados, contentores) | 257 |
| [database/schema.md](database/schema.md) | ER + catálogo 37c/40c + 14c `nif_api_erros` dual | 244 |
| [database/ddl-history.md](database/ddl-history.md) | Evolução DDL `01_criar_tabelas.sql` + `02_criar_tabela_erros.sql` | 34 |
| [api/nif-pt-api.md](api/nif-pt-api.md) | Contrato `nif.pt` + tabela classificação `rate_limit_*` + retry `60s/3600s` | 176 |
| [requirements/requirements.md](requirements/requirements.md) | Requisitos funcionais/não-funcionais, casos de uso, roadmap | 80 |
| [guides/installation.md](guides/installation.md) | Instalação dual PowerShell/Bash (Windows `.venv/Scripts`) | 100 |
| [guides/logging.md](guides/logging.md) | Logging `logging_orchestrator` R1-R9, `<<nif-pt>>`, `nif_pt.log` | 120 |
| [glossary.md](glossary.md) | Glossário PT — NIF, Mod-11, CAE, WAL, ODBC, `nif_api_erros`, `rate_limit_*` | 20 |

## Leitura recomendada (ordem)

1. [README.md](../README.md) — quickstart 3 comandos + badges v1.0.0
2. [MANUAL.md](../MANUAL.md) — manual 15 capítulos (instalação Windows, pipe, troubleshooting)
3. [technical.md](technical.md) — visão técnica com Mermaid (C4, ER, sequência)
4. [api/help.md](api/help.md) — `help()` Python verificado
5. [architecture/architecture.md](architecture/architecture.md) — ADRs
6. [database/schema.md](database/schema.md) — ER 37/40/14c
7. [api/nif-pt-api.md](api/nif-pt-api.md) — contrato + `rate_limit_*`

## Convenções

* Markdown + Mermaid versionados (sem gerador externo; `mkdocs` opcional v1.1).
* `architecture/diagrams.md` + `technical.md` são fonte única — importados por referência.
* Caminhos relativos à raiz `nif-pt/`; `file:line` em `technical.md` §8.
* Docstrings PEP 257 em todos os módulos — `help(xxx)` funciona (ver `api/help.md`).
* Logging R1–R9 com `WIDTH=49`, `<<nif-pt>>`, `RotatingFileHandler` 10MB/5000/10.

## Help Python (v1.0.0)

```python
python -c "import consulta_nif; help(consulta_nif.validar_nif)"
python -c "from utils.error_handler import tratar_erro; help(tratar_erro)"
python -m pydoc consulta_nif
python -m pydoc utils.error_handler
python -m pydoc config.config
```

Ver [api/help.md](api/help.md) para transcrições verificadas.

## Histórico

* `v1.0.0` (2026-09-10) — `error_handler` 612L + `nif_api_erros` 14c + `logging_orchestrator` 580L + `timeout 10s` + `technical.md` + `api/help.md`.
* Ver [CHANGELOG.md](../CHANGELOG.md) e tags `v.0.1.0-alpha` / `v0.2.0-beta` / `v1.0.0`.

## Como contribuir

Ver [CONTRIBUTING.md](../CONTRIBUTING.md) e [SECURITY.md](../SECURITY.md).
