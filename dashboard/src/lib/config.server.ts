// Server-only file operations - DO NOT import in client components
import { readFile, writeFile, mkdir } from 'fs/promises'
import { existsSync } from 'fs'
import path from 'path'
import {
  GuildConfig,
  GuildSettings,
  GuildCommands,
  BotStats,
  DEFAULT_SETTINGS,
  DEFAULT_COMMANDS,
} from './config.types'

// Re-export types for convenience
export type { GuildConfig, GuildSettings, GuildCommands, BotStats }
export { DEFAULT_SETTINGS, DEFAULT_COMMANDS }

// Get config directory path
function getConfigPath(): string {
  return process.env.CONFIG_PATH || path.join(process.cwd(), '..', 'ClaudeBot', 'guild_configs')
}

// Get stats file path
function getStatsPath(): string {
  return process.env.STATS_PATH || path.join(process.cwd(), '..', 'ClaudeBot', 'bot_stats.json')
}

/**
 * Read guild configuration from JSON file
 */
export async function getGuildConfig(guildId: string): Promise<GuildConfig | null> {
  const configDir = getConfigPath()
  const filePath = path.join(configDir, `${guildId}.json`)

  try {
    const content = await readFile(filePath, 'utf-8')
    return JSON.parse(content)
  } catch {
    // File doesn't exist or is invalid
    return null
  }
}

/**
 * Write guild configuration to JSON file
 */
export async function saveGuildConfig(config: GuildConfig): Promise<void> {
  const configDir = getConfigPath()
  const filePath = path.join(configDir, `${config.guildId}.json`)

  // Ensure directory exists
  if (!existsSync(configDir)) {
    await mkdir(configDir, { recursive: true })
  }

  await writeFile(filePath, JSON.stringify(config, null, 2), 'utf-8')
}

/**
 * Get guild config or create with defaults
 */
export async function getOrCreateGuildConfig(guildId: string, guildName: string): Promise<GuildConfig> {
  const existing = await getGuildConfig(guildId)

  if (existing) {
    return existing
  }

  // Create new config with defaults
  const newConfig: GuildConfig = {
    guildId,
    guildName,
    settings: { ...DEFAULT_SETTINGS },
    commands: { ...DEFAULT_COMMANDS },
    systemPrompt: null,
    updatedAt: new Date().toISOString(),
    updatedBy: 'system',
  }

  await saveGuildConfig(newConfig)
  return newConfig
}

/**
 * Update specific settings for a guild
 */
export async function updateGuildSettings(
  guildId: string,
  guildName: string,
  settings: Partial<GuildSettings>,
  updatedBy: string
): Promise<GuildConfig> {
  const config = await getOrCreateGuildConfig(guildId, guildName)

  config.settings = { ...config.settings, ...settings }
  config.updatedAt = new Date().toISOString()
  config.updatedBy = updatedBy

  await saveGuildConfig(config)
  return config
}

/**
 * Update command toggles for a guild
 */
export async function updateGuildCommands(
  guildId: string,
  guildName: string,
  commands: Partial<GuildCommands>,
  updatedBy: string
): Promise<GuildConfig> {
  const config = await getOrCreateGuildConfig(guildId, guildName)

  config.commands = { ...config.commands, ...commands }
  config.updatedAt = new Date().toISOString()
  config.updatedBy = updatedBy

  await saveGuildConfig(config)
  return config
}

/**
 * Update system prompt for a guild
 */
export async function updateGuildPrompt(
  guildId: string,
  guildName: string,
  systemPrompt: string | null,
  updatedBy: string
): Promise<GuildConfig> {
  const config = await getOrCreateGuildConfig(guildId, guildName)

  config.systemPrompt = systemPrompt
  config.updatedAt = new Date().toISOString()
  config.updatedBy = updatedBy

  await saveGuildConfig(config)
  return config
}

/**
 * Read bot stats from JSON file
 */
export async function getBotStats(): Promise<BotStats | null> {
  const statsPath = getStatsPath()

  try {
    const content = await readFile(statsPath, 'utf-8')
    return JSON.parse(content)
  } catch {
    return null
  }
}

/**
 * Get stats for a specific guild
 */
export async function getGuildStats(guildId: string): Promise<{
  messagesCached: number
  tokensUsed: number
  lastActivity: string
  botUptime: string
  botLatency: number
} | null> {
  const stats = await getBotStats()

  if (!stats) {
    return null
  }

  const guildStats = stats.guilds?.[guildId]

  return {
    messagesCached: guildStats?.messagesCached ?? 0,
    tokensUsed: guildStats?.tokensUsed ?? 0,
    lastActivity: guildStats?.lastActivity ?? 'Never',
    botUptime: stats.uptime ?? 'Unknown',
    botLatency: stats.latency ?? 0,
  }
}
