import { t } from './language'
import { localDate } from "./localDate"
export type ReceiptData = {
  wholesale?: boolean; sale: number; total: string; paid: string; balance: string; customer: string
  date?: string; cashier?: string; shop?: string; current?: boolean
  lines: { name: string; package: string; quantity: number; price: string; discount: string; total: string }[]
}


export default function Receipt({ receipt }: { receipt: ReceiptData }) {
  return <article className="receipt" aria-label="Sale receipt">
    <strong>{receipt.shop || 'PharmaWise'}</strong>
    <div className="section-title"><h3>{receipt.wholesale ? t("Wholesale invoice") : t("Receipt")} #{receipt.sale}</h3>
      <button type="button" onClick={() => window.print()}>{t("Print receipt")}</button></div>
    {receipt.date && <p>{localDate(receipt.date)} {t("· Kabul time")}</p>}
    {receipt.cashier && <p>{t("Cashier ·")} {receipt.cashier}</p>}
    <p>{t("Customer ·")} {t(receipt.customer)}</p>
    <table><thead><tr>{[t("Item"), t("Qty"), t("Unit price"), t("Discount"), t("Amount")].map(s => <th key={s}>{s}</th>)}</tr></thead>
      <tbody>{receipt.lines.map((line, i) => <tr key={i}><td>{line.name}</td><td>{line.quantity} × {t(line.package)}</td>
        <td>{line.price}</td><td>{line.discount}</td><td>{line.total}</td></tr>)}</tbody></table>
    <p><strong>{t("Total")} {receipt.total} {t("AFN")}</strong></p>
    <p>{receipt.current ? t("Payments recorded") : t("Paid at checkout")} · {receipt.paid} {t("AFN")}</p>
    <p>{receipt.current ? t("Current balance") : t("Balance at checkout")} · {receipt.balance} {t("AFN")}</p>
  </article>
}
