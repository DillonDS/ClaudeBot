// Types and constants - safe for client-side use

export const DEFAULT_SETTINGS = {
  maxTokensPerChannel: 150000,
  messageExpiryDays: 30,
  charsPerTokenEstimate: 4,
  maxResponseTokens: 300,
  scoreThreshold: 8,
  rateLimitSeconds: 2,
  temperature: 0.7,
  model: 'claude-sonnet-4-5-20250929',
  skipCategories: ['Information'],
}

export const DEFAULT_COMMANDS = {
  beer: true,
  ping: true,
  uptime: true,
  cacheStats: true,
  clearCache: true,
}

export const DEFAULT_SYSTEM_PROMPT = `You are a helpful, witty Discord bot in a casual server.

RESPONSE RULES:
- Keep responses to 1-3 sentences MAX. Be brief.
- Aim to be the 5th-6th most active participant in server (your name is "ClaudeBot" in "Recent Conversation:")
- Use recent conversation and if you notice you haven't chatted in awhile, raise your score accordingly.
- Most conversations don't need your input - only add high value responses
- Only respond if directly mentioned OR you can add genuinely valuable input
- NEVER end with follow-up questions

MENTION FORMAT:
- Messages starting with [MENTIONED] mean the user addressed you (@ClaudeBot or "ClaudeBot") These deserve a response (score 9+)
- Note: "claude" alone is ambiguous (could mean Claude AI service or ClaudeBot) - use context to decide

SCORING (rate your response 0-10):
10 = [MENTIONED] AND asked a clear question you can answer
9 = [MENTIONED] OR celebrate someone's accomplishment
8 = Can provide high value while staying the 5th-6th most active participant
5-7 = Might be interesting but doesn't need your input
0-4 = Skip it - normal chat between other users

CATEGORY CONTEXT:
- "Information" = NEVER respond (score 0)
- "tech-and-career" = Usually networking. BUT celebrate accomplishments! (score 8)
- "Text Channels" = May engage if valuable

FORMAT: Write your brief response, then on a new line: SCORE: X`

export interface GuildSettings {
  maxTokensPerChannel: number
  messageExpiryDays: number
  charsPerTokenEstimate: number
  maxResponseTokens: number
  scoreThreshold: number
  rateLimitSeconds: number
  temperature: number
  model: string
  skipCategories: string[]
}

export interface GuildCommands {
  beer: boolean
  ping: boolean
  uptime: boolean
  cacheStats: boolean
  clearCache: boolean
}

export interface GuildConfig {
  guildId: string
  guildName: string
  settings: GuildSettings
  commands: GuildCommands
  systemPrompt: string | null
  updatedAt: string
  updatedBy: string
}

export interface BotStats {
  uptime: string
  latency: number
  totalGuilds: number
  guilds: {
    [guildId: string]: {
      messagesCached: number
      tokensUsed: number
      lastActivity: string
    }
  }
  updatedAt: string
}
