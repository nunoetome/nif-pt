# Manual — NIF.pt

Ferramenta para consulta de NIFs portugueses via [nif.pt](http://www.nif.pt) e armazenamento local dos resultados.

---

## Índice

- [Arquitetura](#arquitetura)
- [Configuração](#configuração)
- [Consulta de NIF](#consulta-de-nif)
- [Armazenamento em SQLite](#armazenamento-em-sqlite)
- [Armazenamento em Azure SQL](#armazenamento-em-azure-sql)
- [Estrutura da base de dados](#estrutura-da-base-de-dados)
- [Exemplos práticos](#exemplos-práticos)
- [Resolução de problemas](#resolução-de-problemas)

---

## Arquitetura

O sistema é composto por três scripts que funcionam em pipeline:

```
consulta_nif.py  ──JSON──>  importar_nif_sqlite.py  (SQLite local)
                        ──>  importar_nif.py          (Azure SQL)
```

1. **consulta_nif.py** — recebe um NIF como argumento e devolve o JSON da API nif.pt para stdout.
2. **importar_nif_sqlite.py** — lê o JSON do stdin e guarda-o numa base SQLite local.
3. **importar_nif.py** — lê o JSON do stdin e guarda-o numa base Azure SQL.

Toda a configuração está centralizada no `config/config.yaml` e `config/.env`.

---

## Configuração

### config.yaml (`config/config.yaml`)

```yaml
consulta_nif:
  api_base: "http://www.nif.pt"

importar_nif_sqlite:
  db_path: "data/nif_pt.db"
  tabela: "nif_pt"

importar_nif:
  sql_server: "kiwa-pt-operations.database.windows.net"
  sql_database: "kiwa-pt-operations"
  sql_schema: "stg_nunotome"
  sql_driver: "ODBC Driver 18 for SQL Server"
  tabela_staging: "nif_pt_stg"
```

### .env (`config/.env`)

Guarda segredos. Não versionar.

```env
AZURE_USER=Nunotome
AZURE_PALAVRA_CHAVE=********
NIF-PT-KEY=********
```

> Para obter uma chave da API nif.pt, solicitar em http://www.nif.pt/contactos/api/

---

## Consulta de NIF

```bash
python consulta_nif.py <NIF>
```

**Exemplo:**

```bash
python consulta_nif.py 509442013
```

**Exemplo de output:**

```json
{
  "nif": "509442013",
  "valido": true,
  "fonte": "nif.pt",
  "erro": null,
  "dados": {
    "nif": 509442013,
    "title": "Nexperience, Unipessoal, Lda",
    "status": "active",
    "cae": ["62010", "63120"],
    "contacts": {
      "email": "info@nex.pt",
      "phone": "220 198 228",
      "website": "www.nex.pt"
    }
  },
  "nif_valido_formato": true,
  "creditos": {
    "used": "free",
    "left": { "month": 999, "day": 99, "hour": 9, "minute": 0, "paid": 0 }
  }
}
```

### Validação do NIF

O script valida o dígito de controlo do NIF antes de consultar a API. Se o formato for inválido, o script termina com erro antes de fazer qualquer pedido à rede.

### Códigos de erro

| Campo `erro` | Significado |
|---|---|
| `NIF-PT-KEY não encontrada no .env` | Chave da API não configurada |
| `Timeout na consulta à API nif.pt` | API não respondeu dentro do tempo limite |
| `Erro de rede: ...` | Falha de ligação (DNS, rede, etc.) |
| `Resposta inválida (não JSON) da API` | API devolveu conteúdo inesperado |
| `error` / `No records found` | NIF não encontrado na base de dados da API |

---

## Armazenamento em SQLite

Guarda o JSON de resposta numa base SQLite local.

```bash
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
```

A base de dados é criada automaticamente no caminho definido em `config.yaml` (`db_path`). A tabela é criada se não existir.

### Esquema da tabela

```sql
CREATE TABLE nif_pt (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nif             INTEGER NOT NULL,
    dados           TEXT NOT NULL,
    data_consulta   TEXT NOT NULL DEFAULT (datetime('now'))
);
```

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | INTEGER | Chave primária auto-incremento |
| `nif` | INTEGER | NIF consultado |
| `dados` | TEXT | JSON completo da resposta da API |
| `data_consulta` | TEXT | Data e hora do registo (YYYY-MM-DD HH:MM:SS) |

### Consultar dados guardados

```bash
python -c "
import sqlite3, pathlib
db = pathlib.Path('data/nif_pt.db')
conn = sqlite3.connect(str(db))
cur = conn.cursor()
for row in cur.execute('SELECT id, nif, data_consulta FROM nif_pt'):
    print(row)
"
```

---

## Armazenamento em Azure SQL

Guarda o JSON de resposta numa tabela no Azure SQL.

```bash
python consulta_nif.py 509442013 | python importar_nif.py
```

### Pré-requisitos

- Driver ODBC 18 for SQL Server instalado
- Credenciais Azure configuradas no `.env`
- Tabela criada antecipadamente com o script `sql/01_criar_tabelas.sql`

### Schema

As tabelas são criadas no schema `stg_nunotome` (configurável em `config.yaml`).

---

## Estrutura da base de dados

### SQLite — `nif_pt`

```sql
CREATE TABLE nif_pt (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nif             INTEGER NOT NULL,
    dados           TEXT NOT NULL,
    data_consulta   TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### SQL Server — `stg_nunotome.nif_pt_stg`

```sql
CREATE TABLE stg_nunotome.nif_pt_stg (
    id                      BIGINT IDENTITY(1,1) NOT NULL,
    nif                     BIGINT NOT NULL,
    nif_valido_formato      BIT NULL,
    data_consulta           DATETIME2 NOT NULL DEFAULT GETDATE(),
    consulta_origem         NVARCHAR(50) NULL DEFAULT 'nif.pt',
    data_staging            DATETIME2 NOT NULL DEFAULT GETDATE(),
    processado              BIT NOT NULL DEFAULT 0,
    seo_url                 NVARCHAR(255) NULL,
    title                   NVARCHAR(500) NULL,
    -- ... restantes colunas normalizadas ...
    CONSTRAINT pk_nif_pt_stg PRIMARY KEY CLUSTERED (id)
);
```

---

## Exemplos práticos

### 1. Consultar e guardar em SQLite

```bash
python consulta_nif.py 509442013 | python importar_nif_sqlite.py
```

### 2. Consultar e guardar em Azure SQL

```bash
python consulta_nif.py 509442013 | python importar_nif.py
```

### 3. Consultar e guardar em ambos

```bash
python consulta_nif.py 509442013 | tee >(python importar_nif_sqlite.py) | python importar_nif.py
```

### 4. Guardar JSON para ficheiro

```bash
python consulta_nif.py 509442013 > resultado.json
```

### 5. Importar de ficheiro JSON

```bash
python importar_nif_sqlite.py < resultado.json
```

### 6. Consultar histórico na SQLite

```bash
python -c "
import sqlite3
conn = sqlite3.connect('data/nif_pt.db')
for id, nif, data in conn.execute('SELECT id, nif, data_consulta FROM nif_pt ORDER BY data_consulta DESC'):
    print(f'{id}: NIF {nif} — {data}')
"
```

---

## Resolução de problemas

### "NIF-PT-KEY não encontrada no .env"

1. Abrir `config/.env`
2. Verificar se existe a linha `NIF-PT-KEY=...`
3. Se não existir, solicitar chave em http://www.nif.pt/contactos/api/

### "No records found"

O NIF é válido mas não existe na base de dados pública do nif.pt. Pode corresponder a:
- NIF de pessoa singular sem atividade registada
- NIF recente ainda não indexado

### Erro de ligação ao Azure SQL

1. Verificar se o IP atual está autorizado nas firewall rules do Azure SQL
2. Confirmar que as credenciais no `.env` estão corretas
3. Verificar se o `ODBC Driver 18 for SQL Server` está instalado

### SQLite: "database is locked"

O SQLite em modo WAL (Write-Ahead Logging) resolve a maioria dos conflitos. Se persistir, garantir que apenas um processo escreve de cada vez.

---

## Ficheiros do projeto

```
nif_pt/
├── consulta_nif.py           # Consulta a API nif.pt
├── importar_nif_sqlite.py    # Guarda em SQLite
├── importar_nif.py           # Guarda em Azure SQL
├── config/
│   ├── config.py             # Leitor de configuração
│   ├── config.yaml           # Configurações (versionado)
│   └── .env                  # Segredos (NÃO versionar)
├── sql/
│   └── 01_criar_tabelas.sql  # DDL para SQL Server
├── data/
│   └── nif_pt.db             # Base SQLite (gerada, não versionar)
├── requirements.txt
└── MANUAL.md                 # Este documento
```
