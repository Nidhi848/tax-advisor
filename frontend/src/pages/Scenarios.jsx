import { useState, useEffect, Fragment } from 'react'
import {
  getProfile,
  scenarioSTR,
  scenarioCostSeg,
  scenarioCapitalGains,
  scenario401k,
  scenarioCompare,
} from '../lib/api'

const SCENARIO_TYPES = [
  { id: 'str', label: 'Short-Term Rental (STR)', icon: '🏠', description: 'Depreciation, STR loophole, passive loss rules' },
  { id: 'cost_seg', label: 'Cost Segregation', icon: '📐', description: 'Accelerated depreciation, Year 1 tax savings' },
  { id: 'capital_gains', label: 'Capital Gains Harvesting', icon: '📈', description: 'LTCG rates, $3k offset, carryforward' },
  { id: '401k', label: '401k / IRA Optimizer', icon: '💰', description: 'Contribution tax savings, Roth, SEP-IRA' },
]

const FILING_OPTIONS = [
  { value: 'single', label: 'Single' },
  { value: 'married_jointly', label: 'Married Filing Jointly' },
  { value: 'head_of_household', label: 'Head of Household' },
]

export default function Scenarios() {
  const [profile, setProfile] = useState(null)
  const [activeScenario, setActiveScenario] = useState(null)
  const [compareSelection, setCompareSelection] = useState([])
  const [compareResult, setCompareResult] = useState(null)
  const [compareLoading, setCompareLoading] = useState(false)

  useEffect(() => {
    getProfile().then(setProfile).catch(() => {})
  }, [])

  const handleCompare = async () => {
    if (compareSelection.length < 2) return
    setCompareLoading(true)
    setCompareResult(null)
    try {
      const scenarios = compareSelection.map((s) => ({
        name: s.name || s.type,
        modeler: s.type === 'str' ? 'str' : s.type === 'cost_seg' ? 'cost_seg' : s.type === 'capital_gains' ? 'capital_gains' : '401k',
        params: s.params || {},
      }))
      const data = await scenarioCompare(scenarios)
      setCompareResult(data)
    } catch (err) {
      setCompareResult({ error: err.message })
    } finally {
      setCompareLoading(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto p-8">
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-slate-800">Tax Scenario Modeling</h2>
        <p className="text-slate-500 text-sm mt-1">
          Model &quot;what if&quot; investment scenarios and see their tax impact. Use profile defaults or enter values.
        </p>
      </div>

      <div className="flex gap-8 flex-col lg:flex-row">
        <div className="w-full lg:w-72 flex-shrink-0 space-y-3">
          {SCENARIO_TYPES.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setActiveScenario(s.id)}
              className={`w-full text-left rounded-lg border-2 px-4 py-4 transition-colors ${
                activeScenario === s.id
                  ? 'border-slate-800 bg-slate-50'
                  : 'border-slate-200 hover:border-slate-400 bg-white'
              }`}
            >
              <span className="text-2xl block mb-1">{s.icon}</span>
              <span className="font-medium text-slate-800">{s.label}</span>
              <p className="text-xs text-slate-500 mt-1">{s.description}</p>
            </button>
          ))}
        </div>

        <div className="flex-1 min-w-0">
          {activeScenario === 'str' && (
            <STRForm profile={profile} onAddToCompare={(name, params) => setCompareSelection((prev) => [...prev.filter((x) => x.type !== 'str'), { type: 'str', name, params }])} />
          )}
          {activeScenario === 'cost_seg' && (
            <CostSegForm profile={profile} onAddToCompare={(name, params) => setCompareSelection((prev) => [...prev.filter((x) => x.type !== 'cost_seg'), { type: 'cost_seg', name, params }])} />
          )}
          {activeScenario === 'capital_gains' && (
            <CapitalGainsForm profile={profile} onAddToCompare={(name, params) => setCompareSelection((prev) => [...prev.filter((x) => x.type !== 'capital_gains'), { type: 'capital_gains', name, params }])} />
          )}
          {activeScenario === '401k' && (
            <RetirementForm profile={profile} onAddToCompare={(name, params) => setCompareSelection((prev) => [...prev.filter((x) => x.type !== '401k'), { type: '401k', name, params }])} />
          )}
          {!activeScenario && (
            <div className="text-slate-400 text-center py-12 rounded-lg border border-dashed border-slate-200">
              Click a scenario card to open the form.
            </div>
          )}
        </div>
      </div>

      <div className="mt-12 pt-8 border-t border-slate-200">
        <h3 className="font-semibold text-slate-800 mb-4">Compare Scenarios</h3>
        <p className="text-slate-500 text-sm mb-4">
          Run scenarios above and click &quot;Add to comparison&quot; for each. Then compare 2–4 of them below. Baseline (current situation) is always included.
        </p>
        {compareSelection.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <span className="text-sm text-slate-600">Scenarios to compare:</span>
            {compareSelection.map((s, i) => (
              <span key={i} className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-sm">
                <span>{s.name || s.type}</span>
                <button type="button" onClick={() => setCompareSelection((prev) => prev.filter((_, j) => j !== i))} className="text-slate-500 hover:text-slate-800" aria-label="Remove">×</button>
              </span>
            ))}
          </div>
        )}
        <button
          type="button"
          onClick={handleCompare}
          disabled={compareSelection.length < 2 || compareLoading}
          className="px-6 py-2.5 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {compareLoading ? 'Comparing...' : 'Compare Scenarios'}
        </button>

        {compareResult && (
          <CompareTableView result={compareResult} />
        )}
      </div>
    </div>
  )
}

