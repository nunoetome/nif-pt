# Diagramas — nif-pt v1.0.0

> Fonte Mermaid única. Validar em https://mermaid.live. Referenciados em `MANUAL.md`, `architecture.md`, `technical.md`.

## 1. Pipeline (graph LR)

```mermaid
graph LR
    U[Utilizador<br/>NIF 9 dígitos] --> C[consulta_nif.py<br/>validar_nif + requests<br/>retry per-tipo+global]
    C -->|stdout JSON<br/>ensure_ascii=False| S[importar_nif_sqlite.py<br/>JSON bruto WAL]
    C -->|stdout JSON| A[importar_nif.py<br/>36 cols pyodbc]
    C -->|erro classificado| E[(nif_api_erros<br/>SQLite + Azure 14c)]
    S --> DB1[(data/nif_pt.db<br/>nif_pt 4c + nif_api_erros 14c<br/>PRAGMA WAL)]
    A --> DB2[(Azure SQL<br/>stg_nunotome.nif_pt_stg 40c)]
    DB2 -. MERGE futuro .-> DB3[(stg_nunotome.nif_pt 37c PK nif)]
    CFG[config.yaml 37L + .env<br/>get_config merge] -.-> C & S & A & E
    LOG[logging_orchestrator<br/>R1-R9 <<nif-pt>>] -.-> C & S & A & E
```

## 2. Sequência — Consulta com retry e camada de erro (sequenceDiagram)

```mermaid
sequenceDiagram
    participant U as Utilizador
    participant CLI as consulta_nif.py:main
    participant V as validar_nif
    participant CFG as get_config
    participant EH as utils/error_handler
    participant API as nif.pt<br/>?json=1&q=&key=<br/>timeout 10s
    participant DB as nif_api_erros<br/>WAL

    U->>CLI: python consulta_nif.py 509442013
    CLI->>CLI: isdigit? --não--> {"erro":"NIF deve conter apenas dígitos"} exit 1
    CLI->>CFG: get_config("consulta_nif")
    CFG-->>CLI: api_base, timeout 10, NIF-PT-KEY ***XXXX, max_* 5/3/2/0/0, espera 60/3600
    CLI->>EH: init_error_table() DDL WAL
    EH-->>CLI: tabela garantida
    CLI->>V: validar_nif(Mod-11)
    V-->>CLI: true/false (só loga)
    loop tentativa_global 0..5
        CLI->>API: GET ?json=1&q=509442013&key=*** timeout 10s
        alt Timeout / RequestException
            API-->>CLI: Timeout
            CLI->>CLI: sleep 60s retry se <max_global
        else 200 JSON
            API-->>CLI: {result, message, records, credits}
            alt result != success
                CLI->>EH: tratar_erro(nif, data, tentativa_global, tentativas_por_tipo)
                EH->>EH: classificar_erro -> rate_limit_minute/hour/day/month/paid
                EH->>DB: guardar_erro(14c, acao retry_60s/abort_day)
                EH-->>CLI: {tipo, acao, espera, deve_retry, max_tipo, max_global}
                alt retry && deve_retry
                    CLI->>CLI: sleep 60s/3600s continue
                else abort/none
                    CLI-->>U: {erro, tipo_erro, dados} exit 1
                end
            else success
                CLI->>CLI: records[nif] fallback first_key
                CLI-->>U: stdout {nif,valido,erro:null,dados,creditos}
            end
        end
    end
```

## 3. Atividades — Validação e request com error_handler (graph TD)

```mermaid
graph TD
    A[argv NIF] --> B{nif.isdigit?}
    B -- não --> E1[erro + exit 1]
    B -- sim --> C[get_config<br/>api_base, timeout 10, max_*]
    C --> D{API_KEY existe?}
    D -- não --> E2[erro NIF-PT-KEY + exit 1]
    D -- sim --> F[init_error_table<br/>WAL]
    F --> G[validar_nif Mod-11<br/>Σ d*(9-i)%11]
    G --> H[Loop tentativa_global 0..5<br/>tentativas_por_tipo dict]
    H --> I[requests.get<br/>?json=1&q=&key= timeout 10s]
    I --> J{raise_for_status<br/>resp.json}
    J -- Timeout/RequestException --> K[retry rede 60s<br/>se <max_global]
    K --> H
    J -- JSONDecodeError --> E4[erro não JSON + exit 1]
    J -- ok --> L{result == success?}
    L -- não --> M[classificar_erro<br/>guardar_erro WAL]
    M --> N{tipo + limite?}
    N -- minute tenta<3 && global<5 --> O1[sleep 60s retry]
    N -- hour tenta<2 && global<5 --> O2[sleep 3600s retry]
    N -- day/month/paid ou esgotou --> E5[abort tipo_erro + exit 1]
    O1 --> H
    O2 --> H
    L -- sim --> P[records[nif] fallback]
    P --> Q[stdout JSON<br/>valido true + BOX]
    Q --> R[Pipe -> importar_*.py<br/>INSERT WAL/Azure]
    R --> Z[*]
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
        +str tipo_erro
    }
    class RegistoNif {
        +int nif
        +str seo_url
        +str title
        +str alias
        +str status
        +date start_date
        +str activity
        +Place place
        +Geo geo
        +Contacts contacts
        +Structure structure
        +list cae
        +str racius
        +str portugalio
    }
    class Place { +str address; +str pc4; +str pc3; +str city }
    class Geo { +str region; +str county; +str parish }
    class Contacts { +str email; +str phone; +str website; +str fax }
    class Structure { +str nature; +str capital; +str capital_currency }
    class Creditos { +str used; +dict|list left }
    class NifApiErro {
        +int id PK
        +int nif
        +str data_erro
        +str tipo_erro
        +str codigo_erro
        +str mensagem
        +int left_*
        +str dados_json
        +str acao
        +int resolvido
    }
    ConsultaResultado --> RegistoNif
    RegistoNif --> Place & Geo & Contacts & Structure
    ConsultaResultado --> Creditos
    ConsultaResultado ..> NifApiErro : guardar_erro
```

