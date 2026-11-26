import { t } from './language'
import { useEffect, useState } from 'react'
import type { Medicine } from './App'
import { post } from './counterApi'

type Row = { medicine: string; batch: string; expiry: string; boxes: string; units: string; price: string }
const empty = (): Row => ({medicine:'',batch:'',expiry:'',boxes:'1',units:'1',price:''})
export default function Delivery({medicines, refresh}: {medicines: Medicine[]; refresh: () => void}) {
  const [suppliers, setSuppliers] = useState<{id:number;name:string}[]>([])
  const [rows,setRows] = useState([empty()])
  const [error,setError] = useState('')
  const [success,setSuccess] = useState('')
  const [busy,setBusy] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/deliveries/',{signal:controller.signal}).then(async r => {
      if (!r.ok) throw new Error('Supplier access unavailable.')
      setSuppliers(await r.json())
    }).catch(e => {if (!controller.signal.aborted) setError(e.message)})
    return () => controller.abort()
  }, [])
  function change(i:number,patch: Partial<Row>) {setRows(rows.map((r, j) => i === j ? {...r,...patch} : r))}
  return <section><h2>{t("Receive deliveries")}</h2>
    <form onSubmit={async e => {
      e.preventDefault()
      if (busy) return
      const form=e.currentTarget
      setBusy(true);setError('');setSuccess('')
      try {
        const result=await post<{invoice:string;units:number}>('/api/deliveries/',{...Object.fromEntries(new FormData(form)),lines:rows})
        setSuccess(result.invoice+' · '+result.units+' '+t('stock units received'));form.reset();setRows([empty()]);refresh()
      } catch(err){setError(err instanceof Error ? err.message : String(err))}
      finally{setBusy(false)}
    }}><fieldset disabled={busy}><label>{t("Supplier")}<select name="supplier" required defaultValue=""><option value="">{t("Select supplier")}</option>
      {suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label>{t("Invoice number")}<input name="invoice" required maxLength={80}/></label>
      <label>{t("Date received")}<input type="date" name="date" required defaultValue={new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Kabul'}).format(new Date())}/></label>
      {rows.map((r,i) => <fieldset key={i}><legend>{t("Delivery line")} {i+1}</legend>
        <label>{t("Medicine")}<select required value={r.medicine} onChange={e => change(i,{medicine:e.target.value,units:String(medicines.find(m => String(m.id) === e.target.value)?.units_per_box || 1)})}>
          <option value="">{t("Select medicine")}</option>{medicines.map(m => <option key={m.id} value={m.id}>{m.sku} · {m.generic_name} {m.strength}</option>)}</select></label>
        <label>{t("Batch number")}<input required value={r.batch} onChange={e => change(i,{batch:e.target.value})}/></label>
        <label>{t("Expiry date")}<input required type="date" value={r.expiry} onChange={e => change(i,{expiry:e.target.value})}/></label>
        {(['boxes','units','price'] as const).map(k => <label key={k}>{{boxes:t("Boxes received"),units:t("Units per box"),price:t("Purchase price per box (AFN)")}[k]}
          <input required type="number" step={k==='price'?'.01':'1'} min={k==='price'?0:1} value={r[k]} onChange={e => change(i,{[k]:e.target.value})}/></label>)}
        {rows.length>1 && <button type="button" onClick={() => setRows(rows.filter((_,j)=>j!==i))}>{t("Remove")}</button>}</fieldset>)}
      <button type="button" onClick={() => setRows([...rows,empty()])}>{t("Add delivery line")}</button> <button>{t("Post delivery")}</button>
    </fieldset></form>{error && <p role="alert">{t(error)}</p>}{success && <p role="status">{success}</p>}</section>
}
