import { t } from './language'
import { post } from './counterApi'
import Receipt, { type ReceiptData } from './Receipt'
import { useContext, useEffect, useRef, useState } from 'react'
import { RegisterContext } from './registerContext'
import type { Medicine } from './App'


type Pack = 'unit' | 'box'
type CartLine = { medicine: Medicine; pack: Pack; agreed?: string; quantity: string; discount: string }
type Customer = { is_business: boolean; id: number; name: string; phone: string }
const cents = (amount: string | number) => Math.round(Number(amount) * 100)
const money = (amount: number) => (amount / 100).toFixed(2)
const priceOf = (line: CartLine) =>
  Number(line.pack === 'box' ? line.medicine.box_sale_price : line.medicine.unit_sale_price)
const validQuantity = (value: string) => Number.isInteger(Number(value)) && Number(value) > 0
const sellingPrice = (line: CartLine) => line.agreed === undefined ? priceOf(line) : Number(line.agreed)
const subtotal = (line: CartLine) => cents(sellingPrice(line)) * Number(line.quantity) - cents(line.discount)

function errorText(data: unknown): string {
  if (typeof data === 'string') return data
  if (Array.isArray(data)) return data.map(errorText).join(' ')
  if (data && typeof data === 'object') return Object.values(data).map(errorText).join(' ')
  return 'Checkout could not be completed.'
}

