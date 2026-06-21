from langchain_ollama import ChatOllama


def build_text_llm(config):
    return ChatOllama(model=config.text_model, temperature=0, base_url=config.llm_url)


def build_vision_llm(config):
    return ChatOllama(model=config.vision_model, temperature=0, base_url=config.llm_url)
