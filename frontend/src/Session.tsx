import { t } from './language'
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { RegisterContext } from './registerContext'

type User = { id: number; username: string; organization: { id: number; name: string } | null }

async function authPost(action: string, data: object) {
  const tokenResponse = await fetch('/api/auth/csrf/')
  if (!tokenResponse.ok) throw new Error('Cannot reach the sign-in service.')
  const { csrfToken } = await tokenResponse.json()
  const response = await fetch('/api/auth/' + action + '/', {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}))
    throw new Error(detail.detail || 'Request failed. Refresh and try again.')
  }
  return response
}

export default function Session({children}: {children: ReactNode}) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const response = await fetch('/api/auth/me/', {signal: controller.signal})
        if (response.ok) setUser(await response.json())
        else if (![401, 403].includes(response.status)) throw new Error()
      } catch {
        if (!controller.signal.aborted) setError('Cannot reach the sign-in service.')
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [])
  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = Object.fromEntries(new FormData(event.currentTarget))
    setLoading(true)
    setError('')
    try { setUser(await (await authPost('login', data)).json()) }
    catch (err) { setError(err instanceof Error ? err.message : 'Sign-in failed.') }
    finally { setLoading(false) }
  }
  async function signOut() {
    setError('')
    try { await authPost('logout', {}); setUser(null) }
    catch (err) { setError(err instanceof Error ? err.message : 'Sign-out failed.') }
  }
  if (!user) return <main className="login"><h1>PharmaWise</h1>
    <form onSubmit={signIn}><fieldset disabled={loading}>
      <label>{t("Username")}<input required name="username" autoComplete="username" /></label>
      <label>{t("Password")}<input required type="password" name="password" autoComplete="current-password" /></label>
      <button type="submit">{t("Sign in")}</button>
    </fieldset></form>{error && <p role="alert">{t(error)}</p>}</main>
  return <><header className="top"><strong>{user.organization?.name}</strong><span>{user.username}</span> <button onClick={signOut}>{t("Sign out")}</button></header>
    {error && <p role="alert">{t(error)}</p>}{user.organization ? <RegisterContext.Provider value={user.organization.id + "." + user.id}>{children}</RegisterContext.Provider> : <p>Link this account to a pharmacy to open its register.</p>}</>
}
