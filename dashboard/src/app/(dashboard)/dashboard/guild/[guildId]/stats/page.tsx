'use client'

import { use } from 'react'
import { useLiveStats } from '@/hooks/useLiveStats'
import { useGuildConfig } from '@/hooks/useGuildConfig'

interface PageProps {
  params: Promise<{ guildId: string }>
}

export default function StatsPage({ params }: PageProps) {
  const { guildId } = use(params)
  const { stats, isLoading: statsLoading } = useLiveStats(guildId)
  const { config, isLoading: configLoading } = useGuildConfig(guildId)

  if (statsLoading || configLoading) {
    return <LoadingSkeleton />
  }

  const tokenPercentage = config
    ? Math.round((stats?.tokensUsed || 0) / config.settings.maxTokensPerChannel * 100)
    : 0

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-dark-50">Statistics</h1>
        <p className="text-dark-400">Real-time bot performance and usage data</p>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Messages Cached"
          value={stats?.messagesCached?.toString() || '0'}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          }
        />
        <StatCard
          label="Tokens Used"
          value={stats?.tokensUsed?.toLocaleString() || '0'}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
            </svg>
          }
        />
        <StatCard
          label="Bot Latency"
          value={`${stats?.botLatency || 0}ms`}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          }
        />
        <StatCard
          label="Bot Uptime"
          value={stats?.botUptime || 'Unknown'}
          icon={
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
      </div>

      {/* Token Usage Bar */}
      <div className="card mb-8">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium text-dark-100">Token Usage</h2>
          <span className="text-sm text-dark-400">
            {stats?.tokensUsed?.toLocaleString() || 0} / {config?.settings.maxTokensPerChannel.toLocaleString() || 0}
          </span>
        </div>
        <div className="h-4 bg-dark-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              tokenPercentage > 80 ? 'bg-red-500' : tokenPercentage > 50 ? 'bg-yellow-500' : 'bg-coral'
            }`}
            style={{ width: `${Math.min(tokenPercentage, 100)}%` }}
          />
        </div>
        <p className="text-sm text-dark-500 mt-2">
          {tokenPercentage}% of conversation cache used
        </p>
      </div>

      {/* Activity */}
      <div className="card">
        <h2 className="font-medium text-dark-100 mb-4">Activity</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 bg-dark-800 rounded-lg">
            <p className="text-dark-500 text-sm">Last Activity</p>
            <p className="text-dark-100 font-medium">
              {stats?.lastActivity && stats.lastActivity !== 'Never'
                ? new Date(stats.lastActivity).toLocaleString()
                : 'No recent activity'}
            </p>
          </div>
          <div className="p-4 bg-dark-800 rounded-lg">
            <p className="text-dark-500 text-sm">Data Updated</p>
            <p className="text-dark-100 font-medium">
              Auto-refreshes every 30 seconds
            </p>
          </div>
        </div>
      </div>

      <p className="text-sm text-dark-500 mt-6">
        Stats are updated by the bot every 30 seconds. If stats show "Unknown", the bot may not be running.
      </p>
    </div>
  )
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string
  value: string
  icon: React.ReactNode
}) {
  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-2">
        <div className="text-coral">{icon}</div>
        <p className="text-dark-500 text-sm">{label}</p>
      </div>
      <p className="text-2xl font-bold text-dark-50">{value}</p>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-dark-800 rounded w-32 mb-2" />
      <div className="h-4 bg-dark-800 rounded w-64 mb-8" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="card">
            <div className="h-4 bg-dark-700 rounded w-20 mb-2" />
            <div className="h-8 bg-dark-700 rounded w-24" />
          </div>
        ))}
      </div>
    </div>
  )
}
