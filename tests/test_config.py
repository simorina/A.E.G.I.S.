import pytest
from agent.config import load_config, Config, ConfigError

BASE_ENV = {
    "DB_USER": "postgres", "DB_PASS": "secret", "DB_HOST": "localhost",
    "DB_PORT": "5432", "DB_NAME": "aegis", "TARGET_SCHEMA": "schema1",
    "LLM_URL": "http://localhost:11434", "MODEL_NAME": "nemotron",
}

def test_loads_valid_config():
    cfg = load_config(BASE_ENV)
    assert isinstance(cfg, Config)
    assert cfg.schema == "schema1"
    assert cfg.db_uri == "postgresql://postgres:secret@localhost:5432/aegis"

def test_models_fallback_to_model_name():
    cfg = load_config(BASE_ENV)
    assert cfg.text_model == "nemotron"
    assert cfg.vision_model == "nemotron"

def test_explicit_models_override_fallback():
    env = {**BASE_ENV, "TEXT_MODEL": "qwen", "VISION_MODEL": "llava"}
    cfg = load_config(env)
    assert cfg.text_model == "qwen"
    assert cfg.vision_model == "llava"

def test_missing_required_var_raises():
    env = {k: v for k, v in BASE_ENV.items() if k != "DB_HOST"}
    with pytest.raises(ConfigError):
        load_config(env)

def test_no_model_configured_raises():
    env = {k: v for k, v in BASE_ENV.items() if k != "MODEL_NAME"}
    with pytest.raises(ConfigError):
        load_config(env)

def test_defaults_for_optional_numbers():
    cfg = load_config(BASE_ENV)
    assert cfg.statement_timeout_ms == 5000
    assert cfg.memory_turns == 6
    assert cfg.top_k == 100
    assert cfg.tool_calling is True

def test_tool_calling_can_be_disabled():
    env = {**BASE_ENV, "AGENT_TOOL_CALLING": "off"}
    assert load_config(env).tool_calling is False

def test_recursion_limit_default_and_override():
    assert load_config(BASE_ENV).recursion_limit == 25
    assert load_config({**BASE_ENV, "RECURSION_LIMIT": "5"}).recursion_limit == 5