const METRICS = [
  { key: 'gross_income', label: 'Gross Income', format: (v) => v != null ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—', higherBetter: null },
  { key: 'total_deductions', label: 'Total Deductions', format: (v) => v != null ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—', higherBetter: null },
  { key: 'taxable_income', label: 'Taxable Income', format: (v) => v != null ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—', higherBetter: null },
  { key: 'estimated_tax', label: 'Federal Tax Owed', format: (v) => v != null ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—', higherBetter: false },
  { key: 'effective_rate_pct', label: 'Effective Tax Rate', format: (v) => v != null ? `${v}%` : '—', higherBetter: false },
  { key: 'tax_savings_vs_baseline', label: 'Estimated Tax Savings vs Baseline', format: (v) => v != null && v > 0 ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—', higherBetter: true },
  { key: 'net_take_home', label: 'Net Take-Home', format: (v) => v != null ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: 2 })}` : '—', higherBetter: true },
]

function CompareTableView({ result }) {
  if (result.error) {
    return <p className="mt-6 text-red-600 text-sm">{result.error}</p>
  }

  const rows = result.comparison_table || []
  const baseline = rows[0]
  const baselineIndex = 0
  const bestIndex = rows.findIndex((r) => r.is_best_outcome)
  const maxSavings = Math.max(...rows.map((r) => Number(r.tax_savings_vs_baseline) || 0), 0)
  const bestCol = bestIndex >= 0 ? bestIndex : (maxSavings > 0 ? rows.findIndex((r) => (Number(r.tax_savings_vs_baseline) || 0) === maxSavings) : -1)

  const deltaColor = (metric, value, baselineVal) => {
    if (value == null || baselineVal == null || metric.higherBetter === null) return 'text-slate-500'
    const delta = Number(value) - Number(baselineVal)
    if (delta === 0) return 'text-slate-500'
    if (metric.higherBetter === true) return delta > 0 ? 'text-emerald-600' : 'text-red-600'
    return delta < 0 ? 'text-emerald-600' : 'text-red-600'
  }

  const deltaStr = (value, baselineVal, metric) => {
    if (value == null || baselineVal == null) return '—'
    const d = Number(value) - Number(baselineVal)
    if (d === 0) return '—'
    if (metric.key === 'effective_rate_pct') return `${d >= 0 ? '+' : ''}${d.toFixed(2)}%`
    return `${d >= 0 ? '+' : ''}$${Math.abs(d).toLocaleString('en-US', { minimumFractionDigits: 2 })}`
  }

  const exportCsv = () => {
    const headers = ['Metric', ...rows.map((r) => r.scenario_name)]
    const lines = [headers.join(',')]
    METRICS.forEach((m) => {
      lines.push([m.label, ...rows.map((r) => (r[m.key] != null ? r[m.key] : '')).join(',')])
      lines.push([`Δ vs Baseline (${m.label})`, ...rows.map((r, i) => (i === 0 ? '' : deltaStr(r[m.key], baseline?.[m.key], m))).join(',')])
    })
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = 'scenario-comparison.csv'
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const openPrint = () => {
    const win = window.open('', '_blank')
    if (!win) return
    const recommendation = rows.length > 0 && bestCol >= 0 && rows[bestCol]
      ? `Based on your numbers, ${rows[bestCol].scenario_name} saves you the most at $${Number(rows[bestCol].tax_savings_vs_baseline || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}${rows[bestCol].scenario_name.toLowerCase().includes('str') || rows[bestCol].scenario_name.toLowerCase().includes('rental') ? ' — but requires active management and professional verification.' : '.'}`
      : ''
    win.document.write(`
      <!DOCTYPE html><html><head><title>Scenario Comparison</title>
      <style>body{font-family:system-ui,sans-serif;padding:20px} table{border-collapse:collapse;width:100%} th,td{border:1px solid #ccc;padding:8px;text-align:right} th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:#fff} .best{background:#d1fae5} .baseline{background:#f1f5f9} .rec{margin-top:16px;padding:12px;background:#f1f5f9;border-radius:8px}</style></head><body>
      <h1>Tax Scenario Comparison</h1>
      <table><thead><tr><th>Metric</th>${rows.map((r) => `<th class="${r.is_best_outcome ? 'best' : r.scenario_name?.includes('Baseline') ? 'baseline' : ''}">${r.scenario_name}</th>`).join('')}</tr></thead><tbody>
      ${METRICS.map((m) => `<tr><td><strong>${m.label}</strong></td>${rows.map((r) => `<td>${m.format(r[m.key])}</td>`).join('')}</tr>`).join('')}
      </tbody></table>
      ${recommendation ? `<p class="rec">${recommendation}</p>` : ''}
      </body></html>`)
    win.document.close()
    win.focus()
    setTimeout(() => { win.print(); win.close() }, 250)
  }

  const tableContent = (
    <div className="mt-6 overflow-x-auto">
      <table className="w-full border border-slate-200 rounded-lg overflow-hidden text-sm compare-table">
        <thead>
          <tr className="bg-slate-100">
            <th className="text-left p-3 font-medium text-slate-700 sticky left-0 z-10 bg-slate-100 min-w-[180px]">Metric</th>
            {rows.map((row, colIndex) => (
              <th
                key={colIndex}
                className={`text-right p-3 font-medium min-w-[120px] ${
                  colIndex === baselineIndex ? 'bg-slate-200 text-slate-700' : colIndex === bestCol ? 'bg-emerald-100 text-emerald-800' : 'text-slate-700'
                }`}
              >
                {row.scenario_name}
                {row.is_best_outcome && <span className="ml-1 text-emerald-600">✓ Best</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {METRICS.map((metric) => (
            <Fragment key={metric.key}>
              <tr className="border-t border-slate-200">
                <td className="p-3 font-medium text-slate-800 sticky left-0 z-10 bg-white border-r border-slate-100">{metric.label}</td>
                {rows.map((row, colIndex) => (
                  <td
                    key={colIndex}
                    className={`text-right p-3 ${
                      colIndex === baselineIndex ? 'bg-slate-50' : colIndex === bestCol ? 'bg-emerald-50' : ''
                    }`}
                  >
                    {metric.format(row[metric.key])}
                  </td>
                ))}
              </tr>
              <tr className="border-t border-slate-100 bg-slate-50/50">
                <td className="p-2 pl-3 text-xs text-slate-500 sticky left-0 z-10 bg-slate-50/80">Δ vs Baseline</td>
                {rows.map((row, colIndex) => (
                  <td key={colIndex} className={`text-right p-2 text-xs ${colIndex === 0 ? 'text-slate-400' : deltaColor(metric, row[metric.key], baseline?.[metric.key])}`}>
                    {colIndex === 0 ? '—' : deltaStr(row[metric.key], baseline?.[metric.key], metric)}
                  </td>
                ))}
              </tr>
            </Fragment>
          ))}
        </tbody>
      </table>
      {rows.length > 0 && bestCol >= 0 && rows[bestCol] && (
        <p className="mt-4 p-4 rounded-lg bg-slate-100 text-slate-700 text-sm">
          Based on your numbers, <strong>{rows[bestCol].scenario_name}</strong> saves you the most at{' '}
          <strong>${Number(rows[bestCol].tax_savings_vs_baseline || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong>
          {rows[bestCol].scenario_name.toLowerCase().includes('str') || rows[bestCol].scenario_name.toLowerCase().includes('rental')
            ? ' — but requires active management and professional verification.'
            : '.'}
        </p>
      )}
    </div>
  )

  return (
    <div>
      <div className="flex flex-wrap gap-2 mt-4">
        <button type="button" onClick={exportCsv} className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm hover:bg-slate-50">
          Export CSV
        </button>
        <button type="button" onClick={openPrint} className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm hover:bg-slate-50">
          Print / PDF
        </button>
      </div>
      {tableContent}
    </div>
  )
}

function STRForm({ profile, onAddToCompare }) {
  const [form, setForm] = useState({
    property_purchase_price: '',
    gross_rental_income: '',
    w2_income: '',
    average_stay_days: '5',
    material_participation_hours: '800',
    annual_expenses: '',
    filing_status: 'single',
  })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [scenarioName, setScenarioName] = useState('')

  useEffect(() => {
    if (profile) {
      setForm((f) => ({
        ...f,
        w2_income: profile.annual_income != null ? String(profile.annual_income) : (profile.w2_data?.box_1_wages != null ? String(profile.w2_data.box_1_wages) : ''),
        filing_status: profile.filing_status || 'single',
      }))
    }
  }, [profile])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const params = {
        property_purchase_price: form.property_purchase_price ? Number(form.property_purchase_price) : undefined,
        gross_rental_income: form.gross_rental_income ? Number(form.gross_rental_income) : undefined,
        w2_income: form.w2_income ? Number(form.w2_income) : undefined,
        average_stay_days: form.average_stay_days ? Number(form.average_stay_days) : undefined,
        material_participation_hours: form.material_participation_hours ? Number(form.material_participation_hours) : undefined,
        annual_expenses: form.annual_expenses ? Number(form.annual_expenses) : undefined,
        filing_status: form.filing_status || undefined,
      }
      const data = await scenarioSTR(params)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const addToCompare = () => {
    const params = {
      property_purchase_price: form.property_purchase_price ? Number(form.property_purchase_price) : undefined,
      gross_rental_income: form.gross_rental_income ? Number(form.gross_rental_income) : undefined,
      w2_income: form.w2_income ? Number(form.w2_income) : undefined,
      average_stay_days: form.average_stay_days ? Number(form.average_stay_days) : undefined,
      material_participation_hours: form.material_participation_hours ? Number(form.material_participation_hours) : undefined,
      annual_expenses: form.annual_expenses ? Number(form.annual_expenses) : undefined,
      filing_status: form.filing_status || undefined,
    }
    onAddToCompare(scenarioName || 'STR scenario', params)
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6">
      <h3 className="font-semibold text-slate-800 mb-4">Short-Term Rental (STR)</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input type="text" placeholder="Scenario name (for comparison)" value={scenarioName} onChange={(e) => setScenarioName(e.target.value)} className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
        {['property_purchase_price', 'gross_rental_income', 'w2_income', 'annual_expenses'].map((key) => (
          <div key={key}>
            <label className="block text-sm font-medium text-slate-700 mb-1">{key.replace(/_/g, ' ')}</label>
            <input
              type="number"
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              className="w-full rounded-lg border border-slate-300 px-4 py-2"
            />
          </div>
        ))}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Average stay (days)</label>
            <input type="number" value={form.average_stay_days} onChange={(e) => setForm({ ...form, average_stay_days: e.target.value })} className="w-full rounded-lg border border-slate-300 px-4 py-2" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Material participation (hrs/yr)</label>
            <input type="number" value={form.material_participation_hours} onChange={(e) => setForm({ ...form, material_participation_hours: e.target.value })} className="w-full rounded-lg border border-slate-300 px-4 py-2" />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Filing status</label>
          <select value={form.filing_status} onChange={(e) => setForm({ ...form, filing_status: e.target.value })} className="w-full rounded-lg border border-slate-300 px-4 py-2">
            {FILING_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" disabled={loading} className="w-full py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50">
          {loading ? 'Modeling...' : 'Model This'}
        </button>
      </form>
      {result && (
        <>
          <div className="mt-6 pt-6 border-t border-slate-200">
            <h4 className="font-medium text-slate-800 mb-2">Calculation steps</h4>
            <ul className="space-y-1 text-sm text-slate-600">
              {(result.calculation_steps || []).map((s, i) => (
                <li key={i} className="flex justify-between gap-4">
                  <span>{s.step}</span>
                  <span className="font-medium">{typeof s.value === 'number' ? `$${s.value.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : String(s.value)}</span>
                </li>
              ))}
            </ul>
            {result.tax_impact?.estimated_tax_savings != null && result.tax_impact.estimated_tax_savings > 0 && (
              <p className="mt-4 text-lg font-semibold text-emerald-700">
                Tax Savings: ${result.tax_impact.estimated_tax_savings.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
            )}
            <p className="mt-2 text-sm text-slate-600">{result.summary}</p>
            {result.disclaimer && <p className="mt-3 text-xs text-slate-500">{result.disclaimer}</p>}
          </div>
          <button type="button" onClick={addToCompare} className="mt-4 text-sm text-slate-600 hover:text-slate-800 underline">
            Add to comparison
          </button>
        </>
      )}
    </div>
  )
}

