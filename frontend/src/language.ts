import words from './translations.json'
export type Language = 'en' | 'fa' | 'ps'
const dictionary: Record<string,string[]> = words
export function language(): Language {
  const value = localStorage.getItem('pharmawise.language')
  return value === 'fa' || value === 'ps' ? value : 'en'
}
export function t(value: string) {
  const lang=language()
  return lang === 'en' ? value : dictionary[value]?.[lang==='fa'?0:1] ?? value
}
