import { t } from './language'
import { useState } from 'react'
import { post } from './counterApi'
import { localDate } from './localDate'

export type Invoice = { sale: number; balance: string }
type Proof = { id: number; date: string; sale: number; shop: string; name: string; amount: string; balance: string }

export default function Repayment({ invoices, refresh }: { invoices: Invoice[]; refresh: () => void }) {
  const [sale, setSale] = useState('')
  const [amount, setAmount] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [proof, setProof] = useState<Proof>()
  const selected = invoices.find(i => String(i.sale) === sale) ?? invoices[0]
  const [key, setKey] = useState(() => crypto.randomUUID())
  return <div className="repayment">
    {proof && <article className="payment-proof receipt"><strong>{proof.shop}</strong><h3>{t("Payment receipt #")} {proof.id}</h3>
      <p>{proof.name} · {localDate(proof.date)}</p><p>{t("Sale #")} {proof.sale}</p><p>{t("Amount received ·")} {proof.amount} {t("AFN")}</p>
      <p>{t("Remaining on this receipt ·")} {proof.balance} {t("AFN")}</p><button onClick={() => window.print()}>{t("Print receipt")}</button></article>}
    {selected && <form onSubmit={async e => {
      e.preventDefault()
      if (busy) return
      setBusy(true); setError('')
      try {
        const result = await post<Proof>('/api/receipts/' + selected.sale + '/repay/', {key, amount})
        setProof(result); setAmount(''); setKey(crypto.randomUUID()); refresh()
      } catch (err) {setError(String(err instanceof Error ? err.message : err))}
      finally { setBusy(false) }
    }}><fieldset disabled={busy}><legend>{t("Record repayment")}</legend>
      <label>{t("Unpaid receipt")}<select value={selected.sale} onChange={e => {setSale(e.target.value);setKey(crypto.randomUUID())}}>
        {invoices.map(i => <option key={i.sale} value={i.sale}>#{i.sale} · {i.balance} {t("AFN")}</option>)}</select></label>
      <label>{t("Amount received")}<input required type="number" step=".01" min=".01" max={selected.balance} value={amount}
        onChange={e => {setAmount(e.target.value);setKey(crypto.randomUUID())}} /></label>
      <button>{t("Record payment")}</button></fieldset></form>}
    {error && <p role="alert">{t(error)}</p>}
  </div>
}
