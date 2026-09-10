# Diagramas — nif-pt v1.2.0

> Fonte Mermaid única. Validar em https://mermaid.live. Referenciados em `MANUAL.md`, `architecture.md`, `technical.md`. Atualizado para cache + só SQLite.

## 1. Pipeline — cache + run_id (graph LR)

```mermaid
graph LR
    U[Utilizador<br/>NIF 9 dígitos] --> C[consulta_nif.py<br/>validar_nif + cache<br/>retry per-tipo+global<br/>run_id UUID v4]
    C -->|cache hit<br/>is_nif_recente==True| IG[(nif_ignorados<br/>6c cache_recente<br/>WAL)]
    C -->|stdout JSON ignorado<br/>ignorado:true motivo:cache_recente| S[importar_nif_sqlite.py<br/>early skip INSERT]
    C -->|stdout JSON run_id<br/>ensure_ascii=False<br/>cache miss| S2[importar_nif_sqlite.py<br/>JSON bruto WAL 5c run_id]
    C -->|erro classificado run_id| E[(nif_api_erros<br/>SQLite 15c run_id idx)]
    C -->|cache miss| API[(nif.pt<br/>GET ?json=1&q=&key=)]
    S2 --> DB[(data/nif_pt.db<br/>nif_pt 5c + nif_api_erros 15c<br/>+ nif_ignorados 6c<br/>PRAGMA WAL)]
    IG --> DB
    E --> DB
    CV[utils/cache_validator.py<br/>is_nif_recente + registar_ignorado<br/>DDL 6c 2 índices] -. cache .-> C
    CFG[config.yaml 31L + .env<br/>get_config merge cache_*] -.-> C & S2 & E & CV
    LOG[logging_orchestrator<br/>R1-R9 <<nif-pt>> [cache][run]] -.-> C & S2 & E & CV
    RID[utils/run_id.py<br/>generate_run_id + ContextVar<br/>--run-id > payload > ctx > uuid] -. run_id .-> C & S2 & E
```

## 2. Sequência — Consulta com cache + retry + run_id (sequenceDiagram)

```mermaid
sequenceDiagram
    participant U as Utilizador
    participant CLI as consulta_nif.py:main<br/>setup_logging + init_error_table<br/>+ init_cache_tables<br/>ensure_run_id
    participant CV as utils/cache_validator<br/>is_nif_recente + registar_ignorado<br/>nif_ignorados 6c WAL
    participant V as validar_nif<br/>Mod-11
    participant CFG as get_config<br/>config.yaml+.env<br/>cache_ativo/dias
    participant EH as utils/error_handler<br/>classificar_erro + tratar_erro<br/>guardar_erro(...,run_id)
    participant API as nif.pt<br/>?json=1&q=&key=<br/>timeout 10s
    participant DB as SQLite WAL<br/>nif_pt 5c + nif_ignorados 6c<br/>+ nif_api_erros 15c
    participant OUT as stdout<br/>JSON run_id + ignorado
    participant IMP as importar_nif_sqlite.py<br/>stdin JSON -> INSERT/skip

    U->>CLI: python consulta_nif.py 509442013 [--run-id UUID]
    CLI->>CFG: get_config("consulta_nif")
    CFG-->>CLI: api_base, timeout 10, NIF-PT-KEY ***XXXX, max_* 5/3/2/0/0, cache_ativo true dias 30
    CLI->>EH: init_error_table() DDL 15c run_id
    EH-->>CLI: nif_api_erros garantido WAL
    CLI->>CV: init_cache_tables() DDL nif_ignorados 6c WAL
    CV-->>CLI: nif_ignorados garantido
    CLI->>V: validar_nif(Mod-11)
    V-->>CLI: true/false (só loga)
    CLI->>CV: is_nif_recente(nif, dias=30) -> SELECT data_consulta FROM nif_pt WHERE nif=? ORDER BY datetime DESC LIMIT 1
    CV-->>CLI: (recente:bool, data_ultima:str|None) + [cache] recente=True/False (0.02s)
    alt recente == True
        CLI->>CV: registar_ignorado(nif, data_ultima, "cache_recente") -> INSERT nif_ignorados
        CV->>DB: INSERT nif_ignorados (nif, data_ultima_consulta, dias_desde_ultima, motivo)
        CV-->>CLI: id ignorado
        CLI-->>OUT: {"nif":..., "ignorado":true, "motivo":"cache_recente", "data_ultima_consulta":..., "cache_antiguidade_dias":30, "run_id":...} exit 0
        OUT->>IMP: stdin JSON ignorado
        IMP->>IMP: if ignorado -> INFO [cache] skip INSERT + BOX skip + exit 0
    else recente == False
        loop tentativa_global 0..5
            CLI->>API: GET ?json=1&q=509442013&key=*** timeout 10s
            alt Timeout / RequestException
                API-->>CLI: Timeout
                CLI->>CLI: sleep 60s retry se <max_global
            else 200 JSON
                API-->>CLI: {result, message, records, credits}
                alt result != success
                    CLI->>EH: tratar_erro(nif, data, tentativa_global, tentativas_por_tipo, run_id)
                    EH->>EH: classificar_erro -> rate_limit_minute/hour/day/month/paid
                    EH->>DB: guardar_erro(15c, acao retry_60s/abort_day, run_id)
                    EH-->>CLI: {tipo, acao, espera, deve_retry, max_tipo, max_global}
                    alt retry && deve_retry
                        CLI->>CLI: sleep 60s/3600s continue
                    else abort/none
                        CLI-->>OUT: {erro, tipo_erro, dados, run_id} exit 1
                    end
                else success
                    CLI->>CLI: records[nif] fallback first_key
                    CLI-->>OUT: stdout {nif,valido,erro:null,dados,creditos,run_id}
                    OUT->>IMP: stdin JSON run_id
                    IMP->>DB: INSERT nif_pt (nif,dados,data_consulta,run_id) WAL 5c
                    IMP-->>U: stderr BOX Guardado em SQLite run_id=... exit 0
                end
            end
        end
    end
```

