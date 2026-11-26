import { language } from './language'
export function localDate(value: string) {
  return new Date(value).toLocaleString(language() === 'en' ? 'en-GB' : language() === 'ps' ? 'ps-AF' : 'fa-AF', { timeZone: 'Asia/Kabul', dateStyle: 'medium', timeStyle: 'short' })
}
