import { useSyncExternalStore } from 'react'

// A tiny persisted preference store (theme, locale). localStorage can be absent
// or throw (private windows, blocked site data, the Capacitor webview before
// first paint), so every access is guarded and the value still lives in memory.
export function createPref(key, fallback, isValid) {
  const read = () => {
    try {
      const stored = window.localStorage.getItem(key)
      if (stored && isValid(stored)) return stored
    } catch {
      /* storage unavailable: use the fallback */
    }
    return null
  }

  let value = read() ?? (typeof fallback === 'function' ? fallback() : fallback)
  const listeners = new Set()

  const subscribe = (listener) => {
    listeners.add(listener)
    return () => listeners.delete(listener)
  }
  const get = () => value
  const set = (next) => {
    if (!isValid(next) || next === value) return
    value = next
    try {
      window.localStorage.setItem(key, next)
    } catch {
      /* in-memory only */
    }
    listeners.forEach((listener) => listener())
  }
  const use = () => useSyncExternalStore(subscribe, get, get)

  return { get, set, subscribe, use }
}