## 3. Atividades — Validação + cache + request com error_handler (graph TD)

```mermaid
graph TD
    A[argv NIF --run-id] --> R0[ensure_run_id cli_value<br/>extract_cli_run_id + remove_run_id_args]
    R0 --> B{nif.isdigit?}
    B -- não --> E1[erro + run_id + exit 1]
    B -- sim --> C[get_config<br/>api_base, timeout 10, cache_ativo/dias, max_*]
    C --> D{API_KEY existe?}
    D -- não --> E2[erro NIF-PT-KEY + run_id + exit 1]
    D -- sim --> F[init_error_table WAL 15c<br/>+ init_cache_tables WAL 6c]
    F --> G[validar_nif Mod-11<br/>Σ d*(9-i)%11]
    G --> CC{cache_ativo?}
    CC -- não --> H[Loop tentativa_global 0..5]
    CC -- sim --> CH[is_nif_recente nif dias<br/>SELECT nif_pt ORDER BY datetime DESC LIMIT 1<br/>parse YYYY-MM-DD HH:MMSS / ISO]
    CH --> CR{recente?}
    CR -- sim recente=True --> CI[registar_ignorado<br/>INSERT nif_ignorados<br/>dias_desde_ultima + motivo cache_recente]
    CI --> CO[stdout JSON ignorado:true<br/>motivo cache_recente<br/>data_ultima_consulta + cache_antiguidade_dias<br/>+ run_id + BOX cache + exit 0]
    CR -- não recente=False --> H
    CH -- erro BD fail-open --> H
    H --> I[requests.get<br/>?json=1&q=&key= timeout 10s]
    I --> J{raise_for_status<br/>resp.json}
    J -- Timeout/RequestException --> K[retry rede 60s<br/>se <max_global]
    K --> H
    J -- JSONDecodeError --> E4[erro não JSON + run_id + exit 1]
    J -- ok --> L{result == success?}
    L -- não --> M[classificar_erro<br/>guardar_erro WAL run_id]
    M --> N{tipo + limite?}
    N -- minute tenta<3 && global<5 --> O1[sleep 60s retry]
    N -- hour tenta<2 && global<5 --> O2[sleep 3600s retry]
    N -- day/month/paid ou esgotou --> E5[abort tipo_erro + run_id + exit 1]
    O1 --> H
    O2 --> H
    L -- sim --> P[records[nif] fallback]
    P --> Q[stdout JSON<br/>valido true + run_id + BOX]
    Q --> R[Pipe -> importar_nif_sqlite.py<br/>if ignorado: skip INSERT [cache]<br/>else INSERT WAL 5c run_id]
    R --> Z[*]
    CO --> S[Pipe -> importar_nif_sqlite.py<br/>is ignorado -> skip INSERT<br/>BOX NIF ignorado - skip]
    S --> Z
    E1 --> Z
    E2 --> Z
    E4 --> Z
    E5 --> Z
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
        +str run_id
        +bool ignorado
        +str motivo
        +str data_ultima_consulta
        +int cache_antiguidade_dias
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
        +str run_id
        +int resolvido
    }
    class NifIgnorado {
        +int id PK
        +int nif
        +str data_tentativa
        +str data_ultima_consulta
        +int dias_desde_ultima
        +str motivo
        +is_nif_recente() bool
        +registar_ignorado() int
        +init_cache_tables()
    }
    class RunId {
        +str run_id UUID v4
        +generate_run_id() str
        +ensure_run_id(cli, payload) str
        +extract_cli_run_id(argv) str|None
        +remove_run_id_args(argv) list
        +ContextVar _run_id_ctx
    }
    class Config {
        +str api_base
        +int timeout
        +int tempo_de_espera
        +int tempo_espera_minuto
        +int tempo_espera_hora
        +int max_tentativas_global
        +bool cache_ativo
        +int cache_antiguidade_dias
        +str cache_tabela_ignorados
        +str NIF_PT_KEY
    }
    ConsultaResultado --> RegistoNif
    RegistoNif --> Creditos
    ConsultaResultado ..> NifApiErro : erro -> guardar_erro(...,run_id)
    ConsultaResultado ..> NifIgnorado : cache hit -> registar_ignorado
    NifIgnorado ..> ConsultaResultado : is_nif_recente
    Config ..> ConsultaResultado : get_config + cache_*
    RunId ..> ConsultaResultado : ensure_run_id CLI>payload>ctx>gen
    RunId ..> NifApiErro : guardar_erro run_id
```