export default function Checkout({ medicines, onComplete }: {
  medicines: Medicine[]; onComplete: () => void
}) {
  const pendingKey = 'pharmawise.pendingCheckout.' + useContext(RegisterContext)
  const [query, setQuery] = useState('')
  const [cart, setCart] = useState<CartLine[]>([])
  const [customer, setCustomer] = useState('')
  const [customers, setCustomers] = useState<Customer[]>([])
  const [businessForm, setBusinessForm] = useState(false)
  const business = customers.some(c => String(c.id) === customer && c.is_business)
  const [csrf, setCsrf] = useState('')
  const [credit, setCredit] = useState(false)
  const [paid, setPaid] = useState('0.00')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const lock = useRef(false)
  const [pending, setPending] = useState(() => sessionStorage.getItem(pendingKey))
  const [receipt, setReceipt] = useState<ReceiptData | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      try {
        const response = await fetch('/api/checkout/options/', { signal: controller.signal })
        const data = await response.json()
        if (!response.ok) throw new Error(errorText(data))
        setCustomers(data.customers)
        setCsrf(data.csrf)
        setError('')
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Could not load checkout.')
      }
    }
    void load()
    return () => controller.abort()
  }, [reload])

  const term = query.trim().toLowerCase()
  const choices = medicines.filter(m => m.is_active &&
    (m.generic_name.toLowerCase().includes(term) || m.sku.toLowerCase().includes(term)))
  const total = cart.reduce((sum, item) => sum + subtotal(item), 0)
  const collected = credit ? cents(paid) : total
  const priced = cart.every(line => validQuantity(line.quantity) && line.agreed !== '' && line.discount !== '' && Number(line.discount) >= 0 && subtotal(line) >= 0)
  const valid = priced && cart.length > 0 && cart.every(line => Number.isInteger(Number(line.quantity)) &&
    Number(line.quantity) > 0 && Number(line.discount) >= 0 && subtotal(line) >= 0) &&
    collected >= 0 && collected <= total && (!credit || !!customer)

  function add(medicine: Medicine, pack: Pack) {
    setReceipt(null)
    const index = cart.findIndex(line => line.medicine.id === medicine.id && line.pack === pack)
    if (index === -1) {
      setCart([...cart, { medicine, pack, agreed: business && pack === 'box' ? String(medicine.box_sale_price) : undefined, quantity: '1', discount: '0.00' }])
    } else {
      change(index, { quantity: String(Number(cart[index].quantity) + 1) })
    }
  }

  function change(index: number, patch: Partial<CartLine>) {
    setCart(cart.map((line, i) => i === index ? { ...line, ...patch } : line))
  }

  async function submit() {
    if (lock.current || !csrf || (!pending && !valid)) return
    lock.current = true
    setBusy(true)
    setError('')
    try {
      const body = pending ?? JSON.stringify({
        key: crypto.randomUUID(), customer: customer ? Number(customer) : null, paid: money(collected),
        lines: cart.map(line => ({
          medicine: line.medicine.id, package: line.pack, quantity: Number(line.quantity),
          discount: money(cents(line.discount)), expected_price: priceOf(line).toFixed(2),
          ...(line.agreed !== undefined ? { agreed_price: Number(line.agreed).toFixed(2) } : {}),
          expected_units: line.pack === 'box' ? line.medicine.units_per_box : 1,
        })),
      })
      sessionStorage.setItem(pendingKey, body)
      setPending(body)
      const response = await fetch('/api/checkout/', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf }, body,
      })
      if (response.status === 403 || response.status === 401) {
        throw new Error('Sign in again as the same cashier, then refresh this page and retry.')
      }
      const data = await response.json()
      if (!response.ok) {
        if (response.status === 400) {
          sessionStorage.removeItem(pendingKey)
          setPending(null)
        }
        throw new Error(errorText(data))
      }
      sessionStorage.removeItem(pendingKey)
      setPending(null)
      setReceipt(data)
      setCart([])
      setCredit(false)
      setPaid('0.00')
      setCustomer('')
      onComplete()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not reach checkout.')
    } finally {
      lock.current = false
      setBusy(false)
    }
  }

  return <section className="cashier">
    <h2>{t("Cashier checkout")}</h2>
    {error && <p role="alert">{t(error)}</p>}
    {!csrf && error && <button onClick={() => setReload(n => n + 1)}>Reload checkout</button>}
    {pending && !busy && <div role="status">A checkout is awaiting confirmation.{' '}
      <button disabled={!csrf} onClick={submit}>Retry same checkout</button></div>}
    {receipt && <Receipt receipt={receipt} />}
    <button className="business-toggle" disabled={busy || !!pending} onClick={() => setBusinessForm(!businessForm)}>{t("Add pharmacy customer")}</button>
    {businessForm && <form onSubmit={async e => {
      e.preventDefault();setBusy(true);setError('')
      try {
        const c = await post<Customer>('/api/business-customers/', Object.fromEntries(new FormData(e.currentTarget)))
        setCustomers(cs => [...cs.filter(x => x.id !== c.id), c]);setCustomer(String(c.id));setBusinessForm(false)
        setCart(cart.map(line => ({...line, agreed: line.pack === 'box' ? String(priceOf(line)) : undefined})))
      } catch(err){setError(err instanceof Error ? err.message : String(err))}
      finally {setBusy(false)}
    }}><fieldset disabled={busy}><label>{t("Pharmacy name")}<input name="name" required maxLength={150}/></label>
      <label>{t("Phone number")}<input name="phone" required maxLength={30}/></label><button>{t("Save pharmacy")}</button></fieldset></form>}
    <form onSubmit={e => { e.preventDefault(); void submit() }}>
      <fieldset disabled={busy || !!pending || !csrf}>
        <label>{t("Find medicine by name or SKU")} <input type="search" value={query} onChange={e => setQuery(e.target.value)} />
        </label>
        <div className="items">{choices.slice(0, 25).map(m => <div key={m.id}>
          <span>{m.generic_name} {m.strength} · {m.sku} · {m.stock_on_hand - m.expired_units} {t('available')}</span>
          <button type="button" disabled={m.unit_sale_price == null || m.stock_on_hand <= m.expired_units}
            onClick={() => add(m, 'unit')}>{t("Add")} {t(m.stock_unit || 'unit')}</button>
          {m.box_sale_price != null && !!m.units_per_box && <button type="button"
            disabled={m.stock_on_hand - m.expired_units < m.units_per_box} onClick={() => add(m, 'box')}>{t("Add box")}</button>}
        </div>)}</div>
        {choices.length === 0 && <p>{t("No matching medicines.")}</p>}
        <h3>{t("Cart")}</h3>
        {cart.length === 0 && <p>{t("Your cart is empty.")}</p>}
        {cart.map((line, i) => <div className="cart-line" key={line.medicine.id + line.pack}>
          <strong>{line.medicine.generic_name} {line.medicine.strength} · {line.pack === 'box' ? t("box") : t(line.medicine.stock_unit)} · {sellingPrice(line).toFixed(2)} {t("AFN")}</strong>
          {business && line.pack === 'box' && <label>{t("Agreed price per box (AFN)")}<input type="number" min="0" required step=".01"
            value={line.agreed ?? priceOf(line)} onChange={e => change(i,{agreed:e.target.value})}/></label>}
          <label>{t("Quantity")}<input type="number" min="1" step="1" required value={line.quantity}
            onChange={e => change(i, { quantity: e.target.value })} /></label>
          <label>{t("Line discount (AFN)")}<input type="number" min="0" step="0.01" required value={line.discount}
            max={money(cents(sellingPrice(line)) * Number(line.quantity))}
            onChange={e => change(i, { discount: e.target.value })} /></label>
          <span>{!validQuantity(line.quantity) ? t("Enter a positive quantity") : subtotal(line) < 0 ? t("Reduce the discount") : money(subtotal(line)) + ' ' + t('AFN')}</span>
          <button type="button" onClick={() => setCart(cart.filter((_, idx) => idx !== i))}>{t("Remove")}</button>
        </div>)}
        <label>{t("Customer")}<select value={customer} onChange={e => {
          const id = e.target.value
          setCustomer(id)
          const wholesale = customers.some(c => String(c.id) === id && c.is_business)
          setCart(cart.map(line => ({...line, agreed: wholesale && line.pack === 'box' ? String(priceOf(line)) : undefined})))
        }}>
          <option value="">{t("Walk-in")}</option>
          {customers.map(c => <option key={c.id} value={c.id}>{c.name} — {c.phone}</option>)}
        </select></label>
        <label>{t("Payment")}<select value={credit ? 'credit' : 'cash'} onChange={e => setCredit(e.target.value === 'credit')}>
          <option value="cash">{t("Paid in full")}</option><option value="credit">{t("Customer credit / partial payment")}</option>
        </select></label>
        {credit && <label>{t("Cash received (AFN)")}<input type="number" required min="0" step="0.01"
          max={money(total)} value={paid} onChange={e => setPaid(e.target.value)} /></label>}
        {credit && !customer && <p>{t("Select a customer to record credit.")}</p>}
        <p><strong>{t("Total")} {priced ? money(total) : "—"} {t("AFN")}</strong> {t("· Balance")} {priced ? money(total - collected) : "—"} {t("AFN")}</p>
        <button type="submit" disabled={!valid}>{busy ? t("Completing sale…") : t("Complete sale")}</button>
      </fieldset>
    </form>
  </section>
}
