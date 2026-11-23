import os

# Forwarded to create_llm_client. OPENAI_API_KEY must be set in the environment.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER")  # None -> "openai" default
LLM_MODEL = os.environ.get("LLM_MODEL")  # None -> gpt-5.4-nano default
