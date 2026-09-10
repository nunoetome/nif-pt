# API nif.pt — Contrato

> Fonte: `consulta_nif.py:48` `requests.get(url, params={"json":1,"q":nif,"key":API_KEY}, timeout=TIMEOUT)` + `MANUAL.md:85` exemplo + análise de resposta real 2026-09-10.

## 1. Endpoint

```
GET http://www.nif.pt/?json=1&q=<NIF>&key=<NIF-PT-KEY>
```

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `json` | `int` | ✅ | Sempre `1` — força resposta JSON |
| `q` | `string` | ✅ | NIF com 9 dígitos (ex: `509442013`) |
| `key` | `string` | ✅ | Chave obtida em http://www.nif.pt/contactos/api/ (`config/.env` `NIF-PT-KEY`) |

* `API_BASE` vem de `config/config.yaml:10` `consulta_nif.api_base` (`http://www.nif.pt`) + `"/"` (`consulta_nif.py:48`).
* `TIMEOUT` de `config.yaml:3` `timeout:1000` passado a `requests.get(timeout=TIMEOUT)` — **em segundos** (ver §6).

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
      "place": {
        "address": "Rua de Santa Catarina, Nº 1232",
        "pc4": "4000", "pc3": "457", "city": "Porto"
      },
      "geo": {
        "region": "Porto", "county": "Porto", "parish": "Cedofeita"
      },
      "contacts": {
        "email": "info@nex.pt",
        "phone": "220 198 228",
        "website": "www.nex.pt",
        "fax": "224 905 459"
      },
      "structure": {
        "nature": "UNI",
        "capital": "248000.00",
        "capital_currency": "EUR"
      },
      "cae": ["62010", "63120", "62020", "46510"],
      "racius": "https://www.racius.com/nexperience-lda/",
      "portugalio": null
    }
  }
}
```

### 2.2 Normalização em `consulta_nif.py:74`

```python
records = data.get("records", {})
registo = records.get(nif, records.get(list(records.keys())[0] if records else None))
```

* `records` é dict com NIF como chave; fallback para primeira chave se `nif` não bater (ex: API devolve NIF sem zeros à esquerda).
* `consulta_nif.py:77` retorna dict normalizado:

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

## 3. Resposta — Erro

### 3.1 `result != "success"` (`consulta_nif.py:65`)

```json
{
  "result": "No records found",
  "nif_validation": false,
  "credits": { "used": "free", "left": [] },
  "records": {}
}
```

→ `consulta_nif.py:66` retorna `erro: data.get("result")` + `dados: data` completo, `valido: validar_nif(nif)`.

### 3.2 Erros de rede

| Exceção | `erro` | `valido` |
|---------|--------|----------|
| `requests.exceptions.Timeout` | `Timeout na consulta à API nif.pt` | `validar_nif(nif)` |
| `RequestException` | `Erro de rede: ...` | `validar_nif(nif)` |
| `JSONDecodeError` | `Resposta inválida (não JSON) da API` | `validar_nif(nif)` |

Código em `consulta_nif.py:54`.

### 3.3 Sem chave

Se `API_KEY` falta (`consulta_nif.py:40`):

```json
{
  "nif": "509442013",
  "valido": true,
  "fonte": null,
  "erro": "NIF-PT-KEY não encontrada no .env",
  "dados": null
}
```

Sem request de rede; `exit 1` em `consulta_nif.py:105`.

## 4. Validação

`consulta_nif.py:26` `validar_nif(nif)`:

```python
total = sum(int(d) * (9 - i) for i, d in enumerate(nif[:8]))
resto = total % 11
digito_controlo = 0 if resto in (0, 1) else 11 - resto
return digito_controlo == int(nif[8])
```

* `main():98` valida `nif.isdigit()` antes de rede → `{"erro":"NIF deve conter apenas dígitos"}`.
* Validação Mod-11 completa só afeta `valido` em casos de erro; **não bloqueia** `requests.get` (ver `MANUAL.md` §13.6).

## 5. Créditos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `credits.used` | `string` | `"free"` ou `"paid"` |
| `credits.left` | `dict` ou `[]` | Se `paid`: `{"month":int,"day":int,"hour":int,"minute":int,"paid":int}`; se `free`: `[]` (lista vazia) |

* `importar_nif.py:89` faz `creditos.get("left") or {}` → `{}` se `[]` → `parse_int(None)` → `NULL` em SQL. Não crasha mas perde créditos.

## 6. Timeouts e Retry

* `TIMEOUT` de `config.yaml:3` `timeout:1000` → `requests.get(timeout=1000)` **1000 segundos** ≈ 16min. Intenção provável `10` ou `1.0`. Recomenda-se `timeout: 10`.
* `retry_count` e `tempo_de_espera` em `config.yaml:2,4` **não implementados** — `consulta_nif.py` não faz `for attempt in range(retry_count+1)`.

## 7. Exemplo `curl`

```bash
curl "http://www.nif.pt/?json=1&q=509442013&key=SUA_CHAVE"
# ou via Python:
python consulta_nif.py 509442013 | jq .
```

## 8. Mapeamento para SQL

Ver `importar_nif.py:83` `mapear_registo()` e [docs/database/schema.md](../database/schema.md) §4.3. 36 colunas mapeadas de `dados.*` + `creditos.*`.

## 9. Referências

* `consulta_nif.py:48` `url = f"{API_BASE}/"` + `params = {"json":1,"q":nif,"key":API_KEY}`
* http://www.nif.pt/contactos/api/ — obtenção de chave
* Exemplo real em `data/nif_pt.db` (`509442013`, 2026-09-10)
