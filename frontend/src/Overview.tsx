import { t } from './language'
import { useEffect, useState } from 'react'

type Report = {
  date: string; completed_sales: number; sales_after_discounts: string
  payments_received: string; net_payments: string; payment_corrections: string
  known_purchase_cost: string; gross_profit: string | null; units_with_unknown_cost: number
}

const afn = (value: string) => Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 })
function previousDay(end: string, offset: number) {
  const date = new Date(end + 'T12:00:00Z')
  date.setUTCDate(date.getUTCDate() - offset)
  return date.toISOString().slice(0, 10)
}

export default function Overview({ revision }: { revision: number }) {
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kabul' }).format(new Date())
  const [date, setDate] = useState(today)
  const [week, setWeek] = useState<Report[]>([])
  const [message, setMessage] = useState('Loading sales report…')
  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setMessage('Loading sales report…')
      try {
        const days = await Promise.all(Array.from({ length: 7 }, async (_, i) => {
          const r = await fetch('/api/reports/daily-sales/?date=' + previousDay(date, 6 - i), { signal: controller.signal })
          if (!r.ok) throw new Error(r.status === 403 ? 'Your account does not have access to sales reports.' : 'Could not load the sales report.')
          return await r.json() as Report
        }))
        if (!controller.signal.aborted) { setWeek(days); setMessage('') }
      } catch (err) {
        if (!controller.signal.aborted) setMessage(err instanceof Error ? err.message : 'Report unavailable.')
      }
    }
    void load()
    return () => controller.abort()
  }, [date, revision])
  const day = week.at(-1)
  const peak = Math.max(1, ...week.map(d => Number(d.sales_after_discounts)))
  return <section>
    <div className="section-title"><h2>{t("Sales overview")}</h2><label>{t("Report date")} <input type="date" value={date} max={today}
      onChange={e => { if (e.target.value && e.target.validity.valid) setDate(e.target.value) }} /></label></div>
    {message ? <p role="status">{t(message)}</p> : day && <>
      <div className="metrics">
        <article><small>{t("Sales after discounts")}</small><strong>{afn(day.sales_after_discounts)} <em>{t("AFN")}</em></strong><span>{day.completed_sales} {t("completed sales")}</span></article>
        <article><small>{t("Net payments")}</small><strong>{afn(day.net_payments)} <em>{t("AFN")}</em></strong><span>{afn(day.payment_corrections)} {t("AFN in corrections")}</span></article>
        <article><small>{t("Gross profit")}</small><strong>{day.gross_profit === null ? t("Unknown") : afn(day.gross_profit)} {day.gross_profit !== null && <em>{t("AFN")}</em>}</strong><span>{day.units_with_unknown_cost ? day.units_with_unknown_cost + ' ' + t('units with unknown cost') : afn(day.known_purchase_cost) + ' ' + t('AFN purchase cost')}</span></article>
      </div>
      <article className="panel"><h3>{t("Sales over seven days")}</h3>
        <div className="bars">{week.map(d => <div key={d.date}>
          <small>{afn(d.sales_after_discounts)}</small>
          <div className="track"><i style={{ height: (100 * Number(d.sales_after_discounts) / peak) + '%' }} /></div>
          <small>{d.date.slice(5)}</small>
        </div>)}</div>
        <p className="muted">{t("Daily sales after discounts · AFN")}</p>
      </article>
    </>}
  </section>
}