function CostSegForm({ profile, onAddToCompare }) {
  const [form, setForm] = useState({ property_value: '', land_value: '', filing_status: 'single' })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [scenarioName, setScenarioName] = useState('')

  useEffect(() => {
    if (profile) setForm((f) => ({ ...f, filing_status: profile.filing_status || 'single' }))
  }, [profile])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const params = {
        property_value: form.property_value ? Number(form.property_value) : undefined,
        land_value: form.land_value ? Number(form.land_value) : undefined,
        filing_status: form.filing_status || undefined,
      }
      const data = await scenarioCostSeg(params)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const addToCompare = () => {
    onAddToCompare(scenarioName || 'Cost seg scenario', {
      property_value: form.property_value ? Number(form.property_value) : undefined,
      land_value: form.land_value ? Number(form.land_value) : undefined,
      filing_status: form.filing_status || undefined,
    })
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6">
      <h3 className="font-semibold text-slate-800 mb-4">Cost Segregation</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input type="text" placeholder="Scenario name (for comparison)" value={scenarioName} onChange={(e) => setScenarioName(e.target.value)} className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
        {['property_value', 'land_value'].map((key) => (
          <div key={key}>
            <label className="block text-sm font-medium text-slate-700 mb-1">{key.replace(/_/g, ' ')} ($)</label>
            <input type="number" value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className="w-full rounded-lg border border-slate-300 px-4 py-2" />
          </div>
        ))}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Filing status</label>
          <select value={form.filing_status} onChange={(e) => setForm({ ...form, filing_status: e.target.value })} className="w-full rounded-lg border border-slate-300 px-4 py-2">
            {FILING_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" disabled={loading} className="w-full py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50">
          {loading ? 'Modeling...' : 'Model This'}
        </button>
      </form>
      {result && (
        <>
          <div className="mt-6 pt-6 border-t border-slate-200">
            <h4 className="font-medium text-slate-800 mb-2">Calculation steps</h4>
            <ul className="space-y-1 text-sm text-slate-600">
              {(result.calculation_steps || []).map((s, i) => (
                <li key={i} className="flex justify-between gap-4">
                  <span>{s.step}</span>
                  <span className="font-medium">{typeof s.value === 'number' ? `$${s.value.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : String(s.value)}</span>
                </li>
              ))}
            </ul>
            {result.tax_impact?.estimated_tax_savings_yr1 != null && (
              <p className="mt-4 text-lg font-semibold text-emerald-700">
                Year 1 Tax Savings: ${result.tax_impact.estimated_tax_savings_yr1.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
            )}
            <p className="mt-2 text-sm text-slate-600">{result.summary}</p>
            {result.disclaimer && <p className="mt-3 text-xs text-slate-500">{result.disclaimer}</p>}
          </div>
          <button type="button" onClick={addToCompare} className="mt-4 text-sm text-slate-600 hover:text-slate-800 underline">
            Add to comparison
          </button>
        </>
      )}
    </div>
  )
}

function CapitalGainsForm({ profile, onAddToCompare }) {
  const [form, setForm] = useState({ gains: '', losses: '', income: '', filing_status: 'single' })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [scenarioName, setScenarioName] = useState('')

  useEffect(() => {
    if (profile) {
      setForm((f) => ({
        ...f,
        income: profile.annual_income != null ? String(profile.annual_income) : (profile.w2_data?.box_1_wages != null ? String(profile.w2_data.box_1_wages) : ''),
        filing_status: profile.filing_status || 'single',
      }))
    }
  }, [profile])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const params = {
        gains: form.gains ? Number(form.gains) : undefined,
        losses: form.losses ? Number(form.losses) : undefined,
        income: form.income ? Number(form.income) : undefined,
        filing_status: form.filing_status || undefined,
      }
      const data = await scenarioCapitalGains(params)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const addToCompare = () => {
    onAddToCompare(scenarioName || 'Capital gains scenario', {
      gains: form.gains ? Number(form.gains) : undefined,
      losses: form.losses ? Number(form.losses) : undefined,
      income: form.income ? Number(form.income) : undefined,
      filing_status: form.filing_status || undefined,
    })
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6">
      <h3 className="font-semibold text-slate-800 mb-4">Capital Gains Harvesting</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input type="text" placeholder="Scenario name (for comparison)" value={scenarioName} onChange={(e) => setScenarioName(e.target.value)} className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
        {['gains', 'losses', 'income'].map((key) => (
          <div key={key}>
            <label className="block text-sm font-medium text-slate-700 mb-1">{key} ($)</label>
            <input type="number" value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} className="w-full rounded-lg border border-slate-300 px-4 py-2" />
          </div>
        ))}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Filing status</label>
          <select value={form.filing_status} onChange={(e) => setForm({ ...form, filing_status: e.target.value })} className="w-full rounded-lg border border-slate-300 px-4 py-2">
            {FILING_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" disabled={loading} className="w-full py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50">
          {loading ? 'Modeling...' : 'Model This'}
        </button>
      </form>
      {result && (
        <>
          <div className="mt-6 pt-6 border-t border-slate-200">
            <h4 className="font-medium text-slate-800 mb-2">Calculation steps</h4>
            <ul className="space-y-1 text-sm text-slate-600">
              {(result.calculation_steps || []).map((s, i) => (
                <li key={i} className="flex justify-between gap-4">
                  <span>{s.step}</span>
                  <span className="font-medium">{typeof s.value === 'number' ? (s.value >= 0 ? `$${s.value.toLocaleString('en-US', { minimumFractionDigits: 2 })}` : `-$${Math.abs(s.value).toLocaleString('en-US', { minimumFractionDigits: 2 })}`) : String(s.value)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-sm text-slate-600">{result.summary}</p>
          </div>
          <button type="button" onClick={addToCompare} className="mt-4 text-sm text-slate-600 hover:text-slate-800 underline">
            Add to comparison
          </button>
        </>
      )}
    </div>
  )
}

function RetirementForm({ profile, onAddToCompare }) {
  const [form, setForm] = useState({ income: '', filing_status: 'single', age: '', self_employment_income: '' })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [scenarioName, setScenarioName] = useState('')

  useEffect(() => {
    if (profile) {
      setForm((f) => ({
        ...f,
        income: profile.annual_income != null ? String(profile.annual_income) : (profile.w2_data?.box_1_wages != null ? String(profile.w2_data.box_1_wages) : ''),
        filing_status: profile.filing_status || 'single',
        age: profile.age != null ? String(profile.age) : '',
        self_employment_income: profile.self_employment_income != null ? String(profile.self_employment_income) : '',
      }))
    }
  }, [profile])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const params = {
        income: form.income ? Number(form.income) : undefined,
        filing_status: form.filing_status || undefined,
        age: form.age ? Number(form.age) : undefined,
        self_employment_income: form.self_employment_income ? Number(form.self_employment_income) : undefined,
      }
      const data = await scenario401k(params)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const addToCompare = () => {
    onAddToCompare(scenarioName || '401k scenario', {
      income: form.income ? Number(form.income) : undefined,
      filing_status: form.filing_status || undefined,
      age: form.age ? Number(form.age) : undefined,
      self_employment_income: form.self_employment_income ? Number(form.self_employment_income) : undefined,
    })
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6">
      <h3 className="font-semibold text-slate-800 mb-4">401k / IRA Optimizer</h3>
      <form onSubmit={handleSubmit} className="space-y-4">
        <input type="text" placeholder="Scenario name (for comparison)" value={scenarioName} onChange={(e) => setScenarioName(e.target.value)} className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
        {['income', 'age', 'self_employment_income'].map((key) => (
          <div key={key}>
            <label className="block text-sm font-medium text-slate-700 mb-1">{key.replace(/_/g, ' ')}</label>
            <input type="number" value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} placeholder={key === 'age' ? 'e.g. 52' : ''} className="w-full rounded-lg border border-slate-300 px-4 py-2" />
          </div>
        ))}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Filing status</label>
          <select value={form.filing_status} onChange={(e) => setForm({ ...form, filing_status: e.target.value })} className="w-full rounded-lg border border-slate-300 px-4 py-2">
            {FILING_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button type="submit" disabled={loading} className="w-full py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50">
          {loading ? 'Modeling...' : 'Model This'}
        </button>
      </form>
      {result && (
        <>
          <div className="mt-6 pt-6 border-t border-slate-200">
            <h4 className="font-medium text-slate-800 mb-2">Tax impact</h4>
            {(result.calculation_steps || []).map((s, i) => (
              <div key={i} className="text-sm text-slate-600 py-1">
                {s.step}: {Array.isArray(s.value) ? s.value.map((v) => `$${v.contribution?.toLocaleString()}: save $${v.tax_savings?.toLocaleString()}`).join('; ') : String(s.value)}
              </div>
            ))}
            <p className="mt-2 text-sm text-slate-600">{result.summary}</p>
          </div>
          <button type="button" onClick={addToCompare} className="mt-4 text-sm text-slate-600 hover:text-slate-800 underline">
            Add to comparison
          </button>
        </>
      )}
    </div>
  )
}
