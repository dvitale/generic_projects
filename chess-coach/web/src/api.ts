/** Dispatched on window when the server answers 401: the session expired or was never opened. */
export const UNAUTHORIZED = 'sparringmate:unauthorized'

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (response.status === 401 && path !== '/auth/login') window.dispatchEvent(new Event(UNAUTHORIZED))
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Richiesta non valida. Controlla i dati.')
  return data as T
}
