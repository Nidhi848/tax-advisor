const API_BASE = 'http://localhost:8000'

export async function calculateTax(income, filingStatus, deductions = null) {
  const res = await fetch(`${API_BASE}/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      income: Number(income),
      filing_status: filingStatus,
      ...(deductions != null && deductions !== '' ? { deductions: Number(deductions) } : {}),
    }),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Calculation failed')
  return res.json()
}

export async function submitManualDocument(documentType, data) {
  const body = documentType === 'w2'
    ? { document_type: 'w2', w2: data }
    : { document_type: '1099', form_1099: data }
  const res = await fetch(`${API_BASE}/document/manual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Submission failed')
  return res.json()
}

export async function submitPdfDocument(file, documentType) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}/document/pdf?document_type=${documentType}`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'PDF processing failed')
  return res.json()
}

export async function streamChat(message, conversationHistory, onChunk, onDone, onProfileUpdate, conversationId = null) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory,
      ...(conversationId ? { conversation_id: conversationId } : {}),
    }),
  })
  if (!res.ok) throw new Error('Chat failed')
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finished = false
  const scenarioResults = []
  let newConversationId = null
  const onDoneWithMeta = (scenarioResultsArg) => {
    onDone?.(scenarioResultsArg, newConversationId)
  }
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6))
          if (data.type === 'text' && data.content) onChunk(data.content)
          if (data.type === 'profile_update' && onProfileUpdate) onProfileUpdate(data)
          if (data.type === 'scenario_result') scenarioResults.push(data)
          if (data.type === 'conversation_id' && data.id) newConversationId = data.id
          if (data.type === 'done') {
            onDoneWithMeta(scenarioResults)
            finished = true
          }
        } catch (_) {}
      }
    }
  }
  if (!finished) onDoneWithMeta(scenarioResults)
}

export async function listConversations() {
  const res = await fetch(`${API_BASE}/conversations`)
  if (!res.ok) throw new Error('Failed to list conversations')
  return res.json()
}

export async function getConversation(id) {
  const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(id)}`)
  if (!res.ok) throw new Error('Failed to load conversation')
  return res.json()
}

export async function deleteConversation(id) {
  const res = await fetch(`${API_BASE}/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete conversation')
  return res.json()
}

export async function getProfile() {
  const res = await fetch(`${API_BASE}/profile`)
  if (!res.ok) throw new Error('Failed to load profile')
  return res.json()
}

export async function updateProfile(profile) {
  const res = await fetch(`${API_BASE}/profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  })
  if (!res.ok) throw new Error('Failed to update profile')
  return res.json()
}

// Scenario endpoints
export async function scenarioSTR(params = {}) {
  const res = await fetch(`${API_BASE}/scenario/str`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'STR scenario failed')
  return res.json()
}

export async function scenarioCostSeg(params = {}) {
  const res = await fetch(`${API_BASE}/scenario/cost-seg`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Cost seg scenario failed')
  return res.json()
}

export async function scenarioCapitalGains(params = {}) {
  const res = await fetch(`${API_BASE}/scenario/capital-gains`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Capital gains scenario failed')
  return res.json()
}

export async function scenario401k(params = {}) {
  const res = await fetch(`${API_BASE}/scenario/401k`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) throw new Error((await res.json()).detail || '401k scenario failed')
  return res.json()
}

export async function scenarioCompare(scenarios) {
  const res = await fetch(`${API_BASE}/scenario/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenarios }),
  })
  if (!res.ok) throw new Error((await res.json()).detail || 'Compare failed')
  return res.json()
}
