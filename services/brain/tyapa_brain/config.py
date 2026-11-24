import os

# The only place LLM settings are read. OPENAI_API_KEY is read from the environment by the client.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-5.4-nano")

# Seconds to wait for each service's reply. Speech blocks while the dog talks, hence the long one.
HEARING_TIMEOUT_S = 5
SPEECH_TIMEOUT_S = 60
BODY_TIMEOUT_S = 2
