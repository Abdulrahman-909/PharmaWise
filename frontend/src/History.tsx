import { t } from './language'
import Repayment, { type Invoice } from './Repayment'
import { localDate } from "./localDate"
import { useEffect, useState } from 'react'
import Receipt, { type ReceiptData } from './Receipt'

type Row = { id: number; date: string; customer: string; total: string; balance: string }
type Page = { results: Row[]; next: string | null; previous: string | null }
type Account = { id: number; name: string; phone: string; balance: string; open_receipts: number }
type Statement = { invoices: Invoice[]; name: string; phone: string; balance: string; events: {
  date: string; sale: number; label: string; change: string; balance: string
}[] }

function useData<T>(url: string): {data?: T; error?: string} {
  const [result, setResult] = useState<{url: string; data?: T; error?: string}>()
  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const response = await fetch(url, { signal: controller.signal })
        if (!response.ok) throw new Error(response.status === 403 ? 'Your account does not have access.' : 'Could not load these records.')
        const data: T = await response.json()
        if (!controller.signal.aborted) setResult({ url, data })
      } catch (e) {
        if (!controller.signal.aborted) setResult({ url, error: e instanceof Error ? e.message : 'Request failed.' })
      }
    }
    void load()
    return () => controller.abort()
  }, [url])
  return result?.url === url ? result : {}
}

function ReceiptDetail({ id, back }: { id: number; back: () => void }) {
  const {data, error} = useData<ReceiptData>('/api/receipts/' + id + '/')
  return <section className="receipt-detail"><button onClick={back}>{t("Back to history")}</button>
    {data ? <Receipt receipt={data} /> : <p role="status">{t(error || 'Loading receipt…')}</p>}</section>
}

function ReceiptList({open}: {open: (id: number) => void}) {
  const [term, setTerm] = useState('')
  const [page, setPage] = useState(1)
  const {data, error} = useData<Page>('/api/receipts/?q=' + encodeURIComponent(term.trim()) + '&page=' + page)
  return <><h2>{t("Receipt history")}</h2><label>{t("Receipt number, customer name or phone")} <input type="search" value={term} onChange={e => {setPage(1); setTerm(e.target.value)}} /></label>
    {!data ? <p role="status">{t(error || 'Loading receipts…')}</p> : !data.results.length ? <p>{t("No matching receipts.")}</p> : <>
      <table><thead><tr><th>{t("Receipt")}</th><th>{t("Date · Kabul")}</th><th>{t("Customer")}</th><th>{t("Total (AFN)")}</th><th>{t("Current balance (AFN)")}</th></tr></thead>
        <tbody>{data.results.map(s => <tr key={s.id}><td><button onClick={() => open(s.id)}>{t("Receipt #")}{s.id}</button></td>
          <td>{localDate(s.date)}</td><td>{s.customer}</td><td>{s.total}</td><td>{s.balance}</td></tr>)}</tbody></table>
      <button disabled={!data.previous} onClick={() => setPage(page - 1)}>{t("Previous")}</button> {t("Page")} {page} <button disabled={!data.next} onClick={() => setPage(page + 1)}>{t("Next")}</button>
    </>}
  </>
}

function Accounts({open}: {open: (id: number) => void}) {
  const [term, setTerm] = useState('')
  const {data, error} = useData<Account[]>('/api/debtors/')
  const rows = data?.filter(a => (a.name + ' ' + a.phone).toLowerCase().includes(term.trim().toLowerCase()))
  return <><h2>{t("Customer debts")}</h2><label>{t("Customer name or phone")}<input type="search" value={term} onChange={e => setTerm(e.target.value)} /></label>
    {!rows ? <p role="status">{t(error || 'Loading balances…')}</p> : !rows.length ? <p>{t("No matching customers with an outstanding balance.")}</p> :
      <table><thead><tr><th>{t("Customer")}</th><th>{t("Phone")}</th><th>{t("Unpaid receipts")}</th><th>{t("Owes (AFN)")}</th></tr></thead>
        <tbody>{rows.map(a => <tr key={a.id}><td><button onClick={() => open(a.id)}>{a.name}</button></td>
          <td>{a.phone}</td><td>{a.open_receipts}</td><td>{a.balance}</td></tr>)}</tbody></table>}
  </>
}

function Ledger({id, back, open}: {id: number; back: () => void; open: (id: number) => void}) {
  const [version, setVersion] = useState(0)
  const {data, error} = useData<Statement>('/api/debtors/' + id + '/?v=' + version)
  return <><button onClick={back}>{t("All customer debts")}</button>
    <Repayment invoices={data?.invoices || []} refresh={() => setVersion(v => v+1)} />
    {data ? <><h2>{data.name}</h2><p>{data.phone}</p><p><strong>{t("Outstanding balance ·")} {data.balance} {t("AFN")}</strong></p>
      <table><thead><tr><th>{t("Date · Kabul")}</th><th>{t("Activity")}</th><th>{t("Receipt")}</th><th>{t("Change (AFN)")}</th><th>{t("Balance after (AFN)")}</th></tr></thead>
        <tbody>{data.events.map((e, i) => <tr key={i}><td>{localDate(e.date)}</td><td>{t(e.label)}</td>
          <td><button onClick={() => open(e.sale)}>{t("Receipt #")}{e.sale}</button></td><td>{e.change}</td><td>{e.balance}</td></tr>)}</tbody></table></> :
      <p role="status">{t(error || 'Loading account history…')}</p>}
  </>
}

export default function History({debts}: {debts: boolean}) {
  const [account, setAccount] = useState<number | null>(null)
  const [receipt, setReceipt] = useState<number | null>(null)
  if (receipt !== null) return <ReceiptDetail id={receipt} back={() => setReceipt(null)} />
  return <section>{debts ? account !== null ? <Ledger id={account} back={() => setAccount(null)} open={setReceipt} /> :
    <Accounts open={setAccount} /> : <ReceiptList open={setReceipt} />}</section>
}
