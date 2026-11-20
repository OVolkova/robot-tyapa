import os

# forwarded to Mind -> create_llm_client
# OPENAI_API_KEY (or ANTHROPIC_API_KEY, once supported) must also be set in environment
LLM_PROVIDER = os.environ.get("LLM_PROVIDER")  # None -> "openai" default
LLM_MODEL = os.environ.get("LLM_MODEL")  # None -> gpt-5.4-nano default
