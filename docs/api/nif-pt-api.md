# API nif.pt — Contrato v1.2.0

> Fonte: `consulta_nif.py:99` `validar_nif` + `consulta_nif.py:272` `requests.get(url, params={"json":1,"q":nif,"key":API_KEY}, timeout=10)` + `utils/error_handler.py:196` `classificar_erro` + `utils/cache_validator.py:225` `is_nif_recente` + resposta real `509442013` (2026-09-10).

## 1. Endpoint

```
GET http://www.nif.pt/?json=1&q=<NIF>&key=<NIF-PT-KEY>
```

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `json` | `int` | ✅ | Sempre `1` — força JSON |
| `q` | `string` | ✅ | NIF 9 dígitos (ex: `509442013`) |
| `key` | `string` | ✅ | Chave http://www.nif.pt/contactos/api/ (`config/.env` `NIF-PT-KEY` com hífen) |

* `API_BASE` de `config/config.yaml:24` `consulta_nif.api_base` (`http://www.nif.pt`) + `"/"` (`consulta_nif.py:259`).
* `TIMEOUT 10s` de `config/config.yaml:3` → `requests.get(timeout=10)` + loop `max_global+1` com `tempo_de_espera 60s` (`consulta_nif.py:79`).
* `NIF-PT-KEY` mascarada `***XXXX` no log (`consulta_nif.py:261`).
* **Cache antes de API:** `consulta_nif.py:529` `is_nif_recente(nif, dias=30)` verifica `nif_pt` SQLite; se `recente==True` → sem `GET`, devolve JSON `ignorado` e regista `nif_ignorados` (`utils/cache_validator.py:329`).

## 2. Resposta — Sucesso

### 2.1 Envelope `nif.pt`

```json
{
  "result": "success",
  "nif_validation": true,
  "credits": {
    "used": "free",
    "left": []           // ou {"month":999,"day":99,"hour":9,"minute":0,"paid":0} se pago
  },
  "records": {
    "509442013": {
      "nif": 509442013,
      "seo_url": "nexperience-lda",
      "title": "Nexperience, Unipessoal, Lda",
      "alias": "Nexperience",
      "status": "active",
      "start_date": "2010-05-18",
      "activity": "<p>Desenvolvimento de software...</p>",
      "address": "Rua de Santa Catarina, Nº 1232",
      "pc4": "4000", "pc3": "457", "city": "Porto",
      "place": { "address": "Rua ...", "pc4": "4000", "pc3": "457", "city": "Porto" },
      "geo": { "region": "Porto", "county": "Porto", "parish": "Cedofeita" },
      "contacts": { "email": "info@nex.pt", "phone": "220 198 228", "website": "www.nex.pt", "fax": "224 905 459" },
      "structure": { "nature": "UNI", "capital": "248000.00", "capital_currency": "EUR" },
      "cae": ["62010", "63120", "62020", "46510"],
      "racius": "https://www.racius.com/nexperience-lda/",
      "portugalio": null
    }
  }
}
```

### 2.2 Normalização `consulta_nif.py:406` + `run_id`

```python
records = data.get("records", {})
registo = records.get(nif, records.get(list(records.keys())[0] if records else None))
```

* Fallback para primeira chave se `nif` não bater (API pode devolver sem zeros à esquerda).
* `consulta_nif.py:423` retorna (com `run_id`):

