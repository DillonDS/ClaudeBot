import os
import json
import asyncio
import logging
from typing import Optional
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands
import anthropic
import boto3
from dotenv import load_dotenv
import base64

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.gateway').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)


class ClaudeBot:
    """
    A Discord bot powered by Claude that maintains conversation context
    per channel and responds based on self-scoring.
    """

    # Configuration constants
    MAX_TOKENS_PER_CHANNEL = 150000        # 150k token limit per channel
    MESSAGE_EXPIRY_DAYS = 30                # Remove messages older than 30 days
    CHARS_PER_TOKEN_ESTIMATE = 4            # Rough estimate for token counting
    MAX_RESPONSE_TOKENS = 300               # Keep responses brief
    SCORE_THRESHOLD = 8                     # Only respond if score >= 8
    RATE_LIMIT_SECONDS = 2                  # Minimum seconds between responses per channel
    CACHE_FILE = 'conversation_cache.json'  # Persistent cache file

    # Categories to skip conversation history
    SKIP_CATEGORIES = {"Information"}

    def __init__(self):
        self.discord_token: Optional[str] = None
        self.claude_api_key: Optional[str] = None
        self.claude_client: Optional[anthropic.Anthropic] = None
        self.bot: Optional[commands.Bot] = None
        self.start_time: Optional[datetime] = None

        # Conversation cache: category_name -> channel_id -> list of messages
        # Each message: {"user": str, "content": str, "timestamp": datetime,
        #                "mentioned_bot": bool, "channel_name": str}
        self.conversation_cache = defaultdict(lambda: defaultdict(list))

        # Rate limiting: channel_id -> last response timestamp
        self.last_response_time: dict[int, datetime] = {}

        # Load persistent cache on startup
        self.load_cache()

    # =========================================================================
    # API Key & Token Management
    # =========================================================================

    def get_claude_api_key(self) -> str:
        """Get Claude API key from .env (local) or AWS Secrets Manager (production)."""
        load_dotenv()
        key = os.getenv("CLAUDE_API_KEY")
        if key:
            logger.info("Using local development API key")
            return key

        try:
            key = self.get_aws_secret()
            logger.info("Using AWS Secrets Manager API key")
            return key
        except Exception as e:
            logger.warning(f"Failed to get API key from AWS: {e}")

        logger.error("Could not retrieve API key from any source")
        raise ValueError("Claude API key not found in any configured source")

    def get_aws_secret(self) -> str:
        """Retrieve Claude API key from AWS Secrets Manager."""
        try:
            region = os.getenv("AWS_REGION", "us-east-2")
            client = boto3.client('secretsmanager', region_name=region)
            secret_name = os.getenv("AWS_SECRET_NAME")
            response = client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response['SecretString'])
            return secret_data['claude_api_key']
        except Exception as e:
            logger.error(f"Error retrieving secret from AWS: {e}")
            raise

    def get_discord_token(self) -> str:
        """Get Discord bot token from environment."""
        load_dotenv()
        token = os.getenv("DISCORD_TOKEN")
        if token:
            logger.info("Discord token retrieved")
            return token
        logger.error("Discord token not found")
        raise ValueError("Discord bot token not found in environment")

    def initialize_clients(self):
        """Initialize Discord bot and Claude client."""
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

    # =========================================================================
    # Persistent Cache (Save/Load)
    # =========================================================================

    def load_cache(self):
        """Load conversation cache from file on startup."""
        try:
            with open(self.CACHE_FILE, 'r') as f:
                data = json.load(f)

            # Reconstruct the nested defaultdict with datetime conversion
            for category, channels in data.items():
                for channel_id_str, messages in channels.items():
                    channel_id = int(channel_id_str)
                    for msg in messages:
                        # Convert ISO string back to datetime
                        msg['timestamp'] = datetime.fromisoformat(msg['timestamp'])
                        self.conversation_cache[category][channel_id].append(msg)

            total_msgs = sum(
                len(msgs) for channels in self.conversation_cache.values()
                for msgs in channels.values()
            )
            logger.info(f"Loaded {total_msgs} messages from cache file")
        except FileNotFoundError:
            logger.info("No existing cache file, starting fresh")
        except Exception as e:
            logger.warning(f"Error loading cache: {e}, starting fresh")

    def save_cache(self):
        """Save conversation cache to file for persistence."""
        try:
            # Convert to regular dict and serialize datetimes
            data = {}
            for category, channels in self.conversation_cache.items():
                data[category] = {}
                for channel_id, messages in channels.items():
                    data[category][str(channel_id)] = [
                        {
                            **msg,
                            'timestamp': msg['timestamp'].isoformat()
                        }
                        for msg in messages
                    ]

            with open(self.CACHE_FILE, 'w') as f:
                json.dump(data, f, indent=2)

            total_msgs = sum(
                len(msgs) for channels in self.conversation_cache.values()
                for msgs in channels.values()
            )
            logger.info(f"Saved {total_msgs} messages to cache file")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")

    # =========================================================================
    # Conversation Cache Management
    # =========================================================================

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count from text.
        Uses ~4 chars per token which is a reasonable approximation for English.
        For exact counts, you'd need tiktoken with cl100k_base encoding.
        """
        # Character-based estimate for cache management
        return len(text) // self.CHARS_PER_TOKEN_ESTIMATE

    def get_channel_token_count(self, category: str, channel_id: int) -> int:
        """Calculate total estimated tokens for a channel's conversation history."""
        messages = self.conversation_cache[category][channel_id]
        total = 0
        for msg in messages:
            total += self.estimate_tokens(f"{msg['user']}: {msg['content']}")
        return total

    def cleanup_old_messages(self, category: str, channel_id: int):
        """Remove messages older than MESSAGE_EXPIRY_DAYS."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.MESSAGE_EXPIRY_DAYS)
        messages = self.conversation_cache[category][channel_id]

        # Filter out old messages
        original_count = len(messages)
        self.conversation_cache[category][channel_id] = [
            msg for msg in messages if msg['timestamp'] > cutoff
        ]

        removed = original_count - len(self.conversation_cache[category][channel_id])
        if removed > 0:
            logger.info(f"Cleaned up {removed} messages older than {self.MESSAGE_EXPIRY_DAYS} days")

    def enforce_token_limit(self, category: str, channel_id: int):
        """Remove oldest messages if channel exceeds token limit."""
        while self.get_channel_token_count(category, channel_id) > self.MAX_TOKENS_PER_CHANNEL:
            messages = self.conversation_cache[category][channel_id]
            if messages:
                removed = messages.pop(0)  # Remove oldest message
                logger.info(f"Removed old message to stay under token limit")
            else:
                break

    def add_message_to_cache(self, message: discord.Message, mentioned_bot: bool):
        """Add a message to the conversation cache."""
        category = message.channel.category.name if message.channel.category else "Uncategorized"

        # Skip categories add message to cache
        if category in self.SKIP_CATEGORIES:
            return

        channel_id = message.channel.id
        channel_name = message.channel.name

        # Create message entry
        msg_entry = {
            "user": message.author.display_name,
            "content": message.content.strip(),
            "timestamp": datetime.now(timezone.utc),
            "mentioned_bot": mentioned_bot,
            "channel_name": channel_name
        }

        # Add to cache
        self.conversation_cache[category][channel_id].append(msg_entry)

        # Remove old messages and enforce token limit
        self.cleanup_old_messages(category, channel_id)
        self.enforce_token_limit(category, channel_id)

        # Save cache (every 10 messages)
        total_msgs = sum(len(msgs) for ch in self.conversation_cache.values() for msgs in ch.values())
        if total_msgs % 10 == 0:
            self.save_cache()

    def add_bot_response_to_cache(self, message: discord.Message):
        """Add ClaudeBot's own response to cache for context continuity."""
        if not message.channel.category:
            category = "Uncategorized"
        else:
            category = message.channel.category.name

        # Skip categories add bot response to cache
        if category in self.SKIP_CATEGORIES:
            return

        channel_id = message.channel.id
        channel_name = message.channel.name

        # Use "ClaudeBot" in conversation history
        msg_entry = {
            "user": "ClaudeBot",
            "content": message.content.strip(),
            "timestamp": datetime.now(timezone.utc),
            "mentioned_bot": False,
            "channel_name": channel_name
        }

        self.conversation_cache[category][channel_id].append(msg_entry)
        self.cleanup_old_messages(category, channel_id)
        self.enforce_token_limit(category, channel_id)

    def get_conversation_history(self, message: discord.Message) -> str:
        """Build formatted conversation history for Claude."""
        category = message.channel.category.name if message.channel.category else "Uncategorized"
        channel_id = message.channel.id
        channel_name = message.channel.name

        messages = self.conversation_cache[category][channel_id]

        if not messages:
            return ""

        # Format conversation history
        lines = [f"[#{channel_name} in {category}]", "Recent conversation:"]
        for msg in messages:
            lines.append(f"{msg['user']}: {msg['content']}")

        return "\n".join(lines)

    # =========================================================================
    # Discord Event Handlers
    # =========================================================================

    def setup_events(self):
        @self.bot.event
        async def on_ready():
            logger.info(f"{self.bot.user} connected to Discord!")
            try:
                synced = await self.bot.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands")

                if self.start_time is None:
                    self.start_time = datetime.now(timezone.utc)
                    logger.info(f"Bot started at {self.start_time}")
            except Exception as e:
                logger.error(f"Failed to setup events: {e}")

        @self.bot.event
        async def on_message(message: discord.Message):
            # Add bot's OWN responses to cache for context continuity
            if message.author == self.bot.user:
                self.add_bot_response_to_cache(message)
                return

            # Skip other bots entirely
            if message.author.bot:
                return

            await self.handle_message(message)
            await self.bot.process_commands(message)

    # =========================================================================
    # Image Detection
    # =========================================================================

    def detect_image_type(self, image_data: bytes) -> str:
        """Detect image MIME type from binary data."""
        if image_data.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif image_data.startswith(b'RIFF') and image_data[8:12] == b'WEBP':
            return 'image/webp'
        elif image_data.startswith(b'GIF87a') or image_data.startswith(b'GIF89a'):
            return 'image/gif'
        else:
            return 'image/png'  # Default fallback

    # =========================================================================
    # Message Handling
    # =========================================================================

    async def handle_message(self, message: discord.Message):
        """Process incoming messages and potentially respond."""
        try:
            # Ignore DMs
            if not message.guild:
                return

            message_content = message.content.strip()
            if not message_content and not message.attachments:
                return

            # Get channel info
            category = message.channel.category.name if message.channel.category else "Uncategorized"
            channel_id = message.channel.id
            channel_name = message.channel.name

            # Skip categories we don't process
            if category in self.SKIP_CATEGORIES:
                logger.info(f"Skipping message in category: {category}({message.channel.category.id if message.channel.category else 'N/A'})")
                return
            
            
            # # only reply to this guild for testing
            # if message.guild.id != :
            #     logger.info(f"Skipping message in guild: {message.guild.id} - {message.guild.name}")
            #     return

            # Check if bot was mentioned
            # @ mention = "claudebot"/"claude bot" = definite, "claude" alone = ambiguous
            was_mentioned = self.bot.user in message.mentions
            content_lower = message_content.lower()
            text_mentioned = 'claudebot' in content_lower or 'claude bot' in content_lower 
            any_mention = was_mentioned or text_mentioned

            # Build content for Claude
            claude_content = []

            # Add reply context if this is a reply
            if message.reference:
                try:
                    referenced_message = await message.channel.fetch_message(message.reference.message_id)
                    if referenced_message:
                        ref_content = referenced_message.content
                        has_images = any(
                            att.content_type and att.content_type.startswith('image/')
                            for att in referenced_message.attachments
                        )

                        if ref_content and has_images:
                            context = f"[Replying to {referenced_message.author.display_name}'s message with image(s): {ref_content}]"
                        elif ref_content:
                            context = f"[Replying to {referenced_message.author.display_name}: {ref_content}]"
                        elif has_images:
                            context = f"[Replying to {referenced_message.author.display_name}'s image]"
                        else:
                            context = f"[Replying to {referenced_message.author.display_name}]"

                        claude_content.append({"type": "text", "text": context})

                        # Add referenced images
                        for attachment in referenced_message.attachments:
                            if attachment.content_type and attachment.content_type.startswith('image/'):
                                image_data = await attachment.read()
                                base64_image = base64.b64encode(image_data).decode('utf-8')
                                media_type = self.detect_image_type(image_data)
                                claude_content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": base64_image
                                    }
                                })
                except Exception as e:
                    logger.warning(f"Could not fetch referenced message: {e}")

            # Get conversation history BEFORE adding current message (to avoid duplication)
            history = self.get_conversation_history(message)

            # Add current message to cache for future context
            self.add_message_to_cache(message, any_mention)

            # Build current message with context
            mention_marker = "[MENTIONED] " if any_mention else ""
            current_msg = f"{mention_marker}{message.author.display_name}: {message_content}"

            # Combine history and current message
            if history:
                full_context = f"{history}\n\n[Latest message - decide if you should respond based on context above]\n{current_msg}"
            else:
                full_context = f"[#{channel_name} in {category}]\n{current_msg}"

            claude_content.append({"type": "text", "text": full_context})

            # Add current message images
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    image_data = await attachment.read()
                    base64_image = base64.b64encode(image_data).decode('utf-8')
                    media_type = self.detect_image_type(image_data)
                    claude_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_image
                        }
                    })

            # Check rate limiting (skip if responded too recently, unless directly mentioned)
            last_response = self.last_response_time.get(channel_id)
            if last_response and not any_mention:
                seconds_since = (datetime.now(timezone.utc) - last_response).total_seconds()
                if seconds_since < self.RATE_LIMIT_SECONDS:
                    return  # Rate limited, skip Claude API call

            # Get Claude's response
            response = await self.get_claude_response(claude_content, channel_name, channel_id, current_msg)

            if response:
                logger.info(f"Sending response in #{channel_name}")
                await self.send_long_message(message.channel, response)
                # Update rate limit tracker
                self.last_response_time[channel_id] = datetime.now(timezone.utc)

            print() 

        except discord.errors.HTTPException as e:
            logger.error(f"Discord API error: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            try:
                await message.reply("Encountered an error processing your request.")
            except:
                logger.error("Failed to send error message to user")

    # =========================================================================
    # Claude API Integration
    # =========================================================================

    async def get_claude_response(self, claude_content: list, channel_name: str,
                                   channel_id: int, current_msg: str) -> Optional[str]:
        """
        Send conversation to Claude and get a scored response.
        Returns None if score is below threshold.
        """
        try:
            # System prompt with cache_control for prompt caching
            # Using array format to enable caching
            system_prompt = [
                {
                    "type": "text",
                    "text": """You are a helpful, witty Discord bot in a casual server.

RESPONSE RULES:
- Keep responses to 1-3 sentences MAX. Be brief.
- Aim to be the 5th-6th most active participant in server (your name is "ClaudeBot" in "Recent Conversation:") 
- Use recent conversation and if you notice you haven't chatted in awhile, raise your score accordingly. For example: if you haven't chatted in 10+ messages, increase your score 
- Most conversations don't need your input - only add high value responses
- Only respond if directly mentioned OR you can add genuinely valuable input
- NEVER end with follow-up questions

MENTION FORMAT:
- Messages starting with [MENTIONED] mean the user addressed you (@ClaudeBot or "ClaudeBot") These deserve a response (score 9+)
- Note: "claude" alone is ambiguous (could mean Claude AI service or ClaudeBot) - use context to decide if they're referring to you the discord bot

SCORING (rate your response 0-10):
10 = [MENTIONED] AND asked a clear question you can answer
9 = [MENTIONED] OR celebrate someone's accomplishment (promotion, graduation, new job, etc.)
8 = Can provide high value wile staying the 5th-6th most active participant (check "Recent conversation:" to ensure you're staying active)
5-7 = Might be interesting but doesn't need your input
0-4 = Skip it - normal chat between other users

CATEGORY CONTEXT:
- "Information" = NEVER respond (score 0)
- "tech-and-career" = Usually networking. BUT celebrate accomplishments/good news! (score 8)
- "Text Channels" = May engage if valuable

FORMAT: Write your brief response, then on a new line: SCORE: X""",
                    "cache_control": {"type": "ephemeral"}
                }
            ]

            response = await asyncio.to_thread(
                self.claude_client.messages.create,
                model="claude-sonnet-4-5-20250929",
                max_tokens=self.MAX_RESPONSE_TOKENS,
                temperature=0.7,
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": claude_content
                }]
            )

            response_text = response.content[0].text
            score = self.extract_score(response_text)

            # Log with channel name and ID for debugging
            msg_preview = current_msg[:150]
            logger.info(f"[SCORE: {score}] #{channel_name} ({channel_id}) {msg_preview}..." + "\n\n")

            if score is not None and score < self.SCORE_THRESHOLD:
                return None

            # Remove SCORE line from response
            lines = response_text.strip().split('\n')
            filtered_lines = [line for line in lines if not line.strip().startswith("SCORE:")]
            clean_response = '\n'.join(filtered_lines).strip()

            return clean_response.lower() if clean_response else None

        except Exception as e:
            logger.error(f"Error getting Claude response: {e}")
            return None

    def extract_score(self, response: str) -> Optional[int]:
        """Extract the SCORE: X value from Claude's response."""
        try:
            lines = response.strip().split('\n')
            for line in reversed(lines):
                line = line.strip()
                if line.startswith("SCORE:"):
                    score_str = line.replace("SCORE:", "").strip()
                    return int(score_str)
            return None
        except Exception as e:
            logger.warning(f"Error extracting score: {e}")
            return None

    async def send_long_message(self, channel: discord.TextChannel, content: str):
        """Send a message, splitting if it exceeds Discord's limit."""
        max_length = 2000
        try:
            if len(content) <= max_length:
                await channel.send(content)
            else:
                chunks = [content[i:i+max_length] for i in range(0, len(content), max_length)]
                for chunk in chunks:
                    await channel.send(chunk)
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    # =========================================================================
    # Slash Commands
    # =========================================================================

    def setup_slash_commands(self):
        data_file = 'bot_data.json'

        # Load beer counter
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
                beer_counter = data.get('beer_counter', 0)
                logger.info(f"Loaded beer counter: {beer_counter}")
        except FileNotFoundError:
            beer_counter = 0
            try:
                with open(data_file, 'w') as f:
                    json.dump({'beer_counter': 0}, f)
                logger.info("Created new data file")
            except Exception as e:
                logger.error(f"Failed to create data file: {e}")
        except Exception as e:
            beer_counter = 0
            logger.error(f"Error loading data file: {e}")

        @self.bot.tree.command(name="beer", description="Share a beer with ClaudeBot")
        async def beer_command(interaction: discord.Interaction):
            nonlocal beer_counter
            try:
                beer_counter += 1
                with open(data_file, 'w') as f:
                    json.dump({'beer_counter': beer_counter}, f)
                await interaction.response.send_message(
                    f"Cheers! {beer_counter} beers shared with ClaudeBot"
                )
                logger.info(f"Beer #{beer_counter} by {interaction.user.display_name}")
            except Exception as e:
                beer_counter -= 1
                logger.error(f"Failed to save beer counter: {e}")
                await interaction.response.send_message(
                    "I've had too many for now, thanks though"
                )

        @self.bot.tree.command(name="ping", description="Check bot latency")
        async def ping_command(interaction: discord.Interaction):
            latency = round(self.bot.latency * 1000)  # Convert to ms
            await interaction.response.send_message(f"Pong! {latency}ms")

        @self.bot.tree.command(name="uptime", description="Check bot uptime")
        async def uptime_command(interaction: discord.Interaction):
            if self.start_time:
                delta = datetime.now(timezone.utc) - self.start_time
                days = delta.days
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                await interaction.response.send_message(
                    f"Uptime: {days}d {hours}h {minutes}m {seconds}s"
                )
            else:
                await interaction.response.send_message("Uptime unavailable")

        @self.bot.tree.command(name="cache-stats", description="Show conversation cache statistics")
        @discord.app_commands.describe(channel="Optional: view stats for a specific channel")
        @discord.app_commands.default_permissions(manage_messages=True) # admin
        async def cache_stats_command(
            interaction: discord.Interaction,
            channel: Optional[discord.TextChannel] = None
        ):
            # If specific channel requested
            if channel:
                category = channel.category.name if channel.category else "Uncategorized"
                channel_id = channel.id
                messages = self.conversation_cache.get(category, {}).get(channel_id, [])

                if messages:
                    msg_count = len(messages)
                    tokens = self.get_channel_token_count(category, channel_id)
                    oldest = messages[0]['timestamp'].strftime('%Y-%m-%d %H:%M')
                    newest = messages[-1]['timestamp'].strftime('%Y-%m-%d %H:%M')
                    response = (
                        f"**#{channel.name}** ({category})\n"
                        f"Messages: {msg_count}\n"
                        f"Tokens: ~{tokens:,} / {self.MAX_TOKENS_PER_CHANNEL:,}\n"
                        f"Oldest: {oldest}\n"
                        f"Newest: {newest}"
                    )
                else:
                    response = f"No messages cached for #{channel.name}"
                await interaction.response.send_message(response)
                logger.info(f"Cache stats for #{channel.name} requested by {interaction.user.display_name}")
                return

            # Show all channels summary
            stats = []
            total_messages = 0
            for category, channels in self.conversation_cache.items():
                for ch_id, messages in channels.items():
                    if messages:
                        ch_name = messages[0].get('channel_name', 'unknown')
                        msg_count = len(messages)
                        total_messages += msg_count
                        tokens = self.get_channel_token_count(category, ch_id)
                        stats.append(f"#{ch_name}: {msg_count} msgs (~{tokens:,} tokens)")

            if stats:
                response = f"**Cache Stats:**\n" + "\n".join(stats[:10])
                response += f"\n\n**Total:** {total_messages} messages cached"
            else:
                response = "No messages cached yet."

            await interaction.response.send_message(response)

        @self.bot.tree.command(name="clear-cache", description="Clear conversation cache")
        @discord.app_commands.describe(channel="Optional: clear cache for a specific channel only")
        @discord.app_commands.default_permissions(manage_messages=True) # admin
        async def clear_cache_command(
            interaction: discord.Interaction,
            channel: Optional[discord.TextChannel] = None
        ):
            if channel:
                # Clear specific channel
                category = channel.category.name if channel.category else "Uncategorized"
                channel_id = channel.id

                if category in self.conversation_cache and channel_id in self.conversation_cache[category]:
                    msg_count = len(self.conversation_cache[category][channel_id])
                    del self.conversation_cache[category][channel_id]
                    self.save_cache()
                    await interaction.response.send_message(
                        f"Cleared {msg_count} messages from #{channel.name} cache."
                    )
                    logger.info(f"Cache cleared for #{channel.name} by {interaction.user.display_name}")
                else:
                    await interaction.response.send_message(f"No cache found for #{channel.name}")
            else:
                # Clear all channels
                total_msgs = sum(
                    len(msgs) for channels in self.conversation_cache.values()
                    for msgs in channels.values()
                )
                self.conversation_cache.clear()
                self.conversation_cache = defaultdict(lambda: defaultdict(list))
                self.save_cache()
                await interaction.response.send_message(
                    f"Cleared all cache ({total_msgs} messages across all channels)."
                )
                logger.info(f"All cache cleared by {interaction.user.display_name}")

    # =========================================================================
    # Bot Startup
    # =========================================================================

    async def start(self):
        """Initialize and start the bot."""
        try:
            logger.info("Starting ClaudeBot...")
            self.initialize_clients()
            self.setup_events()
            self.setup_slash_commands()
            await self.bot.start(self.discord_token)
        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise


def main():
    bot = ClaudeBot()
    try:
        asyncio.run(bot.start())
    except Exception as e:
        logger.error(f"Bot crashed: {e}")


if __name__ == "__main__":
    main()
