'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Lock, User, Wheat, AlertCircle } from 'lucide-react'

export default function AdminLoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleLogin = (e) => {
    e.preventDefault()
    // Hardcoded internal credentials (MVP only — no real auth).
    if (username === 'admin' && password === 'kedar123') {
      try { sessionStorage.setItem('kedar_admin', '1') } catch {}
      router.push('/admin/dashboard')
    } else {
      setError('Invalid username or password.')
    }
  }

  return (
    <div className="admin-login-background flex min-h-screen items-center justify-center bg-gradient-to-br from-gray-50 to-amber-50 px-4">
      <div className="w-full max-w-sm">
        <Link href="/" className="mb-6 flex items-center justify-center gap-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500 text-white">
            <Wheat className="h-5 w-5" />
          </span>
          <span className="text-xl font-extrabold text-gray-900">Kedar Foods</span>
        </Link>

        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
          <h1 className="text-center text-lg font-bold text-gray-900">Admin Portal</h1>
          <p className="mt-1 text-center text-sm text-gray-500">Sign in to manage products</p>

          {error && (
            <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              <AlertCircle className="h-4 w-4" /> {error}
            </div>
          )}

          <form onSubmit={handleLogin} className="mt-6 space-y-4">
            <div>
              <label className="mb-1 block text-xs font-semibold text-gray-600">Username</label>
              <div className="relative">
                <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  className="w-full rounded-lg border border-gray-200 py-2.5 pl-10 pr-3 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-gray-600">Password</label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-lg border border-gray-200 py-2.5 pl-10 pr-3 text-sm outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-100"
                />
              </div>
            </div>
            <button type="submit" className="w-full rounded-lg bg-amber-500 py-2.5 text-sm font-semibold text-white transition hover:bg-amber-600">
              Sign In
            </button>
          </form>

          <p className="mt-4 text-center text-xs text-gray-400">Demo credentials: admin / kedar123</p>
        </div>
        <Link href="/" className="mt-6 block text-center text-sm text-gray-500 hover:text-amber-600">← Back to store</Link>
      </div>
    </div>
  )
}
