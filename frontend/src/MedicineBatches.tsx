import { t } from './language'
import { useEffect, useState } from 'react'

type Batch = {
  id: number
  batch_number: string
  expiry_date: string
  quantity_on_hand: number
}

type MedicineBatchesProps = {
  medicineId: number
  stockUnit: string
}

function BatchList({ medicineId, stockUnit }: MedicineBatchesProps) {
  const [batches, setBatches] = useState<Batch[]>([])
  const [message, setMessage] = useState('Loading batches…')

  useEffect(() => {
    const controller = new AbortController()

    async function loadBatches() {
      try {
        const response = await fetch(`/api/medicines/${medicineId}/batches/`, {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        })

        if (response.status === 401 || response.status === 403) {
          throw new Error('Sign in to Django Admin as staff, then reopen the batches.')
        }

        if (!response.ok) {
          throw new Error(`Could not load batches (HTTP ${response.status}).`)
        }

        const data: { batches: Batch[] } = await response.json()
        if (controller.signal.aborted) return

        setBatches(data.batches)
        setMessage(data.batches.length === 0 ? 'No batches recorded.' : '')
      } catch (error) {
        if (controller.signal.aborted) return
        setMessage(error instanceof Error ? error.message : 'Could not load batches.')
      }
    }

    void loadBatches()
    return () => controller.abort()
  }, [medicineId])

  if (message) return <p role="status">{t(message)}</p>

  return (
    <table aria-label="Stock batches">
      <thead>
        <tr>
          <th scope="col">{t("Batch number")}</th>
          <th scope="col">{t("Expiry date")}</th>
          <th scope="col">{stockUnit ? `${t('Quantity')} (${t(stockUnit)})` : t("Quantity")}</th>
        </tr>
      </thead>
      <tbody>
        {batches.map((batch) => (
          <tr key={batch.id}>
            <td>{batch.batch_number}</td>
            <td>{batch.expiry_date}</td>
            <td>{batch.quantity_on_hand}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function MedicineBatches({ medicineId, stockUnit }: MedicineBatchesProps) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <button
        type="button"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
      >
        {isOpen ? t("Hide batches") : t("View batches")}
      </button>
      {isOpen && <BatchList medicineId={medicineId} stockUnit={stockUnit} />}
    </>
  )
}