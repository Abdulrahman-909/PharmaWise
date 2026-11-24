import { useEffect, useState } from 'react'
import MedicineBatches from './MedicineBatches'
import ExpiringBatches from './ExpiringBatches'

type Medicine = {
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
  }, [])

  const query = search.trim().toLowerCase()
  const visibleMedicines = medicines.filter((medicine) => {
    const matchesSearch =
      medicine.generic_name.toLowerCase().includes(query) ||
      medicine.sku.toLowerCase().includes(query)

    const matchesStock =
      stockFilter === 'all' ||
      (stockFilter === 'in-stock' && medicine.stock_on_hand > 0) ||
      (stockFilter === 'out-of-stock' && medicine.stock_on_hand === 0) ||
      (stockFilter === 'expired' && medicine.expired_units > 0)

    return matchesSearch && matchesStock
  })

  return (
    <main>
      <h1>PharmaWise</h1>
      <h2>Medicine catalog</h2>

      <div>
        <label htmlFor="medicine-search">Search by generic name or SKU</label>{' '}
        <input
          id="medicine-search"
          type="search"
          placeholder="Paracetamol or MED-001"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>

      <div>
        <label htmlFor="stock-filter">Stock status</label>{' '}
        <select
          id="stock-filter"
          value={stockFilter}
          onChange={(event) => setStockFilter(event.target.value)}
        >
          <option value="all">All medicines</option>
          <option value="in-stock">In stock</option>
          <option value="out-of-stock">Out of stock</option>
          <option value="expired">Has expired units</option>
        </select>
      </div>

      {message && <p role="status">{message}</p>}

      {medicines.length > 0 && visibleMedicines.length === 0 && (
        <p role="status">No medicines match the current filters.</p>
      )}

      {visibleMedicines.length > 0 && (
        <table>
          <thead>
            <tr>
              <th scope="col">SKU</th>
              <th scope="col">Generic name</th>
              <th scope="col">Strength</th>
              <th scope="col">Form</th>
              <th scope="col">Stock unit</th>
              <th scope="col">Price per unit (AFN)</th>
              <th scope="col">Units per box</th>
              <th scope="col">Price per box (AFN)</th>
              <th scope="col">Stock on hand</th>
              <th scope="col">Expired units</th>
              <th scope="col">Unexpired units</th>
              <th scope="col">Reorder status</th>
              <th scope="col">Earliest expiry</th>
              <th scope="col">Batches</th>
            </tr>
          </thead>
          <tbody>
            {visibleMedicines.map((medicine) => (
              <tr key={medicine.id}>
                <td>{medicine.sku}</td>
                <td>{medicine.generic_name}</td>
                <td>{medicine.strength}</td>
                <td>{medicine.dosage_form}</td>
                <td>{medicine.stock_unit || '—'}</td>
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
                    : 'Unavailable'}
                </td>
                <td>{getReorderStatus(medicine)}</td>
                <td>{medicine.earliest_expiry ?? '—'}</td>
                <td>
                <MedicineBatches medicineId={medicine.id} stockUnit={medicine.stock_unit} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <ExpiringBatches />
    </main>
  )
}