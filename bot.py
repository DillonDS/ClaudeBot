import os 
import json
import asyncio
import logging
from typing import Optional
import discord
from discord.ext import commands
import anthropic
import boto3
from dotenv import load_dotenv


# logging 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ClaudeBot class
class ClaudeBot:
    # initializes the bot with optional attributes
    def __init__(self):
        self.discord_token: Optional[str] = None
        self.claude_api_key: Optional[str] = None
        self.claude_client: Optional[anthropic.Anthropic] = None
        self.bot: Optional[commands.Bot] = None
        
    def get_claude_api_key(self) -> str:
        # Claude API key from either .env or AWS Secrets Manager
        # First method: try .env file
        if os.path.exists('.env'):
            load_dotenv()
            key = os.getenv("CLAUDE_API_KEY")
            if key: 
                logger.info("Using local development API")
                return key 
            else:
                logger.warning(".env file found but API key not found")
        # Second method: try AWS Secrets Manager
        try: 
            key = self.get_aws_secret()
            logger.info("Using AWS Secrets Manager API key")
            return key 
        except Exception as e:
            logger.error(f"Failed to get API key from AWS: {e}")
        # If both fail 
        logger.error("Could not retrieve API key from source")
        raise ValueError("Claude API key not found in any configured source")
    
    def get_aws_secret(self) -> str:
        try:
            region = os.getenv("AWS_REGION", "us-east-1")
            client = boto3.client('secretsmanager', region_name=region)
            secret_name = os.getenv("AWS_SECRET_NAME")
            response = client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response['SecretString'])
            return secret_data['claude_api_key']
        except Exception as e:
            logger.error(f"Error retrieving secret from AWS: {e}")
            raise Exception(f"AWS Secrets Manager error: {str(e)}")
        
    def get_discord_token(self) -> str:
        if os.path.exists('.env'):
            load_dotenv()
        token = os.getenv("DISCORD_TOKEN")
        if token:
            logger.info("Discord token retrieved from environment")
            return token
        else:
            logger.error("Discord token not found in environment")
            raise ValueError("Discord bot token not found in environment")

    def initialize_clients(self):
        try: 
            self.discord_token = self.get_discord_token()
            self.claude_api_key = self.get_claude_api_key()
            
            self.claude_client = anthropic.Anthropic(api_key=self.claude_api_key)
            logger.info("Claude client initialized")
            
            intents = discord.Intents.default()
            intents.message_content = True
            intents.presences = True
            intents.guilds = True
            
            self.bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)
        except Exception as e:
            logger.error(f"Error initializing clients: {e}")
            raise 


def main():
    bot = ClaudeBot()

if __name__ == "__main__":
    main()