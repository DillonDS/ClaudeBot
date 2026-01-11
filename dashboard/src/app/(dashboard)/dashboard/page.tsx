'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { getGuildIconUrl, type ManageableGuild } from '@/lib/discord'

export default function DashboardPage() {
  const [guilds, setGuilds] = useState<ManageableGuild[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchGuilds() {
      try {
        const response = await fetch('/api/guilds')
        if (!response.ok) throw new Error('Failed to fetch guilds')
        const data = await response.json()
        setGuilds(data.guilds)
      } catch (err) {
        setError('Failed to load servers')
      } finally {
        setLoading(false)
      }
    }
    fetchGuilds()
  }, [])

  if (loading) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-dark-50 mb-6">Select a Server</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="card animate-pulse">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-dark-700" />
                <div className="flex-1">
                  <div className="h-4 bg-dark-700 rounded w-3/4 mb-2" />
                  <div className="h-3 bg-dark-800 rounded w-1/2" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card text-center py-12">
        <p className="text-red-400 mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="btn-secondary"
        >
          Retry
        </button>
      </div>
    )
  }

  const guildsWithBot = guilds.filter((g) => g.hasBot)
  const guildsWithoutBot = guilds.filter((g) => !g.hasBot)

  return (
    <div>
      <h1 className="text-2xl font-bold text-dark-50 mb-6">Select a Server</h1>

      {guildsWithBot.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-medium text-dark-400 uppercase tracking-wider mb-3">
            Servers with ClaudeBot
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {guildsWithBot.map((guild) => (
              <Link
                key={guild.id}
                href={`/dashboard/guild/${guild.id}`}
                className="card hover:border-coral transition-colors group"
              >
                <div className="flex items-center gap-4">
                  <img
                    src={getGuildIconUrl(guild.id, guild.icon)}
                    alt={guild.name}
                    className="w-12 h-12 rounded-full"
                  />
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-dark-100 truncate group-hover:text-coral transition-colors">
                      {guild.name}
                    </h3>
                    <p className="text-sm text-green-500">Bot active</p>
                  </div>
                  <svg
                    className="w-5 h-5 text-dark-500 group-hover:text-coral transition-colors"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {guildsWithoutBot.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-dark-400 uppercase tracking-wider mb-3">
            Servers without ClaudeBot
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {guildsWithoutBot.map((guild) => (
              <div
                key={guild.id}
                className="card opacity-60 cursor-not-allowed"
              >
                <div className="flex items-center gap-4">
                  <img
                    src={getGuildIconUrl(guild.id, guild.icon)}
                    alt={guild.name}
                    className="w-12 h-12 rounded-full grayscale"
                  />
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-dark-300 truncate">
                      {guild.name}
                    </h3>
                    <p className="text-sm text-dark-500">Bot not installed</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {guilds.length === 0 && (
        <div className="card text-center py-12">
          <p className="text-dark-400">
            No servers found. Make sure you have admin permissions on at least one server.
          </p>
        </div>
      )}
    </div>
  )
}
