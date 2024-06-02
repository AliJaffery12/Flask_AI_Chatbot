import os
import botocore
import botocore.session
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig
import weaviate
import json
from dotenv import load_dotenv
load_dotenv()

aws_region = "eu-central-1"  

# Create an AWS Secrets Manager client with the region and credentials specified
client = botocore.session.get_session().create_client(
    'secretsmanager',
    region_name=aws_region,
   
)

# Create a Secret Cache
cache_config = SecretCacheConfig()
cache = SecretCache(config=cache_config, client=client)

# Retrieve the secret
app_mode = os.environ.get("APP_MODE", "PROD")
secret_name = 'studentSupportBotTest' if app_mode == "DEV" else 'studentSupportBot'
secret = cache.get_secret_string(secret_name)

# Parse the JSON string into a dictionary
secrets_dict = json.loads(secret)
print(secrets_dict)
# Access environment variables
AZURE_OPENAI_BASE = secrets_dict.get("AZURE_OPENAI_BASE")
AZURE_OPENAI_KEY = secrets_dict.get("AZURE_OPENAI_KEY")
GPT4_DEPLOYMENT_ID = secrets_dict.get("GPT4_DEPLOYMENT_ID")
GPT3_DEPLOYMENT_ID = secrets_dict.get("GPT3_DEPLOYMENT_ID")
WEAVIATE_URL = secrets_dict.get("WEAVIATE_URL")
WEAVIATE_API_KEY = secrets_dict.get("WEAVIATE_API_KEY")
CONFLUENCE_USERNAME = secrets_dict.get("CONFLUENCE_USERNAME")
CONFLUENCE_API_TOKEN = secrets_dict.get("CONFLUENCE_API_TOKEN")
SLACK_SIGNING_SECRET = secrets_dict.get("SLACK_SIGNING_SECRET")
SLACK_BOT_TOKEN = secrets_dict.get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = secrets_dict.get("SLACK_APP_TOKEN")
WS_TOKEN=secrets_dict.get("ws_token")
weaviate_config =  {
    "url": WEAVIATE_URL,
    "auth_client_secret": weaviate.AuthApiKey(api_key=WEAVIATE_API_KEY),
    "additional_headers": {
        "X-Azure-Api-Key": AZURE_OPENAI_KEY
    }
}