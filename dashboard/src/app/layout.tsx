import type { Metadata } from 'next'
import { Providers } from '../components/Providers'
import './globals.css'

export const metadata: Metadata = {
  title: 'ClaudeBot Dashboard',
  description: 'Manage your ClaudeBot settings',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-dark-950">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
