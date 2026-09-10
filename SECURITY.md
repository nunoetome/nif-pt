# Política de Segurança — nif-pt

## 1. Segredos

* **Nunca commitar** `config/.env` (`.gitignore:7` `config/.env`).
* Template commitado: `config/.env.example` (sem valores reais).
* Variáveis: `NIF-PT-KEY` (API `nif.pt`), `AZURE_USER`, `AZURE_PALAVRA_CHAVE` (`config/config.py:35`).
* Verificação: `git grep -i "AZURE_PALAVRA_CHAVE\|NIF-PT-KEY" --cached` deve estar vazio.

## 2. Se um segredo for exposto

1. Rodar imediatamente a chave em http://www.nif.pt/contactos/api/ e no Portal Azure.
2. `git filter-repo` ou `BFG` para limpar histórico.
3. `git push --force` após coordenar com colaboradores.

## 3. Boas práticas

* `NIF-PT-KEY` com hífen — `os.getenv("NIF-PT-KEY")` funciona com `python-dotenv` mas frágil em Docker/systemd; roadmap `v0.3` migra para `NIF_PT_KEY`.
* Não logar `NIF-PT-KEY` ou `AZURE_PALAVRA_CHAVE` (mesmo em `DEBUG`).
* ODBC 18 exige `Encrypt=yes` (`importar_nif.py:34`) — não usar `TrustServerCertificate=yes` em prod.

## 4. Reportar vulnerabilidade

Abrir issue privado ou contactar `nunoetome` via GitHub Security Advisories.

## 5. Dependências

* `requests`, `pyyaml`, `python-dotenv`, `pyodbc` — `pip audit` recomendado antes de cada release.
* `ODBC Driver 18` — manter atualizado via https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server.
