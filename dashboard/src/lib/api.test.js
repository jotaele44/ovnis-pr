import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('search() offline degradation', () => {
  it('resolves to an explicit unavailable result instead of throwing offline', async () => {
    vi.stubEnv('VITE_OFFLINE', '1')
    vi.resetModules()
    const { search } = await import('./api')

    await expect(search('ufo')).resolves.toEqual({ results: [], offlineUnavailable: true })
  })

  it('wraps the live /search response when not offline', async () => {
    vi.resetModules()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [{ case_id: 'A' }] }))
    const { search } = await import('./api')

    await expect(search('ufo')).resolves.toEqual({ results: [{ case_id: 'A' }], offlineUnavailable: false })
  })
})
