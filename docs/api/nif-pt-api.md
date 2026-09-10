# API nif.pt — Contrato v1.0.0

> Fonte: `consulta_nif.py:98` `requests.get(url, params={"json":1,"q":nif,"key":API_KEY}, timeout=10)` + `utils/error_handler.py:139` `classificar_erro` + resposta real `509442013` (2026-09-10).

## 1. Endpoint

```
GET http://www.nif.pt/?json=1&q=<NIF>&key=<NIF-PT-KEY>
```

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `json` | `int` | ✅ | Sempre `1` — força JSON |
| `q` | `string` | ✅ | NIF 9 dígitos (ex: `509442013`) |
| `key` | `string` | ✅ | Chave http://www.nif.pt/contactos/api/ (`config/.env` `NIF-PT-KEY` com hífen) |

* `API_BASE` de `config.yaml:21` `consulta_nif.api_base` (`http://www.nif.pt`) + `"/"` (`consulta_nif.py:98`).
* `TIMEOUT 10s` de `config.yaml:3` → `requests.get(timeout=10)` + loop `max_global+1` com `tempo_de_espera 60s` (`consulta_nif.py:28`).
* `NIF-PT-KEY` mascarada `***XXXX` no log (`consulta_nif.py:100`).

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

### 2.2 Normalização `consulta_nif.py:240`

```python
records = data.get("records", {})
registo = records.get(nif, records.get(list(records.keys())[0] if records else None))
```

* Fallback para primeira chave se `nif` não bater (API pode devolver sem zeros à esquerda).
* `consulta_nif.py:257` retorna:

```json
{
  "nif": "509442013",
  "valido": true,                    // validar_nif(nif) ou True se success
  "fonte": "nif.pt",
  "erro": null,
  "dados": { /* registo acima */ },
  "nif_valido_formato": true,        // data.get("nif_validation")
  "creditos": { "used": "free", "left": [] }
}
```

`help(consulta_nif.consultar_nif)` para docstring completa.

## 3. Resposta — Erro (classificada v1.0.0)

### 3.1 `result != "success"` — delega a `utils/error_handler` (`consulta_nif.py:150`)

```json
{
  "result": "error",
  "message": "Limit per minute exceeded",
  "nif_validation": false,
  "credits": { "used": "free", "left": { "minute": 0, "hour": 9, "day": 99, "month": 999, "paid": 0 } },
  "records": {}
}
```

→ `classificar_erro()` (`utils/error_handler.py:139`) → `rate_limit_minute` (prioridade `Limit per minute` na `message_lower`; fallback `left.minute==0`).

→ `tratar_erro()` (`:346`) → `{tipo:"rate_limit_minute", acao:"retry", espera:60, deve_retry: tenta<3 && global<5, max_tipo:3, max_global:5}` + `guardar_erro()` → `nif_api_erros` 14c.

→ `consulta_nif.py:192` `retry` `sleep 60s` se `deve_retry` e `<max_global`, senão `abort`.

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

### 3.2 `No records found` (genérico)

```json
{
  "result": "No records found",
  "nif_validation": false,
  "credits": { "used": "free", "left": [] },
  "records": {}
}
```

→ `generic_error`, `acao=none`, persistido mas sem retry; `consulta_nif.py:216` retorna `erro: result`, `tipo_erro: generic_error`.

### 3.3 Erros de rede (`consulta_nif.py:123`)

| Exceção | `erro` | `valido` | Retry |
|---------|--------|----------|-------|
| `Timeout` | `Timeout na consulta à API nif.pt` | `validar_nif(nif)` | `sleep 60s` se `<max_global` |
| `RequestException` | `Erro de rede: ...` | `validar_nif(nif)` | idem |
| `JSONDecodeError` | `Resposta inválida (não JSON)` | `validar_nif(nif)` | — (fatal) |

### 3.4 Sem chave (`consulta_nif.py:88`)

```json
{
  "nif": "509442013",
  "valido": true,
  "fonte": null,
  "erro": "NIF-PT-KEY não encontrada no .env",
  "dados": null
}
```
Sem request; `exit 1`.

## 4. Validação

`consulta_nif.py:48` `validar_nif()` — `Σ d*(9-i)%11 → 0 se resto 0/1 senão 11-resto` == `d[8]`.

* `main():303` valida `isdigit` antes de rede → `{"erro":"NIF deve conter apenas dígitos"}`.
* Mod-11 só afeta `valido`; **não bloqueia** `requests.get` (log `WARN`).

`help(consulta_nif.validar_nif)` para exemplos `509442013 True` / `123456789 False`.

## 5. Créditos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `credits.used` | `string` | `"free"` ou `"paid"` |
| `credits.left` | `dict` ou `[]` | `paid`: `{"month":int,"day":int,"hour":int,"minute":int,"paid":int}`; `free`: `[]` lista vazia (real 2026-09-10) |

`importar_nif.py:116` `creditos.get("left") or {}` → `{}` se `[]` → `parse_int(None)` → `NULL` (não crasha) + `map` logado.

## 6. Timeouts e Retry (v1.0.0)

* `TIMEOUT 10s` (`config.yaml:3`) → `requests.get(timeout=10)` — 10s, não 1000.
* `retry_count 1` legado fallback; ativo são `max_tentativas_global 5 / minuto 3 / hora 2 / dia 0 / mes 0` + `tempo_espera_minuto 60s / hora 3600s` via `utils/error_handler` (`consulta_nif.py:35`, `utils/error_handler.py:215`).
* Lógica conjunta: `tenta_tipo < max_tipo && tenta_global < max_global` → só retry se ambos permitirem.

## 7. Exemplo `curl` / PowerShell / Python

```bash
curl "http://www.nif.pt/?json=1&q=509442013&key=SUA_CHAVE"
# Python:
python consulta_nif.py 509442013 | python -m json.tool
# PowerShell:
python consulta_nif.py 509442013 | ConvertFrom-Json | Format-List
```

## 8. Mapeamento para SQL

`importar_nif.py:103` `mapear_registo()` 36c + `docs/database/schema.md` §4. `help(importar_nif.mapear_registo)` para docstring.

## 9. Referências

* `consulta_nif.py:98` `url + params` · `consulta_nif.py:150` `tratar_erro()` · `utils/error_handler.py:139` `classificar_erro()`
* `docs/technical.md` §3 sequência · `docs/api/help.md` `help(tratar_erro)`
* http://www.nif.pt/contactos/api/
