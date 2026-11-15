import { Monitor, Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { LOCALES, LOCALE_FLAG, LOCALE_NAME, useLocale } from '@/lib/locale'
import { useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

const THEME_ICON = { dark: Moon, light: Sun, system: Monitor }

// Cycles dark → light → system. The label names the current mode, since the
// icon alone does not say whether it shows the state or the action.
export function ThemeToggle({ className }) {
  const { mode, cycle } = useTheme()
  const { t } = useLocale()
  const Icon = THEME_ICON[mode]
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={cycle}
      aria-label={t('ctl.theme', { mode: t(`theme.${mode}`) })}
      title={t('ctl.theme', { mode: t(`theme.${mode}`) })}
      className={cn('h-11 w-11 shrink-0 shell-desktop:h-8 shell-desktop:w-8', className)}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
    </Button>
  )
}

// A two-button segmented control labelled by flag (ES = 🇵🇷, EN = 🇺🇸). The flag is
// decorative; the language name is the accessible label and the `lang` of the
// button, so a screen reader announces it correctly and a platform that renders
// flags as letters still has a readable name.
export function LocaleToggle({ className }) {
  const { locale, setLocale, t } = useLocale()
  return (
    <div role="group" aria-label={t('ctl.language')} className={cn('flex shrink-0 items-center', className)}>
      {LOCALES.map((code) => (
        <Button
          key={code}
          type="button"
          variant="ghost"
          size="icon"
          lang={code}
          aria-label={LOCALE_NAME[code]}
          title={LOCALE_NAME[code]}
          aria-pressed={locale === code}
          onClick={() => setLocale(code)}
          className={cn(
            'h-11 w-11 text-lg leading-none shell-desktop:h-8 shell-desktop:w-8 shell-desktop:text-base',
            locale === code ? 'bg-slate-800 opacity-100' : 'opacity-50 hover:opacity-100',
          )}
        >
          <span aria-hidden="true">{LOCALE_FLAG[code]}</span>
        </Button>
      ))}
    </div>
  )
}

export default function TopControls({ className }) {
  return (
    <div className={cn('flex items-center gap-0.5', className)}>
      <ThemeToggle />
      <LocaleToggle />
    </div>
  )
}
