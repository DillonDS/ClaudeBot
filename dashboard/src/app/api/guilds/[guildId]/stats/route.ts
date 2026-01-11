import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { getManageableGuilds } from '@/lib/discord'
import { getGuildStats } from '@/lib/config.server'

interface RouteParams {
  params: Promise<{ guildId: string }>
}

async function verifyAccess(guildId: string, accessToken: string): Promise<boolean> {
  const guilds = await getManageableGuilds(accessToken)
  const guild = guilds.find((g) => g.id === guildId)
  return guild?.hasBot ?? false
}

export async function GET(request: Request, { params }: RouteParams) {
  const session = await auth()
  const { guildId } = await params

  if (!session?.accessToken) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const hasAccess = await verifyAccess(guildId, session.accessToken)
  if (!hasAccess) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  try {
    const stats = await getGuildStats(guildId)

    if (!stats) {
      // Return default stats if bot hasn't written any yet
      return NextResponse.json({
        messagesCached: 0,
        tokensUsed: 0,
        lastActivity: 'Never',
        botUptime: 'Unknown',
        botLatency: 0,
      })
    }

    return NextResponse.json(stats)
  } catch (error) {
    console.error('Error getting stats:', error)
    return NextResponse.json({ error: 'Failed to get stats' }, { status: 500 })
  }
}
