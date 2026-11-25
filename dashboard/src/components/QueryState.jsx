import React from 'react'
import { FederationEmptyState } from '@pr-federation/react'

/**
 * Renders one of three states — loading, error, or empty — and otherwise gets
 * out of the way and renders its children.
 *
 * The distinction this exists to enforce: "the request failed" and "the request
 * succeeded and there is nothing" are different answers, and conflating them
 * shows the operator a confident wrong one. Before this, `getJSON` swallowed
 * failures into `[]`, so a backend outage rendered as "Queue empty" — the UI
 * asserted an empty queue when it had never successfully asked.
 *
 * Modelled on `centinelas-pr/frontend/src/components/ListState.jsx`, which
 * already had this split, so the federation gets one pattern rather than a
 * second dialect.
 *
 * Accessibility: loading is announced via `role="status"` / `aria-live`, the
 * error via `role="alert"` so a screen reader is interrupted for a failure but
 * not for a slow load.
 */
export default function QueryState({
  loading,
  error,
  isEmpty = false,
  emptyTitle = 'Nothing here',
  loadingLabel = 'Loading…',
  onRetry,
  children,
}) {
  if (loading) {
    return (
      <div className="py-8 text-center text-xs text-slate-400" role="status" aria-live="polite" aria-busy="true">
        {loadingLabel}
      </div>
    )
  }

  if (error) {
    return (
      <div className="py-8 text-center" role="alert">
        <p className="text-xs font-medium text-amber-300">Could not load this data</p>
        <p className="mx-auto mt-1 max-w-sm text-[11px] text-slate-400">
          {error.message || 'The backend did not respond.'}
        </p>
        <p className="mt-1 text-[11px] text-slate-400">
          This is not an empty result — the request did not succeed.
        </p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 rounded-md border border-slate-700 bg-slate-950 px-3 py-1 text-[11px] text-slate-300 transition hover:text-slate-100"
          >
            Retry
          </button>
        )}
      </div>
    )
  }

  if (isEmpty) return <FederationEmptyState className="py-8" title={emptyTitle} />

  return children
}
