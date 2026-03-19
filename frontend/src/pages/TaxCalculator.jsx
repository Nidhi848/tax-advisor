import { useState } from 'react'
import { calculateTax } from '../lib/api'

const FILING_OPTIONS = [
  { value: 'single', label: 'Single' },
  { value: 'married_jointly', label: 'Married Filing Jointly' },
  { value: 'head_of_household', label: 'Head of Household' },
]

export default function TaxCalculator() {
  const [income, setIncome] = useState('')
  const [filingStatus, setFilingStatus] = useState('single')
  const [deductions, setDeductions] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const data = await calculateTax(
        income,
        filingStatus,
        deductions || null
      )
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-slate-800">Tax Calculator</h2>
        <p className="text-slate-500 text-sm mt-1">
          Estimate your 2025 federal income tax
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Gross Income ($)
          </label>
          <input
            type="number"
            value={income}
            onChange={(e) => setIncome(e.target.value)}
            placeholder="85000"
            className="w-full rounded-lg border border-slate-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Filing Status
          </label>
          <select
            value={filingStatus}
            onChange={(e) => setFilingStatus(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
          >
            {FILING_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Deductions ($) — optional, leave blank for standard deduction
          </label>
          <input
            type="number"
            value={deductions}
            onChange={(e) => setDeductions(e.target.value)}
            placeholder="Standard deduction used if blank"
            className="w-full rounded-lg border border-slate-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
        </div>
        {error && (
          <div className="text-red-600 text-sm">{error}</div>
        )}
        <button
          type="submit"
          disabled={loading}
          className="w-full py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
        >
          {loading ? 'Calculating...' : 'Calculate'}
        </button>
      </form>

      {result && (
        <div className="mt-8 p-6 bg-slate-50 rounded-lg border border-slate-200">
          <h3 className="font-semibold text-slate-800 mb-4">Tax Breakdown</h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-600">Gross Income</dt>
              <dd className="font-medium">${result.gross_income?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Deduction</dt>
              <dd className="font-medium">${result.deduction?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Taxable Income</dt>
              <dd className="font-medium">${result.taxable_income?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</dd>
            </div>
            <div className="flex justify-between pt-2 border-t border-slate-200">
              <dt className="text-slate-700 font-medium">Estimated Tax Owed</dt>
              <dd className="font-semibold text-slate-800">${result.tax_owed?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-600">Effective Rate</dt>
              <dd className="font-medium">{result.effective_tax_rate}</dd>
            </div>
          </dl>
        </div>
      )}
    </div>
  )
}
