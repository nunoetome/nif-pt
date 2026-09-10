# Documentação Técnica — nif-pt

Índice da documentação para além do [MANUAL.md](../MANUAL.md) (manual de instruções na raiz).

## Estrutura

| Pasta / Ficheiro | Descrição |
|------------------|-----------|
| [requirements/requirements.md](requirements/requirements.md) | Requisitos funcionais/não-funcionais, casos de uso, atores |
| [architecture/architecture.md](architecture/architecture.md) | Arquitetura C4 (níveis 1-2) + ADRs |
| [architecture/diagrams.md](architecture/diagrams.md) | Fonte de todos os diagramas Mermaid |
| [database/schema.md](database/schema.md) | Esquemas BD — ER + catálogo 37/40 colunas |
| [database/ddl-history.md](database/ddl-history.md) | Evolução do DDL (`sql/01_criar_tabelas.sql`) |
| [api/nif-pt-api.md](api/nif-pt-api.md) | Contrato da API `nif.pt` (`?json=1&q=&key=`) |
| [guides/installation.md](guides/installation.md) | Guia detalhado de instalação (complemento do MANUAL) |
| [guides/logging.md](guides/logging.md) | Integração do `Logging/logging_template.py` |
| [glossary.md](glossary.md) | Glossário PT (NIF, CAE, WAL, Mod-11, ODBC...) |

## Convenções

* Markdown + Mermaid versionados (sem gerador externo nesta fase; `mkdocs` opcional para `v0.4`).
* Diagramas em `architecture/diagrams.md` são a **fonte única** — importados por referência no MANUAL e nos restantes docs.
* Todos os caminhos são relativos à raiz `nif-pt/`.

## Como contribuir

Ver [CONTRIBUTING.md](../CONTRIBUTING.md) e [SECURITY.md](../SECURITY.md).

## Histórico

Ver [CHANGELOG.md](../CHANGELOG.md) e tags `v.0.1.0-alpha` / `v0.2.0-beta`.
