"""
config.config — Carregamento centralizado de configuração (YAML + .env).

Funde ``config/config.yaml`` (bloco ``default`` + bloco do script) com
segredos de ``config/.env`` via :mod:`dotenv`. Todos os scripts devem usar
:func:`get_config` em vez de ler ficheiros diretamente.

Exemplos:
    >>> from config.config import get_config
    >>> cfg = get_config("consulta_nif")
    >>> cfg["api_base"]
    'http://www.nif.pt'
    >>> cfg["timeout"]
    10
    >>> "NIF_PT_KEY" in cfg
    True

Notas:
    * O ficheiro YAML é lido com ``encoding="utf-8"`` e ``yaml.safe_load``.
    * ``NIF-PT-KEY`` tem hífen intencional — ``os.getenv("NIF-PT-KEY")``.
    * O valor de ``NIF_PT_KEY`` é mascarado no log como ``***XXXX``.
"""

import logging
import os
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Carrega .env
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Lê config.yaml
yaml_path = Path(__file__).parent / "config.yaml"
try:
    with open(yaml_path, "r", encoding="utf-8") as f:
        CONFIG_YAML = yaml.safe_load(f)
    logger.debug("[cfg] config.yaml carregado de %s", yaml_path)
except FileNotFoundError as e:
    logger.error("[cfg] config.yaml não encontrado: %s", e)
    raise
except yaml.YAMLError as e:
    logger.error("[cfg] Falha a ler config.yaml: %s", e)
    raise


# Função para obter config combinada por script
def get_config(script_name: str) -> dict:
    """Devolve configuração fundida para o script dado.

    Combina, por ordem de precedência crescente:

    1. ``default`` de ``config.yaml`` — chaves comuns (``retry_count``,
       ``timeout``, ``tempo_*``, ``max_tentativas_*``, ``cache_*``).
    2. Bloco específico ``config.yaml[script_name]`` (``consulta_nif``,
       ``importar_nif_sqlite``) — faz *shallow merge*
       ``config.update(script_config)``.
    3. Segredos de ``config/.env`` — ``API_TOKEN``, ``NIF-PT-KEY`` (com hífen).

    Args:
        script_name: Nome do bloco em ``config.yaml``. Valores válidos:
            ``"consulta_nif"``, ``"importar_nif_sqlite"``.
            Qualquer outro levanta ``ValueError``.

    Returns:
        Dicionário com todas as chaves fundidas. Chaves de segredos sempre
        presentes (``None`` se ``.env`` não definir):

        * ``NIF_PT_KEY`` — ``os.getenv("NIF-PT-KEY")`` (hífen!)
        * ``API_TOKEN`` — opcional, futuro

        Mais todas as chaves de ``default`` + bloco do script
        (``api_base``, ``db_path``, ``cache_*`` …).

    Raises:
        ValueError: Se ``script_name`` não existe em ``config.yaml``.
        FileNotFoundError: Se ``config.yaml`` não existe (no import).
        yaml.YAMLError: Se ``config.yaml`` é inválido (no import).

    Examples:
        >>> get_config("consulta_nif")["api_base"]
        'http://www.nif.pt'
        >>> get_config("importar_nif_sqlite")["db_path"]
        'data/nif_pt.db'
        >>> get_config("inexistente")  # doctest: +SKIP
        Traceback (most recent call last):
        ValueError: Configuração para o script 'inexistente' não encontrada

    See Also:
        :mod:`consulta_nif`, :mod:`importar_nif_sqlite`,
        :mod:`utils.error_handler` (lê ``tempo_espera_*`` e ``max_tentativas_*``),
        :mod:`utils.cache_validator` (lê ``cache_*``).

    Notas:
        * Loga ``[cfg] Segredos carregados NIF-PT-KEY=***XXXX`` sem expor valores.
        * Aviso se ``NIF-PT-KEY`` falta.
        * TIMING ``%.2fs`` (R9) com ``time.perf_counter``.
    """
    logger.debug(f"{' get_config() ':~^49}")
    t = time.perf_counter()

    if script_name not in CONFIG_YAML:
        logger.error("[cfg] Configuração para o script '%s' não encontrada no config.yaml.", script_name)
        raise ValueError(f"Configuração para o script '{script_name}' não encontrada no config.yaml.")
    else:
        # Config default (pode criar defaults se necessário)
        config = CONFIG_YAML.get("default", {}).copy()
        # Config específica do script
        script_config = CONFIG_YAML.get(script_name, {})
        config.update(script_config)
        logger.debug("[cfg] get_config(%s) merge default+script keys=%s", script_name, list(config.keys()))

    # Adiciona segredos do .env
    config["API_TOKEN"] = os.getenv("API_TOKEN")
    config["NIF_PT_KEY"] = os.getenv("NIF-PT-KEY")

    # Log mascarado — nunca logar valor completo
    nif_key = config["NIF_PT_KEY"]
    masked_key = f"***{nif_key[-4:]}" if nif_key and len(nif_key) >= 4 else ("***" if nif_key else "MISSING")
    logger.info(
        "[cfg] Segredos carregados NIF-PT-KEY=%s",
        masked_key,
    )
    if not nif_key:
        logger.warning("[cfg] NIF-PT-KEY com hífen não encontrada — verificar config/.env (NIF-PT-KEY=...)")

    logger.debug("[cfg] get_config(%s) -> %.2fs", script_name, time.perf_counter() - t)

    return config
