from importlib.metadata import PackageNotFoundError, version

from pydantic_settings import BaseSettings


def get_version():
    try:
        return version("mimic")
    except PackageNotFoundError:
        # Fallback for development when package isn't installed
        return "dev"


class Settings(BaseSettings):
    APP_NAME: str = "Mimic"
    VERSION: str = get_version()
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    GITHUB_TOKEN: str = ""
    UNIFY_API_HOST: str = "https://api.cloudbees.io"
    UNIFY_API_KEY: str = ""  # Optional - only required for MCP mode
    CLOUDBEES_ENDPOINT_ID: str = "9a3942be-0e86-415e-94c5-52512be1138d"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
