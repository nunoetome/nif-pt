# Diagramas — nif-pt

> Fonte única de todos os diagramas Mermaid. Copiar para https://mermaid.live para validar. Referenciados em `MANUAL.md`, `architecture.md`, `schema.md`.

## 1. Pipeline (graph LR)

```mermaid
graph LR
    U[Utilizador<br/>NIF 9 dígitos] --> C[consulta_nif.py<br/>validar_nif + requests]
    C -->|stdout JSON<br/>ensure_ascii=False| S[importar_nif_sqlite.py<br/>JSON bruto]
    C -->|stdout JSON| A[importar_nif.py<br/>36 cols normalizadas]
    S --> DB1[(data/nif_pt.db<br/>id, nif, dados, data_consulta<br/>PRAGMA WAL)]
    A --> DB2[(Azure SQL<br/>stg_nunotome.nif_pt_stg<br/>40 cols)]
    DB2 -. MERGE futuro .-> DB3[(stg_nunotome.nif_pt<br/>37 cols PK nif)]
    CFG[config.yaml + .env<br/>get_config()] -.-> C & S & A
```

## 2. Sequência — Consulta (sequenceDiagram)

```mermaid
sequenceDiagram
    participant U as Utilizador
    participant CLI as consulta_nif.py:main
    participant V as validar_nif
    participant CFG as get_config
    participant API as nif.pt<br/>?json=1&q=&key=
    participant IMP as importar_*.py

    U->>CLI: python consulta_nif.py 509442013
    CLI->>CLI: isdigit? (consulta_nif.py:98)
    alt NIF não dígito
        CLI-->>U: {"erro":"NIF deve conter apenas dígitos"} exit 1
    end
    CLI->>CFG: get_config("consulta_nif")
    CFG-->>CLI: api_base, timeout, NIF-PT-KEY
    alt NIF-PT-KEY falta
        CLI-->>U: {"erro":"NIF-PT-KEY não encontrada"} exit 1
    end
    CLI->>V: validar_nif(nif)
    V-->>CLI: true/false (afeta campo valido)
    CLI->>API: GET ?json=1&q=509442013&key=xxx timeout=1000
    alt Timeout
        API-->>CLI: requests.Timeout
        CLI-->>U: {"erro":"Timeout..."} exit 1
    end
    API-->>CLI: 200 JSON {result, records, credits}
    alt result != success
        CLI-->>U: {"erro":"No records found"} exit 1
    else success
        CLI->>CLI: records.get(nif) fallback first_key
        CLI-->>U: stdout JSON {nif,valido,fonte,erro:null,dados,creditos}
        U->>IMP: stdin JSON
        IMP->>IMP: json.loads + valida erro/nif
        IMP-->>U: stderr "NIF x guardado/inserido" exit 0
    end
```

## 3. Atividades — Validação e Request (graph TD)

```mermaid
graph TD
    A[argv NIF] --> B{nif.isdigit?}
    B -- não --> E1[erro + exit 1]
    B -- sim --> C[get_config<br/>api_base, timeout, key]
    C --> D{API_KEY existe?}
    D -- não --> E2[erro NIF-PT-KEY + exit 1]
    D -- sim --> F[validar_nif Mod-11<br/>Σ d*(9-i)%11]
    F --> G[requests.get<br/>?json=1&q=&key= timeout]
    G --> H{raise_for_status<br/>resp.json}
    H -- Timeout/RequestException --> E3[erro rede + exit 1]
    H -- JSONDecodeError --> E4[erro não JSON + exit 1]
    H -- ok --> I{result == success?}
    I -- não --> E5[erro result + exit 1]
    I -- sim --> J[records.get nif fallback]
    J --> K[return dict<br/>valido, fonte, dados, creditos]
    K --> L[print json.dumps stdout<br/>exit 0/1 conforme erro]
```

## 4. Classes de Domínio (classDiagram)

```mermaid
classDiagram
    class ConsultaResultado {
        +str nif
        +bool valido
        +str fonte
        +str erro
        +RegistoNif dados
        +bool nif_valido_formato
        +Creditos creditos
    }
    class RegistoNif {
        +int nif
        +str seo_url
        +str title
        +str alias
        +str status
        +date start_date
        +str activity
        +str address
        +str pc4
        +str pc3
        +str city
        +Place place
        +Geo geo
        +Contacts contacts
        +Structure structure
        +list cae
        +str racius
        +str portugalio
    }
    class Place {
        +str address
        +str pc4
        +str pc3
        +str city
    }
    class Geo {
        +str region
        +str county
        +str parish
    }
    class Contacts {
        +str email
        +str phone
        +str website
        +str fax
    }
    class Structure {
        +str nature
        +str capital
        +str capital_currency
    }
    class Creditos {
        +str used
        +dict left
    }
    ConsultaResultado --> RegistoNif
    RegistoNif --> Place
    RegistoNif --> Geo
    RegistoNif --> Contacts
    RegistoNif --> Structure
    ConsultaResultado --> Creditos
```

