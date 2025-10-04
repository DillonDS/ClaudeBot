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
import base64
from datetime import datetime, timezone

# print(f"Current directory: {os.getcwd()}")
# print(f".env exists: {os.path.exists('.env')}")

# logging 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ClaudeBot class
class ClaudeBot:
    # initializes the bot with optional attributes
    def __init__(self):
        self.discord_token: Optional[str] = None
        self.claude_api_key: Optional[str] = None
        self.claude_client: Optional[anthropic.Anthropic] = None # will become an Claude client object
        self.bot: Optional[commands.Bot] = None # will become a Discord bot object 
        self.start_time: Optional[datetime] = None

    def get_claude_api_key(self) -> str:
        # Claude API key from either .env or AWS Secrets Manager
        
        # First method: try .env file
        load_dotenv()
        key = os.getenv("CLAUDE_API_KEY")
        if key: 
            logger.info("Using local development API")
            return key 
            
        # Second method: try AWS Secrets Manager
        try: 
            key = self.get_aws_secret()
            logger.info("Using AWS Secrets Manager API key")
            return key 
        except Exception as e:
            logger.warning(f"Failed to get API key from AWS: {e}")
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
        # if os.path.exists('.env'):
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
            
            self.bot = commands.Bot(command_prefix='/', intents=intents, help_command=None) # Discord bot object
        except Exception as e:
            logger.error(f"Error initializing clients: {e}")
            raise 
    
    def setup_events(self): 
        @self.bot.event
        async def on_ready():
            logger.info(f"{self.bot.user} connected to Discord!")
            try:
                synced = await self.bot.tree.sync() # sync slash commands - CommandTree object
                logger.info(f"Synced {len(synced)} slash commands")
                
                await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="for mentions"))

                if self.start_time is None:
                    self.start_time = datetime.now(timezone.utc)
                    logger.info(f"Bot started at {self.start_time}")
                
            except Exception as e:
                logger.error(f"Failed to setup events: {e}")

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author.bot:  # skip all bot messages
                return
            
            if self.bot.user in message.mentions: # if bot is mentioned
                await self.handle_mention(message) 
            
            await self.moderate_message(message)

            await self.bot.process_commands(message) 

    async def handle_mention(self, message: discord.Message): 
        try:  
            # Message content logic 
            message_content = message.content.replace(f'<@{self.bot.user.id}>', '').strip()
            if not message_content and not message.attachments:
                await message.reply(f"You mentioned me with an empty message bozo <a:emote_name:1423865523011190795>")
                return
            
            # Reply context logic
            if message.reference:
                referenced_message = await message.channel.fetch_message(message.reference.message_id)
                if referenced_message and referenced_message.author != self.bot.user:
                    referenced_content = referenced_message.content
                    message_content = f"Context: The user is replying to: {referenced_content}\n\nUser's Message: {message_content}" 
                # include logic to include image if reply references an image
            
            # Claude content assembly
            claude_content = [
                {
                    "type": "text",
                    "text": message_content
                }
            ]
            
            # Image logic
            if message.attachments:
                for attachment in message.attachments:
                    if attachment.content_type and attachment.content_type.startswith('image/'):
                        image_data = await attachment.read()
                        base64_image = base64.b64encode(image_data).decode('utf-8')
                        claude_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": attachment.content_type,
                                "data": base64_image
                            }
                        })
                    else:
                        logger.info(f"Skipping non-image attachment: {attachment.filename}")
                    
            async with message.channel.typing():
                response = await self.claude_response(claude_content)
            
            if response:
                await self.long_message(message.channel, response)
            else:
                await message.reply("Claude did not return a response.")
            
        except Exception as e:
            logger.error(f"Error handling mention: {e}")
            await message.reply("I encountered an error processing your request.")

    async def moderate_message(self, message: discord.Message):
        return

    async def claude_response(self, claude_content) -> str:
        try:
            response = await asyncio.to_thread(
                self.claude_client.messages.create,
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                temperature=0.6,
                messages=[{
                    "role": "user",
                    "content": claude_content
                }]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error getting Claude response: {e}")
            return "Error retrieving response from Claude."

    async def long_message(self, channel: discord.TextChannel, content: str):
        max_length = 2000
        try:
            if len(content) <= max_length:
                await channel.send(content)
            else:
                chunks = [content[i:i+max_length] for i in range
                            (0, len(content), max_length)]
                for chunk in chunks:
                    await channel.send(chunk)
        except Exception as e:
            logger.error(f"Error sending long message: {e}")

    def slash_commands(self):
        beer_counter = 0
        @self.bot.tree.command(name="beer", description="Share a beer with ClaudeBot")
        async def beer_command(interaction: discord.Interaction):
            nonlocal beer_counter
            beer_counter += 1
            await interaction.response.send_message(f"Cheers! {beer_counter} beers have been shared with ClaudeBot")

        @self.bot.tree.command(name="ping", description="Check bot responsiveness")
        async def ping_command(interaction: discord.Interaction):
            latency = round(self.bot.latency, 2)
            await interaction.response.send_message(f"Latency: {latency} seconds")

        @self.bot.tree.command(name="uptime", description="Check bot uptime")
        async def uptime_command(interaction: discord.Interaction):
           if self.start_time:
               current_time = datetime.now(timezone.utc)
               uptime_delta = current_time - self.start_time
               days, seconds = uptime_delta.days, uptime_delta.seconds
               hours, minutes = divmod(seconds, 3600)
               minutes, seconds = divmod(minutes, 60)
               uptime = f"Uptime: {days}d {hours}h {minutes}m {seconds}s"
               await interaction.response.send_message(uptime)

    async def start(self):
        try:
            logger.info("Starting ClaudeBot...")
            self.initialize_clients()
            self.setup_events()
            self.slash_commands()
            await self.bot.start(self.discord_token)
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise

def main():
    bot = ClaudeBot()
    try:
        asyncio.run(bot.start())
    except Exception as e:
        logger.error(f"Bot Crashed: {e}")

if __name__ == "__main__":
    main()