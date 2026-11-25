import { Component } from 'react'

/**
 * Catches render-time exceptions so one bad component does not blank the app.
 *
 * Without this, a throw during render unmounts the whole React tree and the
 * operator gets a white page with no indication of what happened or that
 * anything is wrong — the most extreme version of the failure this repo already
 * had, where an outage was reported as an empty queue.
 *
 * Deliberately not a data-fetching error state: `QueryState` handles a request
 * that failed. This handles code that threw. Keeping them separate means a
 * backend outage does not tear down the page chrome the operator needs in order
 * to understand the outage.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // No telemetry sink in this repo, so the console is the record. Keep the
    // component stack: it is the only way to find which subtree threw.
    console.error('Unhandled render error', error, info?.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="flex min-h-[200px] flex-col items-center justify-center gap-2 p-6 text-center" role="alert">
        <p className="text-sm font-medium text-amber-300">Something broke while rendering this view</p>
        <p className="max-w-md text-[11px] text-slate-400">
          {error.message || String(error)}
        </p>
        <p className="max-w-md text-[11px] text-slate-400">
          This is a bug in the dashboard, not a problem with your data.
        </p>
        <button
          type="button"
          onClick={() => this.setState({ error: null })}
          className="mt-2 rounded-md border border-slate-700 bg-slate-950 px-3 py-1 text-[11px] text-slate-300 transition hover:text-slate-100"
        >
          Try again
        </button>
      </div>
    )
  }
}
