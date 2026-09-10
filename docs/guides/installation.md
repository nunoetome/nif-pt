# Guia de Instalação — nif-pt

> Complemento de [MANUAL.md — Instalação](../../MANUAL.md#4-instalação). Passo-a-passo por SO.

## 1. Pré-requisitos

Ver [MANUAL.md §3](../../MANUAL.md#3-pré-requisitos) — Python `>=3.11`, `ODBC Driver 18` (só Azure), chave `nif.pt`.

## 2. Clonar

```bash
git clone https://github.com/nunoetome/nif-pt.git
cd nif-pt
git checkout prod
```

## 3. `venv` por Shell

### 3.1 Git Bash (MINGW64) — recomendado no teu setup

```bash
python -m venv venv
source venv/Scripts/activate
which python  # .../nif-pt/venv/Scripts/python.exe
```

### 3.2 PowerShell

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
# Erro de execução?:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 3.3 cmd.exe

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

> **Armadilhas:** `source venv/bin/activate` é Linux; `.\venv\Scripts\Activate.ps1` só em PowerShell; `\` vs `/`.

## 4. Dependências

```bash
pip install -r requirements.txt
pip list | findstr -i "requests pyyaml dotenv pyodbc"
# deve mostrar: requests, pyyaml, python-dotenv, pyodbc
```

*Se `ModuleNotFoundError: yaml`*: `pip uninstall yaml -y; pip install pyyaml` (bug `v0.2.0-beta`).

## 5. ODBC Driver 18 (só Azure SQL)

* **Windows:** https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server → `msodbcsql.msi`
* **Verificar:** `Get-OdbcDriver -Name "*ODBC Driver*"` (PowerShell) ou `odbcinst -q -d` (Linux)
* `config/config.yaml:26` espera `ODBC Driver 18 for SQL Server`.

## 6. `.env`

```bash
cp config/.env.example config/.env
# Editar config/.env com editor (VS Code/Notepad) — UTF-8, sem BOM
```

Conteúdo mínimo:

```env
NIF-PT-KEY=sua_chave
AZURE_USER=seu_user
AZURE_PALAVRA_CHAVE=sua_password
```

Ver [MANUAL.md §5](../../MANUAL.md#5-configuração).

## 7. Verificação

```bash
python -c "from config.config import get_config; c=get_config('consulta_nif'); print('OK' if c.get('NIF_PT_KEY') else 'FALTA NIF-PT-KEY')"
python consulta_nif.py 509442013 | head -20
# deve devolver JSON com "erro": null
python -c "import pyodbc; print(pyodbc.version)"  # só se Azure
```

## 8. Atualização

```bash
git pull origin prod
pip install -r requirements.txt
```

## 9. Desinstalação

```bash
deactivate
rm -rf venv/ data/ log_files/
# .env mantém-se (ignorado) — apagar manualmente se necessário
```
