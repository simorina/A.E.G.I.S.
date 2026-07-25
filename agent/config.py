import os
from dataclasses import dataclass
from typing import Mapping, Optional


class ConfigError(Exception):
    """Configurazione mancante o non valida."""


_REQUIRED = ("DB_USER", "DB_PASS", "DB_HOST", "DB_PORT", "DB_NAME",
             "TARGET_SCHEMA", "LLM_URL")


@dataclass(frozen=True)
class Config:
    db_uri: str
    schema: str
    llm_url: str
    text_model: str
    vision_model: str
    statement_timeout_ms: int
    memory_turns: int
    top_k: int
    tool_calling: bool
    recursion_limit: int


def load_config(env: Optional[Mapping[str, str]] = None) -> Config:
    env = os.environ if env is None else env

    missing = [k for k in _REQUIRED if not env.get(k)]
    if missing:
        raise ConfigError(f"Missing required env vars: {', '.join(missing)}")

    base_model = env.get("MODEL_NAME", "")
    text_model = env.get("TEXT_MODEL") or base_model
    vision_model = env.get("VISION_MODEL") or base_model
    if not text_model:
        raise ConfigError("No TEXT_MODEL or MODEL_NAME configured")
    if not vision_model:
        raise ConfigError("No VISION_MODEL or MODEL_NAME configured")

    db_uri = (f"postgresql://{env['DB_USER']}:{env['DB_PASS']}@"
              f"{env['DB_HOST']}:{env['DB_PORT']}/{env['DB_NAME']}")

    return Config(
        db_uri=db_uri,
        schema=env["TARGET_SCHEMA"],
        llm_url=env["LLM_URL"],
        text_model=text_model,
        vision_model=vision_model,
        statement_timeout_ms=int(env.get("STATEMENT_TIMEOUT_MS", "5000")),
        memory_turns=int(env.get("MEMORY_TURNS", "6")),
        top_k=int(env.get("TOP_K", "100")),
        tool_calling=env.get("AGENT_TOOL_CALLING", "on").strip().lower() != "off",
        recursion_limit=int(env.get("RECURSION_LIMIT", "12")),
    )
