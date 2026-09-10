# Guia de Instalação — nif-pt v1.2.0

> Complemento de [MANUAL.md §4](../../MANUAL.md#4-instalação). Dual PowerShell 5.1 + Git Bash (MINGW64) — Windows.

## 1. Pré-requisitos

Ver [MANUAL.md §3](../../MANUAL.md#3-pré-requisitos): Python `>=3.11`, chave `nif.pt` (`NIF-PT-KEY` com hífen). Sem ODBC/Azure.

## 2. Clonar

```bash
git clone https://github.com/nunoetome/nif-pt.git
cd nif-pt
git checkout v1.2.0   # stable; dev para desenvolvimento
```

## 3. `venv` por Shell

### 3.1 PowerShell (Windows — o teu caso)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
# se bloquear: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Get-Command python | Format-List Source  # ...\nif-pt\.venv\Scripts\python.exe
python --version  # Python 3.11.x
```

### 3.2 Git Bash (MINGW64)

```bash
python -m venv .venv
source .venv/Scripts/activate
which python  # .../nif-pt/.venv/Scripts/python.exe
```

> **Armadilhas:** `source .venv/bin/activate` é Linux; `.\.venv\Scripts\Activate.ps1` só PowerShell; `\` vs `/`.

### 3.3 cmd.exe

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

## 4. Dependências v1.2.0

```bash
pip install -r requirements.txt
# requirements.txt pinado:
# requests>=2.31.0
# pyyaml>=6.0.1
# python-dotenv>=1.0.0
pip list | findstr -i "requests pyyaml dotenv"
```

*Sem `pyodbc` desde v1.2.0 (remoção Azure).* Se `ModuleNotFoundError: yaml`: `pip uninstall yaml -y; pip install -r requirements.txt`.

## 5. `.env` + `config.yaml` (31L)

```powershell
Copy-Item config\.env.example config\.env
# Editar config\.env — UTF-8, sem BOM:
# NIF-PT-KEY=sua_chave  (com hífen! http://www.nif.pt/contactos/api/)
```

Ver [MANUAL.md §5](../../MANUAL.md#5-configuração) — 14 chaves default (`timeout 10`, `max_tentativas_global 5 / minuto 3 / hora 2 / dia 0` + `cache_ativo true / cache_antiguidade_dias 30 / cache_tabela_ignorados nif_ignorados`).

> Removido v1.2.0: `AZURE_USER`, `AZURE_PALAVRA_CHAVE`, `importar_nif` block, `sql/` DDL Azure.

## 6. Verificação v1.2.0

```powershell
python -c "from config.config import get_config; c=get_config('consulta_nif'); print('OK' if c.get('NIF_PT_KEY') else 'FALTA NIF-PT-KEY'); print(c.get('cache_ativo'), c.get('cache_antiguidade_dias'))"
python -c "import consulta_nif; help(consulta_nif.validar_nif)"
python -c "from utils.cache_validator import is_nif_recente, registar_ignorado; help(is_nif_recente)"
python -c "from utils.cache_validator import init_cache_tables; init_cache_tables(); print('nif_ignorados OK')"
python -c "from utils.error_handler import init_error_table; init_error_table(); print('nif_api_erros OK')"
python consulta_nif.py 509442013
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
# 2ª execução deve ser cache:
python consulta_nif.py 509442013
# -> {"ignorado": true, "motivo": "cache_recente", ...}
Get-Content log_files\nif_pt.log -Tail 20  # <<nif-pt>> BOX/TAG [cache] TIMING
```

## 7. Atualização

```bash
git fetch --tags
git checkout v1.2.0
pip install -r requirements.txt
# pip uninstall pyodbc -y  # se vinha de v1.1.0
# SQLite migra sozinho: nif_ignorados criado em consulta_nif.py:536 init_cache_tables()
```

## 8. Desinstalação

```powershell
deactivate
Remove-Item -Recurse -Force .venv, data, log_files
# .env mantém-se (ignorado) — apagar manualmente se necessário
```
