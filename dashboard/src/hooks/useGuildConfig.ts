import useSWR from 'swr'
import type { GuildConfig, GuildSettings, GuildCommands } from '@/lib/config.types'

const fetcher = (url: string) => fetch(url).then((res) => res.json())

export function useGuildConfig(guildId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<GuildConfig>(
    guildId ? `/api/guilds/${guildId}/config` : null,
    fetcher
  )

  const updateSettings = async (settings: Partial<GuildSettings>) => {
    if (!guildId || !data) return

    // Optimistic update
    mutate({ ...data, settings: { ...data.settings, ...settings } }, false)

    try {
      const response = await fetch(`/api/guilds/${guildId}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings }),
      })

      if (!response.ok) {
        throw new Error('Failed to update settings')
      }

      return mutate()
    } catch (error) {
      // Revert on error
      mutate()
      throw error
    }
  }

  const updateCommands = async (commands: Partial<GuildCommands>) => {
    if (!guildId || !data) return

    mutate({ ...data, commands: { ...data.commands, ...commands } }, false)

    try {
      const response = await fetch(`/api/guilds/${guildId}/commands`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ commands }),
      })

      if (!response.ok) {
        throw new Error('Failed to update commands')
      }

      return mutate()
    } catch (error) {
      mutate()
      throw error
    }
  }

  const updatePrompt = async (systemPrompt: string | null) => {
    if (!guildId || !data) return

    mutate({ ...data, systemPrompt }, false)

    try {
      const response = await fetch(`/api/guilds/${guildId}/prompt`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ systemPrompt }),
      })

      if (!response.ok) {
        throw new Error('Failed to update prompt')
      }

      return mutate()
    } catch (error) {
      mutate()
      throw error
    }
  }

  return {
    config: data,
    error,
    isLoading,
    updateSettings,
    updateCommands,
    updatePrompt,
    refresh: mutate,
  }
}
