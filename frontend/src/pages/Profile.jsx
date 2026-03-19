import { useState, useEffect } from 'react'
import { getProfile, updateProfile } from '../lib/api'

const FILING_OPTIONS = [
  { value: 'single', label: 'Single' },
  { value: 'married_jointly', label: 'Married Filing Jointly' },
  { value: 'head_of_household', label: 'Head of Household' },
]

export default function Profile() {
  const [filingStatus, setFilingStatus] = useState('single')
  const [stateValue, setStateValue] = useState('')
  const [dependents, setDependents] = useState(0)
  const [annualIncome, setAnnualIncome] = useState('')
  const [age, setAge] = useState('')
  const [selfEmploymentIncome, setSelfEmploymentIncome] = useState('')
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    getProfile()
      .then((p) => {
        setProfile(p)
        setFilingStatus(p.filing_status || 'single')
        setStateValue(p.state || '')
        setDependents(p.dependents ?? 0)
        setAnnualIncome(p.annual_income != null ? String(p.annual_income) : '')
        setAge(p.age != null ? String(p.age) : '')
        setSelfEmploymentIncome(p.self_employment_income != null ? String(p.self_employment_income) : '')
      })
      .catch(() => setMessage('Failed to load profile'))
      .finally(() => setLoading(false))
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setMessage('')
    setSaving(true)
    try {
      await updateProfile({
        filing_status: filingStatus,
        state: stateValue || null,
        dependents,
        annual_income: annualIncome === '' ? null : Number(annualIncome),
        age: age === '' ? null : Number(age),
        self_employment_income: selfEmploymentIncome === '' ? null : Number(selfEmploymentIncome),
      })
      const updated = await getProfile()
      setProfile(updated)
      setMessage('Profile saved.')
    } catch (err) {
      setMessage(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-8">
        <p className="text-slate-500">Loading...</p>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto p-8">
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-slate-800">Profile</h2>
        <p className="text-slate-500 text-sm mt-1">
          Set your filing status and other details
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
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
            State of Residence
          </label>
          <input
            type="text"
            value={stateValue}
            onChange={(e) => setStateValue(e.target.value)}
            placeholder="e.g. CA"
            className="w-full rounded-lg border border-slate-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Number of Dependents
          </label>
          <input
            type="number"
            min="0"
            value={dependents}
            onChange={(e) => setDependents(parseInt(e.target.value, 10) || 0)}
            className="w-full rounded-lg border border-slate-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Annual Income ($)
          </label>
          <input
            type="number"
            min="0"
            value={annualIncome}
            onChange={(e) => setAnnualIncome(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Age (for 401k catch-up, etc.)
          </label>
          <input
            type="number"
            min="0"
            max="120"
            value={age}
            onChange={(e) => setAge(e.target.value)}
            placeholder="Optional"
            className="w-full rounded-lg border border-slate-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Self-employment income ($)
          </label>
          <input
            type="number"
            min="0"
            value={selfEmploymentIncome}
            onChange={(e) => setSelfEmploymentIncome(e.target.value)}
            placeholder="Optional — for SEP-IRA"
            className="w-full rounded-lg border border-slate-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
        </div>
        {message && (
          <div className={`text-sm ${message.includes('Failed') ? 'text-red-600' : 'text-green-600'}`}>
            {message}
          </div>
        )}
        <button
          type="submit"
          disabled={saving}
          className="w-full py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save Profile'}
        </button>
      </form>

      {profile && (
        <div className="mt-8 space-y-4 text-sm">
          <div className="text-slate-500">
            <span className="font-medium text-slate-700">Profile last updated:</span>{' '}
            {profile.last_updated
              ? new Date(profile.last_updated).toLocaleString()
              : 'Not set'}
          </div>

          <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-2">
            <div className="font-semibold text-slate-800">Data on file</div>
            <div className="flex items-center justify-between">
              <span>W-2 data:</span>
              <div className="flex items-center gap-3">
                <span className="text-slate-700">
                  {profile.w2_data ? 'On file' : 'None'}
                </span>
                {profile.w2_data && (
                  <button
                    type="button"
                    onClick={async () => {
                      setSaving(true)
                      try {
                        const updated = await updateProfile({ w2_data: null })
                        setProfile(updated)
                        setMessage('Cleared W-2 data.')
                      } catch (err) {
                        setMessage(err.message)
                      } finally {
                        setSaving(false)
                      }
                    }}
                    className="text-xs text-slate-600 hover:text-slate-900 underline"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span>1099 data:</span>
              <div className="flex items-center gap-3">
                <span className="text-slate-700">
                  {profile.ten99_data ? 'On file' : 'None'}
                </span>
                {profile.ten99_data && (
                  <button
                    type="button"
                    onClick={async () => {
                      setSaving(true)
                      try {
                        const updated = await updateProfile({ ten99_data: null })
                        setProfile(updated)
                        setMessage('Cleared 1099 data.')
                      } catch (err) {
                        setMessage(err.message)
                      } finally {
                        setSaving(false)
                      }
                    }}
                    className="text-xs text-slate-600 hover:text-slate-900 underline"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
          </div>

          <p className="text-xs text-slate-500">
            Privacy: Your profile is stored locally on your machine in <code>user_profile.json</code>{' '}
            and is never uploaded to any external server beyond this app&apos;s backend.
          </p>
        </div>
      )}
    </div>
  )
}
