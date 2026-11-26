import { StrictMode, useLayoutEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './theme.css'
import App from './App'
import Session from './Session'
import { language, type Language } from './language'

type Theme = 'system' | 'light' | 'dark'

const labels = {
  en: ['Language', 'Theme', 'System', 'Light', 'Dark'],
  fa: ['زبان', 'نمایش', 'مطابق سیستم', 'روشن', 'تاریک'],
  ps: ['ژبه', 'بڼه', 'د سیسټم له مخې', 'روښانه', 'تیاره'],
}

function savedTheme(): Theme {
  const value = localStorage.getItem('pharmawise.theme')
  return value === 'light' || value === 'dark' ? value : 'system'
}

export function Pharmacy() {
  const [lang, setLang] = useState(language)
  const [theme, setTheme] = useState(savedTheme)
  const [languageLabel, themeLabel, system, light, dark] = labels[lang]

  useLayoutEffect(() => {
    document.documentElement.lang = lang === 'fa' ? 'fa-AF' : lang
    document.documentElement.dir = lang === 'en' ? 'ltr' : 'rtl'
  }, [lang])

  useLayoutEffect(() => {
    const preference = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      document.documentElement.dataset.theme = theme === 'system'
        ? (preference.matches ? 'dark' : 'light') : theme
    }
    apply()
    if (theme === 'system') {
      preference.addEventListener('change', apply)
      return () => preference.removeEventListener('change', apply)
    }
  }, [theme])

  return <>
    <div className="language-bar">
      <label>{languageLabel}
        <select value={lang} onChange={event => {
          const value = event.target.value as Language
          localStorage.setItem('pharmawise.language', value)
          setLang(value)
        }}>
          <option value="en">English</option>
          <option value="fa">دری</option>
          <option value="ps">پښتو</option>
        </select>
      </label>
      <label>{themeLabel}
        <select value={theme} onChange={event => {
          const value = event.target.value as Theme
          localStorage.setItem('pharmawise.theme', value)
          setTheme(value)
        }}>
          <option value="system">{system}</option>
          <option value="light">{light}</option>
          <option value="dark">{dark}</option>
        </select>
      </label>
    </div>
    <Session><App /></Session>
  </>
}

createRoot(document.getElementById('root')!).render(<StrictMode><Pharmacy /></StrictMode>)
