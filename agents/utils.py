"""
Model Configuration
Centralized model initialization for all agents.
Choose which model to use - by default, we use gpt-4o-mini, but you can uncomment and use other models as needed.
"""

from langchain.chat_models import init_chat_model
from langchain_openai import ChatOpenAI

# Model initialization - choose your model
# Default: gpt-4o-mini (recommended for most use cases)

# Option 1: OpenAI GPT-4o-mini (default, vision-capable)
model = init_chat_model("gpt-4o-mini", temperature=0)

# Option 2: Anthropic Claude Sonnet 4.5 (uncomment to use)
# model = init_chat_model("claude-sonnet-4-5", temperature=0)