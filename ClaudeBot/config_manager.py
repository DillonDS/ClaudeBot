"""
Configuration Manager for ClaudeBot
Handles per-guild settings stored in JSON files and stats publishing.
"""

import os
import json
import logging
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages per-guild configuration from JSON files."""

    # Default configuration values (fallback when no guild config exists)
    DEFAULTS = {
        "maxTokensPerChannel": 150000,
        "messageExpiryDays": 30,
        "charsPerTokenEstimate": 4,
        "maxResponseTokens": 300,
        "scoreThreshold": 8,
        "rateLimitSeconds": 2,
        "temperature": 0.7,
        "model": "claude-sonnet-4-5-20250929",
        "skipCategories": ["Information"],
    }

    DEFAULT_COMMANDS = {
        "beer": True,
        "ping": True,
        "uptime": True,
        "cacheStats": True,
        "clearCache": True,
    }

    DEFAULT_SYSTEM_PROMPT = """You are a helpful, witty Discord bot in a casual server.

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

FORMAT: Write your brief response, then on a new line: SCORE: X"""

    def __init__(self, config_dir: Optional[str] = None, stats_file: Optional[str] = None):
        """
        Initialize the config manager.

        Args:
            config_dir: Directory for guild config JSON files. Defaults to ./guild_configs
            stats_file: Path to bot stats JSON file. Defaults to ./bot_stats.json
        """
        # Get the directory where this script is located
        base_dir = Path(__file__).parent

        self.config_dir = Path(config_dir) if config_dir else base_dir / "guild_configs"
        self.stats_file = Path(stats_file) if stats_file else base_dir / "bot_stats.json"

        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of loaded configs
        self._cache: dict[str, dict] = {}

        logger.info(f"ConfigManager initialized. Config dir: {self.config_dir}")

    def _get_config_path(self, guild_id: str) -> Path:
        """Get the path to a guild's config file."""
        return self.config_dir / f"{guild_id}.json"

    def _load_config(self, guild_id: str) -> Optional[dict]:
        """Load config from file, return None if not found."""
        config_path = self._get_config_path(guild_id)

        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config for guild {guild_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading config for guild {guild_id}: {e}")
            return None

    def get_guild_config(self, guild_id: str) -> dict:
        """
        Get configuration for a guild.
        Returns defaults if no config exists.
        """
        # Check cache first
        if guild_id in self._cache:
            return self._cache[guild_id]

        # Load from file
        config = self._load_config(guild_id)

        if config and "settings" in config:
            self._cache[guild_id] = config["settings"]
            return config["settings"]

        # Return defaults if no config
        return self.DEFAULTS.copy()

    def get_setting(self, guild_id: str, key: str, default=None):
        """Get a specific setting for a guild."""
        config = self.get_guild_config(guild_id)
        return config.get(key, self.DEFAULTS.get(key, default))

    def get_system_prompt(self, guild_id: str) -> str:
        """Get the system prompt for a guild (custom or default)."""
        config = self._load_config(guild_id)

        if config and config.get("systemPrompt"):
            return config["systemPrompt"]

        return self.DEFAULT_SYSTEM_PROMPT

    def is_command_enabled(self, guild_id: str, command: str) -> bool:
        """Check if a command is enabled for a guild."""
        config = self._load_config(guild_id)

        if config and "commands" in config:
            return config["commands"].get(command, True)

        return self.DEFAULT_COMMANDS.get(command, True)

    def get_skip_categories(self, guild_id: str) -> set:
        """Get the set of categories to skip for a guild."""
        config = self.get_guild_config(guild_id)
        categories = config.get("skipCategories", self.DEFAULTS["skipCategories"])
        return set(categories)

    def invalidate_cache(self, guild_id: str):
        """Invalidate cached config for a guild (call when config might have changed)."""
        self._cache.pop(guild_id, None)
        logger.info(f"Invalidated config cache for guild {guild_id}")

    def invalidate_all_caches(self):
        """Invalidate all cached configs."""
        self._cache.clear()
        logger.info("Invalidated all config caches")

    # =========================================================================
    # Stats Publishing
    # =========================================================================

    def write_stats(self, bot, conversation_cache: dict):
        """
        Write bot stats to JSON file for dashboard consumption.

        Args:
            bot: The discord bot instance
            conversation_cache: The conversation cache dict
        """
        try:
            # Calculate uptime
            uptime_str = "Unknown"
            if hasattr(bot, 'start_time') and bot.start_time:
                delta = datetime.now(timezone.utc) - bot.start_time
                days = delta.days
                hours, remainder = divmod(delta.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                uptime_str = f"{days}d {hours}h {minutes}m"

            # Calculate per-guild stats
            guild_stats = {}
            for category, channels in conversation_cache.items():
                for channel_id, messages in channels.items():
                    if not messages:
                        continue

                    # Try to get guild_id from the first message's channel
                    # Since we don't have direct access, we'll aggregate by channel
                    # The dashboard will need to map channels to guilds

                    # For now, estimate tokens
                    total_tokens = sum(
                        len(f"{msg['user']}: {msg['content']}") // 4
                        for msg in messages
                    )

                    # Get the most recent activity
                    last_activity = max(
                        (msg['timestamp'] for msg in messages),
                        default=None
                    )

            # Build stats object
            stats = {
                "uptime": uptime_str,
                "latency": round(bot.latency * 1000) if hasattr(bot, 'latency') else 0,
                "totalGuilds": len(bot.guilds) if hasattr(bot, 'guilds') else 0,
                "guilds": {},
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }

            # Calculate per-guild stats from conversation cache
            # Group channels by guild (we need to track this in the cache)
            total_messages = 0
            total_tokens = 0

            for category, channels in conversation_cache.items():
                for channel_id, messages in channels.items():
                    if messages:
                        total_messages += len(messages)
                        total_tokens += sum(
                            len(f"{msg['user']}: {msg['content']}") // 4
                            for msg in messages
                        )

            # For now, write aggregate stats
            # In a future update, we can track guild_id per channel
            stats["totalMessages"] = total_messages
            stats["totalTokens"] = total_tokens

            # Write to file
            with open(self.stats_file, 'w') as f:
                json.dump(stats, f, indent=2)

            logger.debug(f"Wrote stats to {self.stats_file}")

        except Exception as e:
            logger.error(f"Error writing stats: {e}")

    def write_guild_stats(self, guild_id: str, messages_cached: int, tokens_used: int):
        """
        Update stats for a specific guild.
        """
        try:
            # Load existing stats
            stats = {}
            if self.stats_file.exists():
                with open(self.stats_file, 'r') as f:
                    stats = json.load(f)

            # Ensure guilds dict exists
            if "guilds" not in stats:
                stats["guilds"] = {}

            # Update guild stats
            stats["guilds"][guild_id] = {
                "messagesCached": messages_cached,
                "tokensUsed": tokens_used,
                "lastActivity": datetime.now(timezone.utc).isoformat(),
            }

            # Write back
            with open(self.stats_file, 'w') as f:
                json.dump(stats, f, indent=2)

        except Exception as e:
            logger.error(f"Error writing guild stats: {e}")