*Mapeado por `importar_nif.py:83` `mapear_registo()` → 36 colunas.*

## 5. ER (erDiagram)

```mermaid
erDiagram
    sqlite_nif_pt {
        INTEGER id PK
        INTEGER nif
        TEXT dados
        TEXT data_consulta
    }
    nif_pt {
        BIGINT nif PK
        BIT nif_valido_formato
        DATETIME2 data_consulta
        NVARCHAR seo_url
        NVARCHAR title
        NVARCHAR alias
        NVARCHAR status
        DATE start_date
        NVARCHAR activity
        NVARCHAR place_address
        NVARCHAR address
        NVARCHAR geo_region
        NVARCHAR contacts_email
        NVARCHAR structure_nature
        DECIMAL structure_capital
        NVARCHAR cae
        NVARCHAR racius
        NVARCHAR portugalio
        NVARCHAR creditos_used
        INT creditos_left_month
    }
    nif_pt_stg {
        BIGINT id PK
        BIGINT nif
        BIT nif_valido_formato
        DATETIME2 data_consulta
        NVARCHAR seo_url
        NVARCHAR title
        DATETIME2 data_staging
        BIT processado
    }
    nif_pt_stg ||--o{ nif_pt : "MERGE WHERE processado=0"
```

## 6. Estados do NIF (stateDiagram-v2)

```mermaid
stateDiagram-v2
    [*] --> InvalidoFormato: nif.isdigit==false
    [*] --> ValidoFormato: validar_nif
    InvalidoFormato --> [*]: exit 1 "NIF deve conter apenas dígitos"
    ValidoFormato --> SemChave: NIF-PT-KEY falta
    ValidoFormato --> ConsultarAPI: key existe
    SemChave --> [*]: exit 1 "NIF-PT-KEY não encontrada"
    ConsultarAPI --> Timeout: requests.Timeout
    ConsultarAPI --> ErroRede: RequestException
    ConsultarAPI --> NaoEncontrado: result != success
    ConsultarAPI --> Encontrado: result == success
    Timeout --> [*]: exit 1 "Timeout"
    ErroRede --> [*]: exit 1 "Erro de rede"
    NaoEncontrado --> [*]: exit 1 "No records found"
    Encontrado --> GuardadoSQLite: | importar_nif_sqlite.py
    Encontrado --> GuardadoAzure: | importar_nif.py
    GuardadoSQLite --> [*]: exit 0
    GuardadoAzure --> GuardadoSQLite: tee ambos
    GuardadoAzure --> [*]: exit 0
```

## 7. Contentores C4 (graph TB)

```mermaid
graph TB
    U[Utilizador<br/>CLI] --> SYS[nif-pt<br/>Python 3.11 CLI]
    subgraph SYS
        C[consulta_nif.py<br/>110L]
        S[importar_nif_sqlite.py<br/>88L]
        A[importar_nif.py<br/>213L]
        CFG[config.py 40L]
        LOG[logging_template.py 579L]
    end
    SYS --> API[(nif.pt<br/>externo)]
    SYS --> DB1[(SQLite<br/>local)]
    SYS --> DB2[(Azure SQL<br/>remoto)]
    CFG -. config .-> C & S & A
    LOG -. futuro .-> C & S & A
```

## 8. Componentes — `importar_nif.py` (graph LR)

```mermaid
graph LR
    subgraph importar_nif.py
        CS[connection_string<br/>ODBC 18]
        MP[mapear_registo<br/>36 cols]
        CT[colunas_tabela]
        PL[placeholders ?]
        VI[valores_para_insert]
        PD[parse_date/capital/int]
        CA[extrair_cae]
        MN[main stdin]
    end
    MN --> MP
    MP --> PD & CA
    MN --> CS & CT & PL & VI
    CT --> PL
    MP --> VI
```

*Todos os diagramas validados para `mermaid.live` (graph/sequenceDiagram/classDiagram/erDiagram/stateDiagram).*
