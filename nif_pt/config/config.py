import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

# Carrega .env
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Lê config.yaml
yaml_path = Path(__file__).parent / "config.yaml"
with open(yaml_path, "r") as f:
    CONFIG_YAML = yaml.safe_load(f)


# Função para obter config combinada por script
def get_config(script_name: str):
    """
    Retorna um dict com a configuração do script, combinando:
    - Config geral (default)
    - Config específica do script
    - Segredos do .env
    """
    
    if script_name not in CONFIG_YAML:
        raise ValueError(f"Configuração para o script '{script_name}' não encontrada no config.yaml.")
    else:
        # Config default (pode criar defaults se necessário)
        config = CONFIG_YAML.get("default", {}).copy()
        # Config específica do script
        script_config = CONFIG_YAML.get(script_name, {})
        config.update(script_config)

    # Adiciona segredos do .env
    config["AZURE_USER"] = os.getenv("AZURE_USER")
    config["AZURE_PALAVRA_CHAVE"] = os.getenv("AZURE_PALAVRA_CHAVE")
    config["API_TOKEN"] = os.getenv("API_TOKEN")
    config["NIF_PT_KEY"] = os.getenv("NIF-PT-KEY")

    return config