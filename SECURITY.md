# Política de Segurança — nif-pt

## 1. Segredos

* **Nunca commitar** `config/.env` (`.gitignore:7` `config/.env`).
* Template commitado: `config/.env.example` (sem valores reais).
* Variável: `NIF-PT-KEY` (API `nif.pt`) (`config/config.py:120` `os.getenv("NIF-PT-KEY")`).
* Verificação: `git grep -i "NIF-PT-KEY" --cached` deve estar vazio.

> Removido em v1.2.0: `AZURE_USER`, `AZURE_PALAVRA_CHAVE`, `pyodbc`, `ODBC Driver 18`. Não há segredos Azure.

## 2. Se um segredo for exposto

1. Rodar imediatamente a chave em http://www.nif.pt/contactos/api/.
2. `git filter-repo` ou `BFG` para limpar histórico.
3. `git push --force` após coordenar com colaboradores.

## 3. Boas práticas

* `NIF-PT-KEY` com hífen — `os.getenv("NIF-PT-KEY")` funciona com `python-dotenv` mas frágil em Docker/systemd; roadmap `v1.3` migra para `NIF_PT_KEY`.
* Não logar `NIF-PT-KEY` (mesmo em `DEBUG`) — mascarada `***XXXX` em `config/config.py:124` e `consulta_nif.py:261`.
* `data/nif_pt.db` e `log_files/nif_pt.log` estão em `.gitignore` — contêm dados de NIFs e `run_id`; não commitar.

## 4. Reportar vulnerabilidade

Abrir issue privado ou contactar `nunoetome` via GitHub Security Advisories.

## 5. Dependências

* `requests`, `pyyaml`, `python-dotenv` — `pip audit` recomendado antes de cada release.
