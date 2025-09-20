from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig


boto_config = BotocoreConfig(
    retries={"max_attempts": 4, "mode": "standard"},
    read_timeout=1000
)

sonnet37_model = BedrockModel(
    model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    temperature=0,
    top_p=1,
    max_tokens=131072,
    boto_client_config=boto_config, 
)


opus4_model = BedrockModel(
    model_id="us.anthropic.claude-opus-4-20250514-v1:0",
    temperature=0.2,
    max_tokens=10000,
    boto_client_config=boto_config, 
)

sonnet35_model = BedrockModel(
    model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    temperature=1,
    top_p=1,
    max_tokens=8191,
    boto_client_config=boto_config, 
)

nova_pro_model = BedrockModel(
    model_id="us.amazon.nova-pro-v1:0",
    temperature=0.5,
    max_tokens=10000,
    boto_client_config=boto_config, 
)

# Create the central orchestrator with interleaved thinking
sonnet4_model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    temperature=0.1,  # Need temperature 1 for creative thinking
    top_p=0.95,
    max_tokens=65536,
    boto_client_config=boto_config,
)