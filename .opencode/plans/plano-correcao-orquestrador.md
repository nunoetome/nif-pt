# Plano de Correção - Orquestrador NIF.pt

## Problemas Identificados

1. **Rate Limiter espera sempre 60s** - `orquestrador.py:95` usa `max(max_wait, self.pause)` onde `self.pause = 60`
2. **Log do erro "error" sem contexto** - `consulta_nif.py:65-72` mostra apenas "error" sem detalhes
3. **Sem tratamento de Ctrl+C** - KeyboardInterrupt causa traceback

---

## Alterações Propostas

### 1. Corrigir Rate Limiter (`orquestrador.py:95`)

**Antes:**
```python
sleep_time = max(max_wait, float(self.pause))
```

**Depois:**
```python
sleep_time = max(max_wait, min(float(self.pause), 5.0))
```

**Razão:** O `self.pause` (60s) é usado como fallback quando `max_wait` é muito pequeno. Com `min(60, 5) = 5`, garantimos:
- Se `max_wait` = 59s → espera 59s
- Se `max_wait` = 2s → espera 5s (mínimo para evitar spam)
- Se `max_wait` = 0 → não espera

---

### 2. Adicionar Função `_classificar_erro_api()` (`consulta_nif.py`)

Adicionar antes de `consultar_nif()`:

```python
def _classificar_erro_api(data: dict, nif: str) -> str:
    """Classifica o erro da API e devolve uma descrição legível."""
    result = data.get("result", "")
    error = data.get("error", "")
    
    if result == "error":
        error_lower = error.lower()
        # NIFs privados/inexistentes
        if any(kw in error_lower for kw in ["not found", "não encontrado", "invalid", "inválido"]):
            return "NIF privado ou inexistente"
        # Limite de taxa
        if any(kw in error_lower for kw in ["limit", "rate", "quota"]):
            return "Limite de taxa atingido"
        # Erro genérico
        return error or "Erro desconhecido da API"
    
    return result
```

---

### 3. Atualizar Tratamento de Erros (`consulta_nif.py:65-72`)

**Antes:**
```python
if data.get("result") != "success":
    return {
        "nif": nif,
        "valido": validar_nif(nif),
        "fonte": "nif.pt",
        "erro": data.get("result", "Erro desconhecido da API"),
        "dados": data,
    }
```

**Depois:**
```python
if data.get("result") != "success":
    erro_msg = _classificar_erro_api(data, nif)
    return {
        "nif": nif,
        "valido": validar_nif(nif),
        "fonte": "nif.pt",
        "erro": erro_msg,
        "dados": data,
    }
```

---

### 4. Adicionar Retry Logic para Erros de Limite (`consulta_nif.py`)

Modificar `consultar_nif()` para incluir retry:

```python
def consultar_nif(nif: str, max_retries: int = 3) -> dict:
    """Consulta um NIF na API nif.pt com retry automático para erros de limite."""
    if not API_KEY:
        return {
            "nif": nif,
            "valido": validar_nif(nif),
            "fonte": None,
            "erro": "NIF-PT-KEY não encontrada no .env",
            "dados": None,
        }

    url = f"{API_BASE}/"
    params = {"json": 1, "q": nif, "key": API_KEY}

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            return {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt",
                    "erro": "Timeout na consulta à API nif.pt", "dados": None}
        except requests.exceptions.RequestException as e:
            return {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt",
                    "erro": f"Erro de rede: {e}", "dados": None}
        except json.JSONDecodeError:
            return {"nif": nif, "valido": validar_nif(nif), "fonte": "nif.pt",
                    "erro": "Resposta inválida (não JSON) da API", "dados": None}

        if data.get("result") != "success":
            erro_msg = _classificar_erro_api(data, nif)
            
            # Retry se for erro de limite
            if "Limite de taxa" in erro_msg and attempt < max_retries - 1:
                wait_time = 60 * (attempt + 1)
                logger.warning(f"[api] Limite atingido para NIF {nif}. Retry {attempt+1}/{max_retries} em {wait_time}s...")
                time.sleep(wait_time)
                continue
            
            return {
                "nif": nif,
                "valido": validar_nif(nif),
                "fonte": "nif.pt",
                "erro": erro_msg,
                "dados": data,
            }

        records = data.get("records", {})
        registo = records.get(nif, records.get(list(records.keys())[0] if records else None))

        return {
            "nif": nif,
            "valido": True,
            "fonte": "nif.pt",
            "erro": None,
            "dados": registo,
            "nif_valido_formato": data.get("nif_validation"),
            "creditos": data.get("credits"),
        }

    # Se todos os retries falharam
    return {
        "nif": nif,
        "valido": validar_nif(nif),
        "fonte": "nif.pt",
        "erro": f"Falhou após {max_retries} tentativas",
        "dados": None,
    }
```

---

### 5. Adicionar Tratamento de Ctrl+C (`orquestrador.py`)

Modificar o loop principal em `main()`:

**Antes (linhas 283-328):**
```python
for idx, nif in enumerate(nifs, 1):
    # ... ciclo existente ...
```

**Depois:**
```python
try:
    for idx, nif in enumerate(nifs, 1):
        logger.info(f"[{idx}/{total}] NIF: {nif}")

        if not validar_nif(nif):
            erros += 1
            logger.warning(f"NIF {nif}: inválido (digito de controlo errado) — a saltar")
            resultado = {
                "nif": nif,
                "valido": False,
                "fonte": None,
                "erro": "NIF inválido (digito de controlo errado)",
                "dados": None,
            }
            processados.add(nif)
            guardar_progresso(processados, rate_limiter)
            continue

        rate_limiter.esperar_se_necessario()

        try:
            resultado = consultar_nif(nif)
        except Exception as e:
            logger.error(f"Erro na consulta do NIF {nif}: {e}")
            resultado = {
                "nif": nif,
                "valido": False,
                "fonte": "nif.pt",
                "erro": str(e),
                "dados": None,
            }

        rate_limiter.registar_pedido()

        if resultado.get("erro"):
            erros += 1
            logger.warning(f"NIF {nif}: {resultado['erro']}")
        else:
            logger.info(f"NIF {nif}: OK")

        if usar_sqlite:
            _inserir_sqlite(resultado)
        if usar_azure:
            _inserir_azure(resultado)

        processados.add(nif)
        guardar_progresso(processados, rate_limiter)

except KeyboardInterrupt:
    logger.info("[main] Interrompido pelo utilizador. A guardar progresso...")
    guardar_progresso(processados, rate_limiter)
    logger.info(f"[main] Progresso guardado: {len(processados)} NIF(s) processados")
    sys.exit(0)
```

---

## Ficheiros a Modificar

| Ficheiro | Linhas | Alteração |
|----------|--------|-----------|
| `orquestrador.py` | 95 | Corrigir `sleep_time` |
| `orquestrador.py` | 283-328 | Adicionar try/except KeyboardInterrupt |
| `consulta_nif.py` | Novo | Adicionar `_classificar_erro_api()` |
| `consulta_nif.py` | 38-85 | Adicionar retry logic e import time |

---

## Notas

- Todas as alterações seguem o Livro de Estilo de Logs (TAGs [rate], [api], [main])
- O retry logic usa backoff exponencial (60s, 120s, 180s)
- A classificação de erros detecta NIFs privados e erros de limite
- O Ctrl+C guarda progresso antes de sair
