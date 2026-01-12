import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { getManageableGuilds } from '@/lib/discord'
import { getOrCreateGuildConfig, updateGuildCommands } from '@/lib/config.server'

interface RouteParams {
  params: Promise<{ guildId: string }>
}

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
    return NextResponse.json({ commands: config.commands })
  } catch (error) {
    console.error('Error getting commands:', error)
    return NextResponse.json({ error: 'Failed to get commands' }, { status: 500 })
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
    const config = await updateGuildCommands(
      guildId,
      access.guildName!,
      body.commands,
      session.user!.id!
    )
    return NextResponse.json({ commands: config.commands })
  } catch (error) {
    console.error('Error updating commands:', error)
    return NextResponse.json({ error: 'Failed to update commands' }, { status: 500 })
  }
}
