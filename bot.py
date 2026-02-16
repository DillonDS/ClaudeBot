import os
import json
import asyncio
import logging
from typing import Optional
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
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
    MAX_TOKENS_PER_CHANNEL = 10000          # 10k token limit per channel (storage)
    MESSAGE_EXPIRY_DAYS = 12                # Remove messages older than 12 days
    CHARS_PER_TOKEN_ESTIMATE = 4            # Rough estimate for token counting
    MAX_RESPONSE_TOKENS = 300               # Keep responses brief
    SCORE_THRESHOLD = 8                     # Only respond if score >= 8
    CACHE_FILE = 'conversation_cache.json'  # Persistent cache file

    # Batching and context limits
    BATCH_WINDOW_SECONDS = 5                # Collect messages for 5 seconds before processing
    HAIKU_CONTEXT_TOKENS = 2000             # ~2k tokens to Haiku for scoring
    SONNET_CONTEXT_TOKENS = 4500            # ~4.5k tokens to Sonnet for response

    # Listen-only: cache messages for context, but only respond if mentioned
    LISTEN_ONLY_CATEGORIES = {"Information"}
    LISTEN_ONLY_CHANNELS = {"readings", "github-profiles", "linkedin"}

    # Timezone for conversation history dividers
    DISPLAY_TIMEZONE = ZoneInfo("America/New_York")

    def __init__(self):
        self.discord_token: Optional[str] = None
        self.claude_api_key: Optional[str] = None
        self.claude_client: Optional[anthropic.Anthropic] = None
        self.bot: Optional[commands.Bot] = None
        self.start_time: Optional[datetime] = None

        # Conversation cache: category_name -> channel_id -> list of messages
        self.conversation_cache = defaultdict(lambda: defaultdict(list))

        # Batching: collect messages before processing
        self.pending_messages: dict[int, list[dict]] = {}  # channel_id -> list of message data
        self.batch_tasks: dict[int, asyncio.Task] = {}     # channel_id -> pending batch task

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
            secret_name = os.getenv("AWS_SECRET_NAME")
            if not secret_name:
                raise ValueError("AWS_SECRET_NAME environment variable not set")
            client = boto3.client('secretsmanager', region_name=region)
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
        """Save conversation cache to file using atomic write to prevent corruption."""
        temp_file = self.CACHE_FILE + '.tmp'
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

            # Write to temp file first - if crash happens here, the original cache file is still intact
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)

            # replaces cache file only after temp file is fully written
            os.replace(temp_file, self.CACHE_FILE)

            total_msgs = sum(
                len(msgs) for channels in self.conversation_cache.values()
                for msgs in channels.values()
            )
            logger.info(f"Saved {total_msgs} messages to cache file")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
            # Clean up temp file if it exists from a failed write
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    logger.warning(f"Could not clean up temp file: {temp_file}")

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
                messages.pop(0)  # Remove oldest message
                logger.info("Removed old message to stay under token limit")
            else:
                break

    def add_message_to_cache(self, message: discord.Message,
                             reply_author: str = None, reply_content: str = None,
                             reply_has_images: bool = False):
        """Add a message to the conversation cache (including listen-only channels for context)."""
        category = message.channel.category.name if message.channel.category else "Uncategorized"
        channel_id = message.channel.id
        channel_name = message.channel.name
        
        # Truncate reply content if too long
        if reply_content and len(reply_content) > 50:
            reply_content = reply_content[:50] + "..."
        
        # Add image marker if replying to an image
        if reply_has_images and reply_content:
            reply_content += " [image]"
        elif reply_has_images:
            reply_content = "[image]"

        # Build content with image marker if message has images
        content = message.content.strip()
        image_count = sum(
            1 for att in message.attachments
            if att.content_type and att.content_type.startswith('image/')
        )
        if image_count:
            marker = f" [shared {image_count} image{'s' if image_count > 1 else ''}]"
            content += marker

        # Create message entry
        msg_entry = {
            "user": message.author.display_name,
            "content": content,
            "timestamp": datetime.now(timezone.utc),
            "channel_name": channel_name,
            "reply_author": reply_author,
            "reply_content": reply_content
        }

        # Add to cache
        self.conversation_cache[category][channel_id].append(msg_entry)

        # Remove old messages and enforce token limit
        self.cleanup_old_messages(category, channel_id)
        self.enforce_token_limit(category, channel_id)

    def add_bot_response_to_cache(self, message: discord.Message):
        """Add ClaudeBot's own response to cache for context continuity."""
        if not message.channel.category:
            category = "Uncategorized"
        else:
            category = message.channel.category.name

        channel_name = message.channel.name
        channel_id = message.channel.id

        # Use "ClaudeBot" in conversation history
        msg_entry = {
            "user": "ClaudeBot",
            "content": message.content.strip(),
            "timestamp": datetime.now(timezone.utc),
            "channel_name": channel_name,
            "reply_author": None,
            "reply_content": None
        }

        self.conversation_cache[category][channel_id].append(msg_entry)
        self.cleanup_old_messages(category, channel_id)
        self.enforce_token_limit(category, channel_id)

    def format_hour(self, dt: datetime) -> str:
        """Format a datetime's hour as '2pm', '12am', etc."""
        hour = dt.hour
        if hour == 0:
            return "12am"
        elif hour < 12:
            return f"{hour}am"
        elif hour == 12:
            return "12pm"
        else:
            return f"{hour - 12}pm"

    def get_conversation_history(self, message: discord.Message) -> str:
        """Build formatted conversation history for Claude."""
        category = message.channel.category.name if message.channel.category else "Uncategorized"
        channel_id = message.channel.id

        messages = self.conversation_cache[category][channel_id]

        if not messages:
            return ""

        # Format conversation history with hourly dividers
        lines = []
        current_hour_key = None

        for msg in messages:
            # Insert hourly divider when the hour changes
            msg_time = msg['timestamp'].astimezone(self.DISPLAY_TIMEZONE)
            hour_key = (msg_time.date(), msg_time.hour)
            if hour_key != current_hour_key:
                current_hour_key = hour_key
                time_str = self.format_hour(msg_time)
                lines.append(f"--- {msg_time.strftime('%b')} {msg_time.day}, {time_str} ET ---")

            reply_author = msg.get('reply_author')
            reply_content = msg.get('reply_content')

            if reply_author:
                if reply_content:
                    lines.append(f'{msg["user"]} [replying to {reply_author}: "{reply_content}"]: {msg["content"]}')
                else:
                    lines.append(f'{msg["user"]} [replying to {reply_author}]: {msg["content"]}')
            else:
                lines.append(f"{msg['user']}: {msg['content']}")

        return "\n".join(lines)

    def get_trimmed_history(self, message: discord.Message, max_tokens: int) -> str:
        """Get conversation history trimmed to max_tokens (keeps most recent)."""
        history = self.get_conversation_history(message)
        # Trim from the start (oldest) to fit within limit, keeping newest
        while self.estimate_tokens(history) > max_tokens and '\n' in history:
            history = history.split('\n', 1)[1]
        return history

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

                await self.bot.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.watching, name="chat")
                )
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

    # =========================================================================
    # Image Detection
    # =========================================================================

    def detect_image_type(self, image_data: bytes) -> str:
        """Detect image MIME type from binary data."""
        if image_data.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        elif image_data.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif len(image_data) >= 12 and image_data.startswith(b'RIFF') and image_data[8:12] == b'WEBP':
            return 'image/webp'
        elif image_data.startswith(b'GIF87a') or image_data.startswith(b'GIF89a'):
            return 'image/gif'
        else:
            return 'image/png'  # Default fallback

    # =========================================================================
    # Message Handling
    # =========================================================================

    async def handle_message(self, message: discord.Message):
        """Add message to batch for processing."""
        try:
            # Ignore DMs
            if not message.guild:
                return

            message_content = message.content.strip()
            if not message_content and not message.attachments:
                return

            channel_id = message.channel.id

            # # only reply to this guild for testing
            # if message.guild.id != GUILD:
            #     logger.info(f"Skipping message in guild: {message.guild.id} - {message.guild.name}")
            #     return

            # Check if bot was mentioned
            was_mentioned = self.bot.user in message.mentions
            content_lower = message_content.lower()
            text_mentioned = 'claudebot' in content_lower or 'claude bot' in content_lower
            any_mention = was_mentioned or text_mentioned

            # Build message data for batch
            msg_data = {
                "user": message.author.display_name,
                "content": message_content,
                "message_obj": message,
                "mentioned": any_mention,
                "reply_author": None,
                "reply_content": None,
                "reply_has_images": False,
                "reply_images": [],
                "images": []
            }

            # Capture reply context if this is a reply
            if message.reference:
                try:
                    referenced_message = await message.channel.fetch_message(message.reference.message_id)
                    if referenced_message:
                        msg_data["reply_author"] = referenced_message.author.display_name
                        msg_data["reply_content"] = referenced_message.content or None
                        msg_data["reply_has_images"] = any(
                            att.content_type and att.content_type.startswith('image/')
                            for att in referenced_message.attachments
                        )

                        # Capture referenced images
                        for attachment in referenced_message.attachments:
                            if attachment.content_type and attachment.content_type.startswith('image/'):
                                image_data = await attachment.read()
                                base64_image = base64.b64encode(image_data).decode('utf-8')
                                media_type = self.detect_image_type(image_data)
                                msg_data["reply_images"].append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": base64_image
                                    }
                                })
                except Exception as e:
                    logger.warning(f"Could not fetch referenced message: {e}")

            # Capture current message images
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    image_data = await attachment.read()
                    base64_image = base64.b64encode(image_data).decode('utf-8')
                    media_type = self.detect_image_type(image_data)
                    msg_data["images"].append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64_image
                        }
                    })

            # Add to pending batch
            if channel_id not in self.pending_messages:
                self.pending_messages[channel_id] = []
            self.pending_messages[channel_id].append(msg_data)

            # Start batch timer only if one isn't already running (5-second window)
            if channel_id not in self.batch_tasks:
                self.batch_tasks[channel_id] = asyncio.create_task(
                    self.process_batch_after_delay(channel_id)
                )

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def process_batch_after_delay(self, channel_id: int):
        """Wait for batch window, then process accumulated messages."""
        try:
            await asyncio.sleep(self.BATCH_WINDOW_SECONDS)
            await self.process_batch(channel_id)
        except Exception as e:
            logger.error(f"Error in batch delay: {e}")

    async def process_batch(self, channel_id: int):
        """Process all pending messages for a channel."""
        if channel_id not in self.pending_messages:
            return

        batch = self.pending_messages.pop(channel_id)
        if channel_id in self.batch_tasks:
            del self.batch_tasks[channel_id]

        if not batch:
            return

        try:
            # Get channel info from first message
            first_msg = batch[0]["message_obj"]
            channel = first_msg.channel
            category = channel.category.name if channel.category else "Uncategorized"
            channel_name = channel.name

            # Check if this is a listen-only channel
            is_listen_only = (
                category in self.LISTEN_ONLY_CATEGORIES or
                channel_name in self.LISTEN_ONLY_CHANNELS
            )
            any_mentioned = any(msg_data["mentioned"] for msg_data in batch)

            # Build content array maintaining proper order: text -> images for each message
            latest_content = []

            for msg_data in batch:
                # Build the message line (with reply context if replying)
                mention_marker = "[MENTIONED] " if msg_data["mentioned"] else ""

                if msg_data["reply_author"]:
                    # Build reply indicator: [replying to Alice: "content" + image]
                    reply_parts = []
                    if msg_data["reply_content"]:
                        # Truncate reply content
                        reply_text = msg_data["reply_content"]
                        if len(reply_text) > 25:
                            reply_text = reply_text[:25] + "..."
                        reply_parts.append(f'"{reply_text}"')
                    if msg_data["reply_has_images"]:
                        reply_parts.append("image")

                    reply_info = " + ".join(reply_parts) if reply_parts else "message"
                    msg_text = f'{mention_marker}{msg_data["user"]} [replying to {msg_data["reply_author"]}: {reply_info}]: {msg_data["content"]}'
                else:
                    msg_text = f'{mention_marker}{msg_data["user"]}: {msg_data["content"]}'

                latest_content.append({"type": "text", "text": msg_text})

                # Add referenced images with label (if replying to an image)
                if msg_data["reply_images"]:
                    latest_content.append({"type": "text", "text": f"{msg_data['reply_author']}'s referenced image:"})
                    latest_content.extend(msg_data["reply_images"])

                # Add the message's own images with label
                if msg_data["images"]:
                    latest_content.append({"type": "text", "text": f"{msg_data['user']}'s image:"})
                    latest_content.extend(msg_data["images"])

            # Get trimmed history before adding batch to cache 
            haiku_history = self.get_trimmed_history(first_msg, self.HAIKU_CONTEXT_TOKENS)
            sonnet_history = self.get_trimmed_history(first_msg, self.SONNET_CONTEXT_TOKENS)

            # Add all batch messages to cache (for future context)
            for msg_data in batch:
                self.add_message_to_cache(
                    msg_data["message_obj"],
                    msg_data.get("reply_author"),
                    msg_data.get("reply_content"),
                    msg_data.get("reply_has_images", False)
                )

            # Save cache after each batch
            self.save_cache()

            # Handle listen-only channels: only respond if mentioned
            if is_listen_only and not any_mentioned:
                logger.info(f"Listen-only #{channel_name} - no mention, skipping API calls")
                return

            # If mentioned anywhere, skip Haiku and go straight to Sonnet
            if any_mentioned:
                logger.info(f"Mentioned in #{channel_name} - sending to Sonnet to respond directly")
                response = await self.generate_response(
                    sonnet_history, latest_content, channel_name, category)
                if response:
                    await self.send_long_message(channel, response)
                return

            # Regular channel, no mention: Score with Haiku
            score = await self.score_message(haiku_history, latest_content, channel_name, category)

            preview = " | ".join(m["content"][:15] for m in batch)
            logger.info(f"[SCORE: {score}] #{channel_name} - {len(batch)} msg(s) - \"{preview}\"")

            if score is None or score < self.SCORE_THRESHOLD:
                logger.info(f"Skipping response in #{channel_name} - Score: {score}")
                return

            response = await self.generate_response(
                sonnet_history, latest_content, channel_name, category)

            if response:
                logger.info(f"Sending response in #{channel_name}")
                await self.send_long_message(channel, response)

        except discord.errors.HTTPException as e:
            logger.error(f"Discord API error: {e}")
        except Exception as e:
            logger.error(f"Error processing batch: {e}")

    # =========================================================================
    # Claude API Integration
    # =========================================================================

    async def score_message(self, haiku_history: str, latest_content: list,
                            channel_name: str, category: str) -> Optional[int]:
        """Score whether to respond using Haiku (cheap and fast)."""
        try:
            # Build content: header, history, then new messages with their images
            content = [
                {"type": "text", "text": f"""[#{channel_name} in {category}]
Previous conversation:
{haiku_history}

[New messages]
"""}
            ]

            # Add new messages with their images in proper order
            content.extend(latest_content)

            # Add scoring instructions at the end
            content.append({"type": "text", "text": """
You are a helpful, witty Discord bot in a casual server. - decide if ClaudeBot should respond to the new messages based on the following criteria:
- Take Previous conversation and new messages into account
- Only respond if you can add a valuable input OR be witty (be selective, not all messages need a response)
- If someone shares good news, celebrate with them!

- 10: Directly mentioned ([MENTIONED]) - always respond
- 9: Someone sharing big news worth celebrating (promotion, graduation, new job)
- 8-9: Opportunity to be witty/funny, OR a question requiring expertise others maybe/likely don't have
- 5-7: Simple questions anyone could answer, mild interest but not needed
- 0-4: Normal chat, skip

Note: If someone said "Claude" it doesn't mean they're talking to you. Check context to determine if they're talking about ClaudeBot or Claude the AI service.

Frequency check: If ClaudeBot appears in the last 10 messages of "Previous conversation", subtract 2 from your score.

Just output: SCORE: X"""})

            response = await asyncio.to_thread(
                self.claude_client.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=20,
                messages=[{"role": "user", "content": content}]
            )

            return self.extract_score(response.content[0].text)

        except Exception as e:
            logger.error(f"Error scoring message: {e}")
            return None

    async def generate_response(self, sonnet_history: str, latest_content: list,
                                channel_name: str, category: str) -> Optional[str]:
        """Generate response using Sonnet (only called when score >= threshold)."""
        try:
            # Build content: header, history, then new messages with their images
            content = [
                {"type": "text", "text": f"""[#{channel_name} in {category}]
Recent conversation:
{sonnet_history}

[New messages]
"""}
            ]

            # Add new messages with their images in proper order
            content.extend(latest_content)

            system_prompt = """you're claudebot, a chill member of this discord server. you run on claude sonnet 4.5.

vibes:
- keep it to 1-3 sentences max
- be helpful when someone needs it, be funny/witty when there's an opening
- match the energy of the chat
- celebrate wins, roast bad takes, drop knowledge when relevant
- never end with a question
- type in all lowercase"""

            response = await asyncio.to_thread(
                self.claude_client.messages.create,
                model="claude-sonnet-4-5-20250929",
                max_tokens=self.MAX_RESPONSE_TOKENS,
                temperature=0.7,
                system=system_prompt,
                messages=[{"role": "user", "content": content}]
            )

            return response.content[0].text.strip()

        except Exception as e:
            logger.error(f"Error generating response: {e}")
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
        content = content.lower()
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
                if len(stats) > 10:
                    response += f"\n*(showing 10 of {len(stats)} channels)*"
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
