import { useEffect, useState } from 'react'

type ExpiringBatch = {
  medicine__sku: string
  medicine__generic_name: string
  medicine__stock_unit: string
  batch_number: string
  expiry_date: string
  quantity_on_hand: number
}

export default function ExpiringBatches() {
  const [batches, setBatches] = useState<ExpiringBatch[]>([])
  const [message, setMessage] = useState('Loading expiry report…')

  useEffect(() => {
    const controller = new AbortController()

    async function loadReport() {
      try {
        const response = await fetch('/api/reports/expiring-batches/', {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        })

        if (response.status === 401 || response.status === 403) {
          throw new Error('Sign in to Django Admin as staff, then refresh.')
        }

        if (!response.ok) {
          throw new Error(`Could not load the expiry report (HTTP ${response.status}).`)
        }

        const rows: ExpiringBatch[] = await response.json()
        if (controller.signal.aborted) return

        setBatches(rows)
        setMessage(rows.length === 0 ? 'No stocked batches expire in this period.' : '')
      } catch (error) {
        if (controller.signal.aborted) return

        setMessage(
          error instanceof Error ? error.message : 'Could not load the expiry report.'
        )
      }
    }

    void loadReport()
    return () => controller.abort()
  }, [])

  return (
    <section aria-labelledby="expiry-report-heading">
      <h2 id="expiry-report-heading">Batches expiring within 30 days</h2>

      {message && <p role="status">{message}</p>}

      {batches.length > 0 && (
        <table>
          <thead>
            <tr>
              <th scope="col">SKU</th>
              <th scope="col">Generic name</th>
              <th scope="col">Batch number</th>
              <th scope="col">Expiry date</th>
              <th scope="col">Quantity</th>
              <th scope="col">Stock unit</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr key={JSON.stringify([batch.medicine__sku, batch.batch_number])}>
                <td>{batch.medicine__sku}</td>
                <td>{batch.medicine__generic_name}</td>
                <td>{batch.batch_number}</td>
                <td>{batch.expiry_date}</td>
                <td>{batch.quantity_on_hand}</td>
                <td>{batch.medicine__stock_unit || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}