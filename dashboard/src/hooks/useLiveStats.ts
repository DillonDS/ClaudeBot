import useSWR from 'swr'

interface GuildStats {
  messagesCached: number
  tokensUsed: number
  lastActivity: string
  botUptime: string
  botLatency: number
}

const fetcher = (url: string) => fetch(url).then((res) => res.json())

export function useLiveStats(guildId: string | null) {
  const { data, error, isLoading } = useSWR<GuildStats>(
    guildId ? `/api/guilds/${guildId}/stats` : null,
    fetcher,
    {
      refreshInterval: 30000, // Refresh every 30 seconds
      revalidateOnFocus: true,
    }
  )

  return {
    stats: data,
    error,
    isLoading,
  }
}
