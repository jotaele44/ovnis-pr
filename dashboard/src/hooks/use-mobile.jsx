import * as React from "react"

// The federation GUI spec's mobile breakpoint is <= 860 CSS px. Keep in step with
// the `shell-mobile` / `shell-desktop` variants in index.css.
export const MOBILE_BREAKPOINT = 860

const query = () => `(max-width: ${MOBILE_BREAKPOINT - 1}px)`

// Read synchronously on first render so a phone never paints the desktop shell
// (and mounts a map in a 440px pane) before the effect corrects it.
const initial = () =>
  typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(query()).matches
    : false

export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState(initial)

  React.useEffect(() => {
    const mql = window.matchMedia(query())
    const onChange = () => setIsMobile(mql.matches)
    mql.addEventListener("change", onChange)
    onChange()
    return () => mql.removeEventListener("change", onChange)
  }, [])

  return isMobile
}
