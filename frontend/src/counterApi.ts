export async function post<T>(url: string, body: unknown): Promise<T> {
  const token = await fetch('/api/auth/csrf/')
  if (!token.ok) throw new Error('Refresh and sign in again.')
  const { csrfToken } = await token.json()
  const response = await fetch(url, { method: 'POST', headers: {
    'Content-Type': 'application/json', 'X-CSRFToken': csrfToken,
  }, body: JSON.stringify(body) })
  const data = await response.json()
  if (!response.ok) throw new Error(Object.values(data).flat(Infinity).join(' ') || 'Request failed.')
  return data
}
