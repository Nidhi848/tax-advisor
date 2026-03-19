import { useState } from 'react'
import { submitManualDocument, submitPdfDocument } from '../lib/api'

const FILING_OPTIONS = [
  { value: 'single', label: 'Single' },
  { value: 'married_jointly', label: 'Married Filing Jointly' },
  { value: 'head_of_household', label: 'Head of Household' },
]

export default function DocumentEntry() {
  const [activeTab, setActiveTab] = useState('manual')

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-slate-800">Document Entry</h2>
        <p className="text-slate-500 text-sm mt-1">
          Enter W-2 or 1099 data manually or upload a PDF
        </p>
      </div>

      <div className="flex gap-2 border-b border-slate-200 mb-6">
        <button
          onClick={() => setActiveTab('manual')}
          className={`px-4 py-2 font-medium border-b-2 -mb-px transition-colors ${
            activeTab === 'manual'
              ? 'border-slate-800 text-slate-800'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          Manual Entry
        </button>
        <button
          onClick={() => setActiveTab('pdf')}
          className={`px-4 py-2 font-medium border-b-2 -mb-px transition-colors ${
            activeTab === 'pdf'
              ? 'border-slate-800 text-slate-800'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          PDF Upload
        </button>
      </div>

      {activeTab === 'manual' && <ManualEntryForm />}
      {activeTab === 'pdf' && <PdfUploadForm />}
    </div>
  )
}

function ManualEntryForm() {
  const [documentType, setDocumentType] = useState('w2')
  const [w2, setW2] = useState({
    box_1_wages: '',
    box_2_federal_withheld: '',
    box_16_state_wages: '',
    box_17_state_withheld: '',
    employer_name: '',
  })
  const [form1099, setForm1099] = useState({
    total_income: '',
    federal_withheld: '0',
    payer_name: '',
  })
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const data = documentType === 'w2'
        ? await submitManualDocument(documentType, {
            box_1_wages: Number(w2.box_1_wages),
            box_2_federal_withheld: Number(w2.box_2_federal_withheld),
            box_16_state_wages: Number(w2.box_16_state_wages),
            box_17_state_withheld: Number(w2.box_17_state_withheld),
            employer_name: w2.employer_name || '',
          })
        : await submitManualDocument(documentType, {
            total_income: Number(form1099.total_income),
            federal_withheld: Number(form1099.federal_withheld || 0),
            payer_name: form1099.payer_name || '',
          })
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">Form Type</label>
        <select
          value={documentType}
          onChange={(e) => setDocumentType(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-4 py-2"
        >
          <option value="w2">W-2</option>
          <option value="1099">1099</option>
        </select>
      </div>

      {documentType === 'w2' && (
        <div className="space-y-4">
          <h3 className="font-medium text-slate-700">W-2 Fields</h3>
          {[
            { key: 'box_1_wages', label: 'Box 1: Wages, tips, other compensation' },
            { key: 'box_2_federal_withheld', label: 'Box 2: Federal income tax withheld' },
            { key: 'box_16_state_wages', label: 'Box 16: State wages' },
            { key: 'box_17_state_withheld', label: 'Box 17: State income tax withheld' },
          ].map(({ key, label }) => (
            <div key={key}>
              <label className="block text-sm text-slate-600 mb-1">{label}</label>
              <input
                type="number"
                value={w2[key]}
                onChange={(e) => setW2({ ...w2, [key]: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-4 py-2"
                required
              />
            </div>
          ))}
          <div>
            <label className="block text-sm text-slate-600 mb-1">
              Employer name <span className="text-amber-600">(stays local, never sent to API)</span>
            </label>
            <input
              type="text"
              value={w2.employer_name}
              onChange={(e) => setW2({ ...w2, employer_name: e.target.value })}
              placeholder="Optional"
              className="w-full rounded-lg border border-slate-300 px-4 py-2"
            />
          </div>
        </div>
      )}

      {documentType === '1099' && (
        <div className="space-y-4">
          <h3 className="font-medium text-slate-700">1099 Fields</h3>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Total income received</label>
            <input
              type="number"
              value={form1099.total_income}
              onChange={(e) => setForm1099({ ...form1099, total_income: e.target.value })}
              className="w-full rounded-lg border border-slate-300 px-4 py-2"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">Federal tax withheld (0 if none)</label>
            <input
              type="number"
              value={form1099.federal_withheld}
              onChange={(e) => setForm1099({ ...form1099, federal_withheld: e.target.value })}
              className="w-full rounded-lg border border-slate-300 px-4 py-2"
            />
          </div>
          <div>
            <label className="block text-sm text-slate-600 mb-1">
              Payer name <span className="text-amber-600">(stays local, never sent to API)</span>
            </label>
            <input
              type="text"
              value={form1099.payer_name}
              onChange={(e) => setForm1099({ ...form1099, payer_name: e.target.value })}
              placeholder="Optional"
              className="w-full rounded-lg border border-slate-300 px-4 py-2"
            />
          </div>
        </div>
      )}

      {error && <div className="text-red-600 text-sm">{error}</div>}
      <button
        type="submit"
        disabled={loading}
        className="w-full py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
      >
        {loading ? 'Submitting...' : 'Submit'}
      </button>

      {result && (
        <div className="p-6 bg-slate-50 rounded-lg border border-slate-200 space-y-4">
          <h3 className="font-semibold text-slate-800">Result</h3>
          <p className="text-sm text-slate-600">
            Estimated tax owed: ${result.tax_calculation?.tax_owed?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </p>
          <p className="text-sm">
            {result.outcome === 'refund' ? (
              <span className="text-green-700">
                You are likely due a refund of ~${result.refund_or_owed?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            ) : (
              <span className="text-amber-700">
                You may owe ~${(-result.refund_or_owed)?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            )}
          </p>
        </div>
      )}
    </form>
  )
}

function PdfUploadForm() {
  const [documentType, setDocumentType] = useState('w2')
  const [file, setFile] = useState(null)
  const [confirmed, setConfirmed] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file || !confirmed) return
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const data = await submitPdfDocument(file, documentType)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <p className="text-amber-800 text-sm font-medium">
          Your document contents will be sent to Anthropic&apos;s API for processing. Use manual entry to keep your data local.
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">Form Type</label>
        <select
          value={documentType}
          onChange={(e) => setDocumentType(e.target.value)}
          className="w-full rounded-lg border border-slate-300 px-4 py-2"
        >
          <option value="w2">W-2</option>
          <option value="1099">1099</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700 mb-2">PDF File</label>
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="w-full rounded-lg border border-slate-300 px-4 py-2"
        />
      </div>

      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
          className="rounded border-slate-300"
        />
        <span className="text-sm text-slate-700">
          I understand my document will be sent to Anthropic&apos;s API
        </span>
      </label>

      {error && <div className="text-red-600 text-sm">{error}</div>}
      <button
        type="submit"
        disabled={loading || !file || !confirmed}
        className="w-full py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Processing...' : 'Upload & Parse'}
      </button>

      {result && (
        <div className="p-6 bg-slate-50 rounded-lg border border-slate-200 space-y-4">
          <h3 className="font-semibold text-slate-800">Result</h3>
          {result.warning && (
            <p className="text-sm text-amber-700">{result.warning}</p>
          )}
          <p className="text-sm text-slate-600">
            Estimated tax owed: ${result.tax_calculation?.tax_owed?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
          </p>
          <p className="text-sm">
            {result.outcome === 'refund' ? (
              <span className="text-green-700">
                You are likely due a refund of ~${result.refund_or_owed?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            ) : (
              <span className="text-amber-700">
                You may owe ~${(-result.refund_or_owed)?.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
            )}
          </p>
        </div>
      )}
    </form>
  )
}