*Cache: `is_nif_recente()` lê `nif_pt`; `registar_ignorado()` escreve `nif_ignorados` 6c; ` consulta_nif.main` decide `ignorado:true` antes de API.*

## 5. ER (erDiagram) v1.2.0

```mermaid
erDiagram
    nif_pt {
        INTEGER id PK
        INTEGER nif
        TEXT dados
        TEXT data_consulta
        TEXT run_id
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
        TEXT run_id
        INTEGER resolvido
    }
    nif_ignorados {
        INTEGER id PK
        INTEGER nif
        TEXT data_tentativa
        TEXT data_ultima_consulta
        INTEGER dias_desde_ultima
        TEXT motivo
    }
    nif_pt ||--o{ nif_ignorados : "is_nif_recente"
    nif_pt ||--o{ nif_api_erros : "mesma DB WAL run_id"
```

## 6. Estados do NIF (stateDiagram-v2) — com cache

```mermaid
stateDiagram-v2
    [*] --> InvalidoFormato: nif.isdigit==false
    [*] --> ValidoFormato: validar_nif
    InvalidoFormato --> [*]: exit 1 "NIF deve conter apenas dígitos"
    ValidoFormato --> SemChave: NIF-PT-KEY falta
    ValidoFormato --> CacheCheck: key existe + init tables
    SemChave --> [*]: exit 1 "NIF-PT-KEY não encontrada"
    CacheCheck --> IgnoradoCache: is_nif_recente==True<br/>registar_ignorado + JSON ignorado:true<br/>exit 0 sem API
    CacheCheck --> ConsultarAPI: is_nif_recente==False<br/>ou cache_ativo==false
    IgnoradoCache --> SkipSQLite: | importar_nif_sqlite<br/>ignorado==true -> skip INSERT
    SkipSQLite --> [*]: exit 0 BOX skip
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
    Encontrado --> GuardadoSQLite: | importar_nif_sqlite<br/>INSERT 5c run_id
    GuardadoSQLite --> [*]: exit 0 BOX sucesso
```

## 7. Contentores C4 (graph TB)

```mermaid
graph TB
    U[Utilizador CLI] --> SYS[nif-pt v1.2.0<br/>Python 3.11 + cache]
    subgraph SYS
        C[consulta_nif.py 626L]
        CV[cache_validator.py 407L]
        E[error_handler.py 806L]
        S[importar_nif_sqlite.py 285L]
        R[utils/run_id.py 191L]
        CFG[config.py 134L]
        LOG[logging_orchestrator.py 580L]
    end
    SYS --> API[(nif.pt<br/>se cache miss)]
    SYS --> DB[(SQLite WAL<br/>3 tabelas)]
    CFG -.-> C & S & E & CV
    LOG -.-> C & S & E & CV
    CV -.-> DB
```

## 8. Componentes — `importar_nif_sqlite.py` + `cache_validator` (graph LR)

```mermaid
graph LR
    subgraph importar_nif_sqlite.py 285L
        GD[get_db WAL 5c run_id]
        MS[main stdin run_id<br/>early skip ignorado]
    end
    subgraph cache_validator.py 407L
        IR[is_nif_recente<br/>SELECT nif_pt]
        RG[registar_ignorado<br/>INSERT nif_ignorados]
        IT[init_cache_tables<br/>DDL 6c WAL]
        PC[_parse_data_consulta]
    end
    MS --> IR
    IR --> PC
    MS --> RG
    MS --> GD
    MS -->|ignorado==true| SKIP[skip INSERT BOX [cache]]
    IT --> GD
```

*Todos os diagramas validados em `mermaid.live` (graph/sequence/class/er/state). Ver `docs/technical.md` para catálogo file:line.*
