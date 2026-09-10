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
def get_config(script_name: str):
    """
    Retorna um dict com a configuração do script, combinando:
    - Config geral (default)
    - Config específica do script
    - Segredos do .env
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
    config["AZURE_USER"] = os.getenv("AZURE_USER")
    config["AZURE_PALAVRA_CHAVE"] = os.getenv("AZURE_PALAVRA_CHAVE")
    config["API_TOKEN"] = os.getenv("API_TOKEN")
    config["NIF_PT_KEY"] = os.getenv("NIF-PT-KEY")

    # Log mascarado — nunca logar valor completo
    nif_key = config["NIF_PT_KEY"]
    masked_key = f"***{nif_key[-4:]}" if nif_key and len(nif_key) >= 4 else ("***" if nif_key else "MISSING")
    logger.info(
        "[cfg] Segredos carregados AZURE_USER=%s NIF-PT-KEY=%s",
        "OK" if config["AZURE_USER"] else "MISSING",
        masked_key,
    )
    if not nif_key:
        logger.warning("[cfg] NIF-PT-KEY com hífen não encontrada — verificar config/.env (NIF-PT-KEY=...)")

    logger.debug("[cfg] get_config(%s) -> %.2fs", script_name, time.perf_counter() - t)

    return config
