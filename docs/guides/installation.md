# Guia de Instalação — nif-pt v1.0.0

> Complemento de [MANUAL.md §4](../../MANUAL.md#4-instalação). Dual PowerShell 5.1 + Git Bash (MINGW64) — Windows.

## 1. Pré-requisitos

Ver [MANUAL.md §3](../../MANUAL.md#3-pré-requisitos): Python `>=3.11`, `ODBC Driver 18` (só Azure), chave `nif.pt` (`NIF-PT-KEY` com hífen).

## 2. Clonar

```bash
git clone https://github.com/nunoetome/nif-pt.git
cd nif-pt
git checkout v1.0.0   # stable; dev para desenvolvimento
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

## 4. Dependências v1.0.0

```bash
pip install -r requirements.txt
# requirements.txt pinado:
# requests>=2.31.0
# pyyaml>=6.0.1
# python-dotenv>=1.0.0
# pyodbc>=5.0.0
pip list | findstr -i "requests pyyaml dotenv pyodbc"
```

*Fix v1.0.0:* `yaml` → `pyyaml` + falta `python-dotenv`/`pyodbc` corrigido. Se `ModuleNotFoundError: yaml`: `pip uninstall yaml -y; pip install -r requirements.txt`.

## 5. ODBC Driver 18 (só Azure SQL)

* **Windows:** https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server → `msodbcsql.msi`
* **Verificar:** `Get-OdbcDriver -Name "*ODBC Driver*"` (PS) ou `odbcinst -q -d` (Linux)
* `config.yaml:35` espera `ODBC Driver 18 for SQL Server` + `Encrypt=yes;TrustServerCertificate=no` (`importar_nif.py:47`).

## 6. `.env` + `config.yaml` (37L)

```powershell
Copy-Item config\.env.example config\.env
# Editar config\.env — UTF-8, sem BOM:
# NIF-PT-KEY=sua_chave  (com hífen! http://www.nif.pt/contactos/api/)
# AZURE_USER=seu_user
# AZURE_PALAVRA_CHAVE=sua_password
```

Ver [MANUAL.md §5](../../MANUAL.md#5-configuração) — 11 chaves default (`timeout 10`, `max_tentativas_global 5 / minuto 3 / hora 2 / dia 0`).

## 7. Verificação v1.0.0

```powershell
python -c "from config.config import get_config; c=get_config('consulta_nif'); print('OK' if c.get('NIF_PT_KEY') else 'FALTA NIF-PT-KEY')"
python -c "import consulta_nif; help(consulta_nif.validar_nif)"
python -c "from utils.error_handler import tratar_erro; help(tratar_erro)"
python -c "from utils.error_handler import init_error_table; init_error_table(); print('nif_api_erros OK')"
python consulta_nif.py 509442013
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
Get-Content log_files\nif_pt.log -Tail 20  # <<nif-pt>> BOX/TAG/TIMING
python -c "import pyodbc; print(pyodbc.version)"  # só Azure
```

## 8. Atualização

```bash
git fetch --tags
git checkout v1.0.0
pip install -r requirements.txt
# Opcional: aplicar DDL erros no Azure
sqlcmd -S kiwa-pt-operations.database.windows.net -d kiwa-pt-operations -i sql/02_criar_tabela_erros.sql
# SQLite cria nif_api_erros automaticamente (init_error_table)
```

## 9. Desinstalação

```powershell
deactivate
Remove-Item -Recurse -Force .venv, data, log_files
# .env mantém-se (ignorado) — apagar manualmente se necessário
```