*Mapeado por `importar_nif.py:103` `mapear_registo()` → 36c; `NifApiErro` via `guardar_erro()` 14c.*

## 5. ER (erDiagram) v1.0.0

```mermaid
erDiagram
    sqlite_nif_pt {
        INTEGER id PK
        INTEGER nif
        TEXT dados
        TEXT data_consulta
    }
    nif_api_erros {
        INTEGER id PK
        INTEGER nif
        TEXT data_erro
        TEXT tipo_erro
        TEXT codigo_erro
        TEXT mensagem
        INTEGER left_month
        INTEGER left_day
        INTEGER left_hour
        INTEGER left_minute
        INTEGER left_paid
        TEXT dados_json
        TEXT acao
        INTEGER resolvido
    }
    nif_pt {
        BIGINT nif PK
        BIT nif_valido_formato
        DATETIME2 data_consulta
        NVARCHAR title
        NVARCHAR cae
        INT creditos_left_minute
    }
    nif_pt_stg {
        BIGINT id PK
        BIGINT nif
        DATETIME2 data_staging
        BIT processado
        NVARCHAR title
    }
    nif_pt_stg ||--o{ nif_pt : "MERGE WHERE processado=0"
    sqlite_nif_pt ||--o{ nif_pt_stg : "mesmo NIF"
    sqlite_nif_pt ||--o{ nif_api_erros : "mesma DB WAL"
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
    ConsultarAPI --> Timeout: Timeout
    ConsultarAPI --> ErroRede: RequestException
    ConsultarAPI --> RateLimit: Limit per minute/hour
    ConsultarAPI --> QuotaFatal: Limit per day/month
    ConsultarAPI --> NaoEncontrado: result != success
    ConsultarAPI --> Encontrado: result == success
    Timeout --> ConsultarAPI: retry 60s se <global
    RateLimit --> ConsultarAPI: retry 60s/3600s se <tipo && <global
    QuotaFatal --> [*]: abort + nif_api_erros
    NaoEncontrado --> [*]: generic_error + guarda
    Encontrado --> GuardadoSQLite: | importar_nif_sqlite
    Encontrado --> GuardadoAzure: | importar_nif
    GuardadoSQLite --> [*]: exit 0
    GuardadoAzure --> [*]: exit 0
```

## 7. Contentores C4 (graph TB)

```mermaid
graph TB
    U[Utilizador CLI] --> SYS[nif-pt v1.0.0<br/>Python 3.11]
    subgraph SYS
        C[consulta_nif.py 355L]
        E[error_handler.py 612L]
        S[importar_nif_sqlite.py 152L]
        A[importar_nif.py 321L]
        CFG[config.py 70L]
        LOG[logging_orchestrator.py 580L]
    end
    SYS --> API[(nif.pt)]
    SYS --> DB1[(SQLite WAL)]
    SYS --> DB2[(Azure SQL)]
    CFG -.-> C & S & A & E
    LOG -.-> C & S & A & E
```

## 8. Componentes — `importar_nif.py` (graph LR)

```mermaid
graph LR
    subgraph importar_nif.py
        CS[connection_string ODBC 18]
        MR[mapear_registo 36c]
        CT[colunas_tabela]
        PL[placeholders ?]
        VI[valores_para_insert]
        PD[parse_date/capital/int + extrair_cae]
        MN[main stdin]
    end
    MN --> MR & CS & CT & PL & VI
    MR --> PD
    CT --> PL
    MR --> VI
```

*Todos os diagramas validados em `mermaid.live` (graph/sequence/class/er/state). Ver `docs/technical.md` para catálogo file:line.*
