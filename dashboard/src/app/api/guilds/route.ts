import { NextResponse } from 'next/server'
import { auth } from '@/lib/auth'
import { getManageableGuilds } from '@/lib/discord'

export async function GET() {
  const session = await auth()

  if (!session?.accessToken) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  try {
    const guilds = await getManageableGuilds(session.accessToken)
    return NextResponse.json({ guilds })
  } catch (error) {
    console.error('Error fetching guilds:', error)
    return NextResponse.json({ error: 'Failed to fetch guilds' }, { status: 500 })
  }
}
