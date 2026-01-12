// Discord permission flags
const MANAGE_GUILD = BigInt(0x20)
const ADMINISTRATOR = BigInt(0x8)

export interface DiscordGuild {
  id: string
  name: string
  icon: string | null
  owner: boolean
  permissions: string
}

export interface ManageableGuild {
  id: string
  name: string
  icon: string | null
  hasBot: boolean
}

/**
 * Fetch guilds the user is a member of from Discord API
 */
export async function getUserGuilds(accessToken: string): Promise<DiscordGuild[]> {
  const response = await fetch('https://discord.com/api/v10/users/@me/guilds', {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    next: { revalidate: 60 }, // Cache for 60 seconds
  })

  if (!response.ok) {
    throw new Error(`Failed to fetch guilds: ${response.status}`)
  }

  return response.json()
}

/**
 * Check if user has permission to manage a guild
 */
export function canManageGuild(guild: DiscordGuild): boolean {
  const permissions = BigInt(guild.permissions)
  return (
    guild.owner ||
    (permissions & ADMINISTRATOR) === ADMINISTRATOR ||
    (permissions & MANAGE_GUILD) === MANAGE_GUILD
  )
}

/**
 * Fetch guilds the bot is a member of
 */
export async function getBotGuilds(): Promise<string[]> {
  const botToken = process.env.DISCORD_BOT_TOKEN

  if (!botToken) {
    console.error('DISCORD_BOT_TOKEN not set')
    return []
  }

  try {
    const response = await fetch('https://discord.com/api/v10/users/@me/guilds', {
      headers: {
        Authorization: `Bot ${botToken}`,
      },
      next: { revalidate: 60 },
    })

    if (!response.ok) {
      console.error(`Failed to fetch bot guilds: ${response.status}`)
      return []
    }

    const guilds = await response.json()
    return guilds.map((g: { id: string }) => g.id)
  } catch (error) {
    console.error('Error fetching bot guilds:', error)
    return []
  }
}

/**
 * Get guilds the user can manage that also have the bot
 */
export async function getManageableGuilds(accessToken: string): Promise<ManageableGuild[]> {
  const [userGuilds, botGuildIds] = await Promise.all([
    getUserGuilds(accessToken),
    getBotGuilds(),
  ])

  const botGuildSet = new Set(botGuildIds)

  return userGuilds
    .filter((guild) => canManageGuild(guild))
    .map((guild) => ({
      id: guild.id,
      name: guild.name,
      icon: guild.icon,
      hasBot: botGuildSet.has(guild.id),
    }))
    .sort((a, b) => {
      // Sort: guilds with bot first, then alphabetically
      if (a.hasBot && !b.hasBot) return -1
      if (!a.hasBot && b.hasBot) return 1
      return a.name.localeCompare(b.name)
    })
}

/**
 * Get Discord CDN URL for guild icon
 */
export function getGuildIconUrl(guildId: string, iconHash: string | null, size: number = 64): string {
  if (!iconHash) {
    // Default Discord icon
    return `https://cdn.discordapp.com/embed/avatars/${Number(guildId) % 5}.png`
  }
  const extension = iconHash.startsWith('a_') ? 'gif' : 'png'
  return `https://cdn.discordapp.com/icons/${guildId}/${iconHash}.${extension}?size=${size}`
}
