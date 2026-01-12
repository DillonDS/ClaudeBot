import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { getManageableGuilds } from '@/lib/discord'
import { getOrCreateGuildConfig, updateGuildPrompt } from '@/lib/config.server'
import { DEFAULT_SYSTEM_PROMPT } from '@/lib/config.types'

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
    return NextResponse.json({
      systemPrompt: config.systemPrompt,
      defaultPrompt: DEFAULT_SYSTEM_PROMPT,
      isCustom: config.systemPrompt !== null,
    })
  } catch (error) {
    console.error('Error getting prompt:', error)
    return NextResponse.json({ error: 'Failed to get prompt' }, { status: 500 })
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
    // If systemPrompt is empty string or matches default, set to null
    const promptValue = body.systemPrompt?.trim() || null

    const config = await updateGuildPrompt(
      guildId,
      access.guildName!,
      promptValue,
      session.user!.id!
    )
    return NextResponse.json({
      systemPrompt: config.systemPrompt,
      isCustom: config.systemPrompt !== null,
    })
  } catch (error) {
    console.error('Error updating prompt:', error)
    return NextResponse.json({ error: 'Failed to update prompt' }, { status: 500 })
  }
}
