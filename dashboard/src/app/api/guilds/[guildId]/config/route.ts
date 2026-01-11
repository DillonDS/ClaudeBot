import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { getManageableGuilds } from '@/lib/discord'
import { getOrCreateGuildConfig, updateGuildSettings } from '@/lib/config.server'

interface RouteParams {
  params: Promise<{ guildId: string }>
}

// Verify user can manage this guild
async function verifyAccess(guildId: string, accessToken: string): Promise<{ authorized: boolean; guildName?: string }> {
  const guilds = await getManageableGuilds(accessToken)
  const guild = guilds.find((g) => g.id === guildId)

  if (!guild || !guild.hasBot) {
    return { authorized: false }
  }

  return { authorized: true, guildName: guild.name }
}

export async function GET(request: Request, { params }: RouteParams) {
  const session = await auth()
  const { guildId } = await params

  if (!session?.accessToken) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const access = await verifyAccess(guildId, session.accessToken)
  if (!access.authorized) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  try {
    const config = await getOrCreateGuildConfig(guildId, access.guildName!)
    return NextResponse.json(config)
  } catch (error) {
    console.error('Error getting guild config:', error)
    return NextResponse.json({ error: 'Failed to get config' }, { status: 500 })
  }
}

export async function PUT(request: Request, { params }: RouteParams) {
  const session = await auth()
  const { guildId } = await params

  if (!session?.accessToken) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const access = await verifyAccess(guildId, session.accessToken)
  if (!access.authorized) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }

  try {
    const body = await request.json()
    const config = await updateGuildSettings(
      guildId,
      access.guildName!,
      body.settings,
      session.user.id
    )
    return NextResponse.json(config)
  } catch (error) {
    console.error('Error updating guild config:', error)
    return NextResponse.json({ error: 'Failed to update config' }, { status: 500 })
  }
}
