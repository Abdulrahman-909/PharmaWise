import { t } from './language'
import Delivery from './Delivery'
import History from './History'
import { useEffect, useState } from 'react'
import MedicineBatches from './MedicineBatches'
import Overview from './Overview'
import Checkout from './Checkout'
import ExpiringBatches from './ExpiringBatches'

export type Medicine = {
  is_active: boolean
  id: number
  sku: string
  generic_name: string
  strength: string
  dosage_form: string
  stock_unit: string
  units_per_box: number | null
  unit_sale_price: number | string | null
  box_sale_price: number | string | null
  stock_on_hand: number
  expired_units: number
  earliest_expiry: string | null
  reorder_level: number | null
}

function getReorderStatus(medicine: Medicine): string {
  if (medicine.reorder_level == null) return 'Threshold not set'
  if (medicine.stock_on_hand == null || medicine.expired_units == null) {
    return 'Unavailable'
  }

  const unexpiredUnits = medicine.stock_on_hand - medicine.expired_units
  return unexpiredUnits <= medicine.reorder_level ? 'Needs reorder' : 'Above threshold'
}

export default function App() {
  const [page, setPage] = useState<'overview' | 'catalog' | 'checkout' | 'receipts' | 'debts' | 'delivery'>('overview')
  const [revision, setRevision] = useState(0)
  const [medicines, setMedicines] = useState<Medicine[]>([])
  const [message, setMessage] = useState('Loading medicines…')
  const [search, setSearch] = useState('')
  const [stockFilter, setStockFilter] = useState('all')

  useEffect(() => {
    const controller = new AbortController()

    async function loadMedicines() {
      try {
        const response = await fetch('/api/medicines/', {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        })

        if (response.status === 401 || response.status === 403) {
          setMessage('Sign in to Django Admin as staff, then refresh this page.')
          return
        }

        if (!response.ok) {
          throw new Error(`Django returned HTTP ${response.status}.`)
        }

        const rows: Medicine[] = await response.json()
        setMedicines(rows)
        setMessage(rows.length === 0 ? 'No medicines in the catalog yet.' : '')
      } catch (error) {
        if (controller.signal.aborted) return

        setMessage(
          error instanceof Error ? error.message : 'Could not load medicines.'
        )
      }
    }

    void loadMedicines()
    return () => controller.abort()
  }, [revision])

  const query = search.trim().toLowerCase()
  const visibleMedicines = medicines.filter((medicine) => {
    const matchesSearch =
      medicine.generic_name.toLowerCase().includes(query) ||
      medicine.sku.toLowerCase().includes(query)

    const matchesStock =
      stockFilter === 'all' ||
      (stockFilter === 'reorder' && getReorderStatus(medicine) === 'Needs reorder') ||
      (stockFilter === 'in-stock' && medicine.stock_on_hand > 0) ||
      (stockFilter === 'out-of-stock' && medicine.stock_on_hand === 0) ||
      (stockFilter === 'expired' && medicine.expired_units > 0)

    return matchesSearch && matchesStock
  })

  return (
    <main className="workspace">
      <aside><div className="brand"><b aria-hidden="true">✚</b> PharmaWise</div>
        <nav aria-label="Workspace">
          {(['overview', 'catalog', 'checkout', 'receipts', 'debts', 'delivery'] as const).map(tab =>
            <button key={tab} type="button" aria-pressed={page === tab} onClick={() => setPage(tab)}>
              {{ overview: t("Overview"), catalog: t("Medicine catalog"), checkout: t("Checkout"), receipts: t("Receipt history"), debts: t("Customer debts"), delivery: t("Receive deliveries") }[tab]}
            </button>)}
        </nav>
      </aside>
      <div className="content">
      {page === 'delivery' && <Delivery medicines={medicines} refresh={() => setRevision(v => v+1)} />}
      {(page === 'receipts' || page === 'debts') && <History key={page} debts={page === 'debts'} />}
      {page === 'overview' && <>
        <Overview revision={revision} />
        <div className="panel"><div className="section-title"><h3>{t("Reorder watch")}</h3>
          <button onClick={() => { setPage('catalog'); setStockFilter('reorder'); setSearch('') }}>{t("View in catalog")}</button></div>
          {message ? <p>{t(message)}</p> : medicines.some(m => getReorderStatus(m) === 'Needs reorder')
            ? medicines.filter(m => getReorderStatus(m) === 'Needs reorder').slice(0, 5).map(m =>
              <div className="watch" key={m.id}><strong>{m.generic_name} {m.strength}</strong>
                <span>{m.stock_on_hand - m.expired_units} {t('available')} · {t('Reorder level')} {m.reorder_level} ({t(m.stock_unit)})</span></div>)
            : <p>{t("No medicines at their reorder level.")}</p>}
        </div>
      </>}
      {page !== 'overview' && message && <p role="status">{t(message)}</p>}
      <div hidden={page !== 'checkout'}>
        <Checkout medicines={medicines} onComplete={() => setRevision(value => value + 1)} />
      </div>
      <section hidden={page !== 'catalog'}>
      <h2>{t("Medicine catalog")}</h2>

      <div>
        <label htmlFor="medicine-search">{t("Search by generic name or SKU")}</label>{' '}
        <input
          id="medicine-search"
          type="search"
          placeholder="Paracetamol or MED-001"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>

      <div>
        <label htmlFor="stock-filter">{t("Stock status")}</label>{' '}
        <select
          id="stock-filter"
          value={stockFilter}
          onChange={(event) => setStockFilter(event.target.value)}
        >
          <option value="all">{t("All medicines")}</option>
          <option value="in-stock">{t("In stock")}</option>
          <option value="out-of-stock">{t("Out of stock")}</option>
          <option value="reorder">{t("Needs reorder")}</option>
          <option value="expired">{t("Has expired units")}</option>
        </select>
      </div>

      {medicines.length > 0 && visibleMedicines.length === 0 && (
        <p role="status">No medicines match the current filters.</p>
      )}

      {visibleMedicines.length > 0 && (
        <div className="table-wrap"><table>
          <thead>
            <tr>
              <th scope="col">{t("SKU")}</th>
              <th scope="col">{t("Generic name")}</th>
              <th scope="col">{t("Strength")}</th>
              <th scope="col">{t("Form")}</th>
              <th scope="col">{t("Stock unit")}</th>
              <th scope="col">{t("Price per unit (AFN)")}</th>
              <th scope="col">{t("Units per box")}</th>
              <th scope="col">{t("Price per box (AFN)")}</th>
              <th scope="col">{t("Stock on hand")}</th>
              <th scope="col">{t("Expired units")}</th>
              <th scope="col">{t("Unexpired units")}</th>
              <th scope="col">{t("Reorder status")}</th>
              <th scope="col">{t("Earliest expiry")}</th>
              <th scope="col">{t("Batches")}</th>
            </tr>
          </thead>
          <tbody>
            {visibleMedicines.map((medicine) => (
              <tr key={medicine.id}>
                <td>{medicine.sku}</td>
                <td>{medicine.generic_name}</td>
                <td>{medicine.strength}</td>
                <td>{medicine.dosage_form}</td>
                <td>{t(medicine.stock_unit) || '—'}</td>
                <td>
  {medicine.unit_sale_price != null
    ? Number(medicine.unit_sale_price).toFixed(2)
    : '—'}
</td>
<td>{medicine.units_per_box ?? '—'}</td>
<td>
  {medicine.box_sale_price != null
    ? Number(medicine.box_sale_price).toFixed(2)
    : '—'}
</td>
                <td>{medicine.stock_on_hand ?? 'Unavailable'}</td>
                <td>{medicine.expired_units ?? 'Unavailable'}</td>
                <td>
                  {medicine.stock_on_hand != null && medicine.expired_units != null
                    ? medicine.stock_on_hand - medicine.expired_units
                    : t("Unavailable")}
                </td>
                <td>{t(getReorderStatus(medicine))}</td>
                <td>{medicine.earliest_expiry ?? '—'}</td>
                <td>
                <MedicineBatches key={revision} medicineId={medicine.id} stockUnit={medicine.stock_unit} />
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}

      <ExpiringBatches key={revision} />
      </section>
      </div>
    </main>
  )
}