```json
{
  "nif": "509442013",
  "valido": true,                    // validar_nif(nif) ou True se success
  "fonte": "nif.pt",
  "erro": null,
  "dados": { /* registo acima */ },
  "nif_valido_formato": true,        // data.get("nif_validation")
  "creditos": { "used": "free", "left": [] },
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

`help(consulta_nif.consultar_nif)` para docstring completa.

## 3. Resposta — Cache hit (novo v1.2.0)

Quando `utils/cache_validator.py:225` `is_nif_recente(nif, dias=30)==True`, `consulta_nif.py:547` **não faz `GET`** e devolve:

```json
{
  "nif": "509442013",
  "valido": true,
  "fonte": null,
  "erro": null,
  "dados": null,
  "nif_valido_formato": null,
  "creditos": null,
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "ignorado": true,
  "motivo": "cache_recente",
  "data_ultima_consulta": "2026-09-10 12:00:00",
  "cache_antiguidade_dias": 30
}
```

* `ignorado: true` + `motivo: "cache_recente"` distingue de erro; `importar_nif_sqlite.py:194` faz early skip (sem `INSERT`).
* Persistido em `nif_ignorados` 6c (`utils/cache_validator.py:329` `registar_ignorado`) com `dias_desde_ultima`.
* Config via `config/config.yaml:15` `cache_ativo`, `cache_antiguidade_dias`, `cache_tabela_ignorados`; `cache_ativo: false` ou `cache_antiguidade_dias: 0` desliga.
* Log `stderr` `INFO [cache] NIF ... ignorado` + `BOX NIF ignorado - cache recente`.

## 4. Resposta — Erro (classificada v1.0.0 + run_id)

### 4.1 `result != "success"` — delega a `utils/error_handler` (`consulta_nif.py:312`)

```json
{
  "result": "error",
  "message": "Limit per minute exceeded",
  "nif_validation": false,
  "credits": { "used": "free", "left": { "minute": 0, "hour": 9, "day": 99, "month": 999, "paid": 0 } },
  "records": {}
}
```

→ `classificar_erro()` (`utils/error_handler.py:196`) → `rate_limit_minute` (prioridade `Limit per minute` na `message_lower`; fallback `left.minute==0`).

→ `tratar_erro()` (`:515`) → `{tipo:"rate_limit_minute", acao:"retry", espera:60, deve_retry: tenta<3 && global<5, max_tipo:3, max_global:5}` + `guardar_erro(...,run_id)` → `nif_api_erros` 15c.

→ `consulta_nif.py:356` `retry` `sleep 60s` se `deve_retry` e `<max_global`, senão `abort` + JSON com `tipo_erro` + `run_id`.

**Tabela de classificação:**

| `message` contém | `credits.left` | Tipo `classificar_erro` | Ação `tratar_erro` | Espera | `max_*` |
|---|---|---|---|---|---|
| `Limit per minute` | `minute==0` | `rate_limit_minute` | `retry` | 60s | 3 |
| `Limit per hour` | `hour==0` | `rate_limit_hour` | `retry` | 3600s | 2 |
| `Limit per day` | `day==0` | `rate_limit_day` | `abort` + BOX fatal | 0 | 0 |
| `Limit per month` | `month==0` | `rate_limit_month` | `abort` + BOX fatal | 0 | 0 |
| `Limit per ... paid` | `paid==0` | `rate_limit_paid` | `abort` | 0 | 0 |
| outro `result != success` | — | `generic_error` | `none` auditoria | 0 | 0 |
| — | — | `unknown` | `none` | 0 | 0 |

Ver `docs/technical.md §10` para lógica `&&` (per-tipo e global).

### 4.2 `No records found` (genérico)

```json
{
  "result": "No records found",
  "nif_validation": false,
  "credits": { "used": "free", "left": [] },
  "records": {}
}
```

→ `generic_error`, `acao=none`, persistido mas sem retry; `consulta_nif.py:379` retorna `erro: result`, `tipo_erro: generic_error`, `run_id`.

### 4.3 Erros de rede (`consulta_nif.py:284`)

| Exceção | `erro` | `valido` | Retry |
|---------|--------|----------|-------|
| `Timeout` | `Timeout na consulta à API nif.pt` | `validar_nif(nif)` | `sleep 60s` se `<max_global` |
| `RequestException` | `Erro de rede: ...` | `validar_nif(nif)` | idem |
| `JSONDecodeError` | `Resposta inválida (não JSON)` | `validar_nif(nif)` | — (fatal) |

Todos com `run_id`.

### 4.4 Sem chave (`consulta_nif.py:248`)

```json
{
  "nif": "509442013",
  "valido": true,
  "fonte": null,
  "erro": "NIF-PT-KEY não encontrada no .env",
  "dados": null,
  "run_id": "550e8400-..."
}
```
Sem request (e sem cache); `exit 1`.

## 5. Validação

`consulta_nif.py:99` `validar_nif()` — `Σ d*(9-i)%11 → 0 se resto 0/1 senão 11-resto` == `d[8]`.

* `main():513` valida `isdigit` antes de rede/cache → `{"erro":"NIF deve conter apenas dígitos","run_id":...}`.
* Mod-11 só afeta `valido`; **não bloqueia** `requests.get` (log `WARN`).

`help(consulta_nif.validar_nif)` para exemplos `509442013 True` / `123456789 False`.

## 6. Créditos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `credits.used` | `string` | `"free"` ou `"paid"` |
| `credits.left` | `dict` ou `[]` | `paid`: `{"month":int,"day":int,"hour":int,"minute":int,"paid":int}`; `free`: `[]` lista vazia (real 2026-09-10) |

Sem Azure, `creditos.left` só é persistido no JSON bruto `nif_pt.dados` (não há 37c normalizadas).

## 7. Timeouts, Retry e Cache (v1.2.0)

* `TIMEOUT 10s` (`config/config.yaml:3`) → `requests.get(timeout=10)`.
* `retry_count 1` legado fallback; ativo são `max_tentativas_global 5 / minuto 3 / hora 2 / dia 0 / mes 0` + `tempo_espera_minuto 60s / hora 3600s` via `utils/error_handler` (`consulta_nif.py:79`, `utils/error_handler.py:272`).
* Lógica conjunta: `tenta_tipo < max_tipo && tenta_global < max_global` → só retry se ambos permitirem.
* **Cache:** `cache_ativo true` + `cache_antiguidade_dias 30` → `is_nif_recente()` evita `GET` para NIFs com `nif_pt.data_consulta` dentro da janela; `nif_ignorados` audita; `importar_nif_sqlite.py:194` não insere `ignorado`.

## 8. Exemplo `curl` / PowerShell / Python

```bash
curl "http://www.nif.pt/?json=1&q=509442013&key=SUA_CHAVE"
# Python:
python consulta_nif.py 509442013 | python -m json.tool
# PowerShell:
python consulta_nif.py 509442013 | ConvertFrom-Json | Format-List
# Cache hit (2ª vez em <30d):
python consulta_nif.py 509442013
# -> {"ignorado": true, "motivo": "cache_recente", "data_ultima_consulta": "...", "run_id": "..."}
```

## 9. Referências

* `consulta_nif.py:99` `validar_nif` · `consulta_nif.py:171` `consultar_nif` · `consulta_nif.py:529` cache `is_nif_recente` · `utils/cache_validator.py:225` `is_nif_recente` · `utils/error_handler.py:196` `classificar_erro()`
* `docs/technical.md` §3 sequência cache · `docs/api/help.md` `help(is_nif_recente)` + `help(tratar_erro)`
* http://www.nif.pt/contactos/api/
