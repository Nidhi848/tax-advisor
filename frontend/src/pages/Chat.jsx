import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  streamChat,
  getProfile,
  listConversations,
  getConversation,
  deleteConversation,
} from '../lib/api'

const CONVERSATION_ID_KEY = 'tax_advisor_conversation_id'

function groupByTime(conversations) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterday = today - 86400000
  const groups = { Today: [], Yesterday: [], Earlier: [] }
  conversations.forEach((c) => {
    const t = new Date(c.timestamp).getTime()
    if (t >= today) groups.Today.push(c)
    else if (t >= yesterday) groups.Yesterday.push(c)
    else groups.Earlier.push(c)
  })
  return groups
}

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [profile, setProfile] = useState(null)
  const [profileNotice, setProfileNotice] = useState('')
  const [conversationId, setConversationId] = useState(() => localStorage.getItem(CONVERSATION_ID_KEY))
  const [conversations, setConversations] = useState([])
  const [historyOpen, setHistoryOpen] = useState(true)
  const [showWelcome, setShowWelcome] = useState(true)
  const [showHelp, setShowHelp] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  const hasProfile = profile && (
    profile.annual_income != null ||
    profile.w2_data ||
    profile.ten99_data ||
    (profile.filing_status && profile.filing_status !== 'single') ||
    profile.dependents > 0
  )

  const refreshConversations = () => {
    listConversations().then(setConversations).catch(() => setConversations([]))
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  useEffect(() => {
    getProfile().then(setProfile).catch(() => {})
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoadingHistory(true)
    Promise.all([listConversations(), conversationId ? getConversation(conversationId).catch(() => null) : Promise.resolve(null)])
      .then(([list, conv]) => {
        if (cancelled) return
        setConversations(list)
        if (conv && conv.messages) setMessages(conv.messages)
        else {
          if (conversationId && !conv) {
            setConversationId(null)
            localStorage.removeItem(CONVERSATION_ID_KEY)
          }
          setMessages([])
        }
        setShowWelcome(list.length === 0 && !hasProfile)
      })
      .catch(() => { if (!cancelled) setConversations([]) })
      .finally(() => { if (!cancelled) setLoadingHistory(false) })
    return () => { cancelled = true }
  }, [conversationId])

  useEffect(() => {
    if (conversations.length === 0 && profile && !hasProfile) setShowWelcome(true)
    if (conversations.length > 0 || hasProfile) setShowWelcome(false)
  }, [conversations.length, hasProfile, profile])

  const profileSummary = (() => {
    if (!profile) return ''
    const parts = []
    if (profile.filing_status) parts.push(profile.filing_status.replace('_', ' '))
    if (profile.annual_income != null) parts.push(`$${profile.annual_income.toLocaleString('en-US')}`)
    if (profile.state) parts.push(profile.state)
    return parts.join(' · ')
  })()

  const handleNewChat = () => {
    setConversationId(null)
    setMessages([])
    localStorage.removeItem(CONVERSATION_ID_KEY)
    setShowWelcome(false)
    inputRef.current?.focus()
  }

  const handleSelectConversation = (id) => {
    setConversationId(id)
    localStorage.setItem(CONVERSATION_ID_KEY, id)
    getConversation(id).then((c) => {
      if (c && c.messages) setMessages(c.messages)
    }).catch(() => {})
  }

  const handleDeleteConversation = (e, id) => {
    e.stopPropagation()
    if (!window.confirm('Delete this conversation?')) return
    deleteConversation(id).then(() => {
      refreshConversations()
      if (conversationId === id) {
        handleNewChat()
      }
    }).catch(() => {})
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || isLoading) return

    setInput('')
    const userMsg = { role: 'user', content: text }
    setMessages((m) => [...m, userMsg])
    setIsLoading(true)
    setStreamingContent('')

    const conversationHistory = messages.map((m) => ({
      role: m.role,
      content: typeof m.content === 'string' ? m.content : m.content,
    }))

    try {
      let fullContent = ''
      await streamChat(
        text,
        conversationHistory,
        (chunk) => {
          fullContent += chunk
          setStreamingContent(fullContent)
        },
        (scenarioResults = [], newConversationId) => {
          setMessages((m) => [...m, { role: 'assistant', content: fullContent, scenarioResults: scenarioResults?.length ? scenarioResults : undefined }])
          setStreamingContent('')
          setIsLoading(false)
          if (newConversationId) {
            setConversationId(newConversationId)
            localStorage.setItem(CONVERSATION_ID_KEY, newConversationId)
            refreshConversations()
          }
        },
        (evt) => {
          if (evt?.field) {
            setProfileNotice(`Profile updated: ${evt.field} → ${String(evt.value)}`)
            getProfile().then(setProfile).catch(() => {})
            setTimeout(() => setProfileNotice(''), 4000)
          }
        },
        conversationId || undefined
      )
    } catch (err) {
      setMessages((m) => [...m, { role: 'assistant', content: `Error: ${err.message}` }])
      setIsLoading(false)
      setStreamingContent('')
    }
    inputRef.current?.focus()
  }

  const handleSuggestion = (prefillText, nav) => {
    if (nav) {
      navigate(nav)
      return
    }
    setInput(prefillText)
    setShowWelcome(false)
    inputRef.current?.focus()
  }

  const grouped = groupByTime(conversations)
  const showGettingStarted = showWelcome || showHelp

  return (
    <div className="flex h-full min-h-0">
      {/* Chat History panel */}
      <div className="w-64 flex-shrink-0 border-r border-slate-200 bg-slate-50 flex flex-col">
        <div className="p-3 border-b border-slate-200">
          <button
            type="button"
            onClick={handleNewChat}
            className="w-full py-2 px-3 rounded-lg bg-slate-800 text-white text-sm font-medium hover:bg-slate-700"
          >
            New Chat
          </button>
        </div>
        <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
          <button
            type="button"
            onClick={() => setHistoryOpen((o) => !o)}
            className="flex items-center justify-between w-full px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-100"
          >
            <span>Chat History</span>
            <span className="text-slate-400">{historyOpen ? '▼' : '▶'}</span>
          </button>
          {historyOpen && (
            <div className="flex-1 overflow-y-auto px-2 pb-2">
              {loadingHistory ? (
                <p className="text-xs text-slate-500 px-2">Loading...</p>
              ) : (
                <>
                  {['Today', 'Yesterday', 'Earlier'].map((label) => (
                    grouped[label].length > 0 && (
                      <div key={label} className="mb-3">
                        <div className="text-xs font-medium text-slate-500 px-2 py-1">{label}</div>
                        {grouped[label].map((c) => (
                          <button
                            key={c.id}
                            type="button"
                            onClick={() => handleSelectConversation(c.id)}
                            className={`w-full text-left px-2 py-2 rounded-lg text-sm truncate flex items-center gap-2 group ${
                              conversationId === c.id ? 'bg-slate-200 text-slate-900' : 'hover:bg-slate-100 text-slate-700'
                            }`}
                          >
                            <span className="flex-1 min-w-0 truncate">{c.preview || 'New conversation'}</span>
                            <span
                              role="button"
                              tabIndex={0}
                              onClick={(e) => handleDeleteConversation(e, c.id)}
                              onKeyDown={(e) => e.key === 'Enter' && handleDeleteConversation(e, c.id)}
                              className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-600 flex-shrink-0"
                              aria-label="Delete"
                            >
                              ×
                            </span>
                          </button>
                        ))}
                      </div>
                    )
                  ))}
                  {conversations.length === 0 && (
                    <p className="text-xs text-slate-500 px-2">No conversations yet.</p>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="border-b border-slate-200 px-6 py-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-800">Chat</h2>
            <p className="text-slate-500 text-sm mt-1">
              Ask about taxes or scenario modeling. Try: &quot;If I buy a $600k STR in Nashville, how much can I save?&quot;
            </p>
            {profileSummary && (
              <div className="mt-3 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                <span className="w-2 h-2 rounded-full bg-emerald-500" />
                <span>Profile: {profileSummary}</span>
              </div>
            )}
            {profileNotice && (
              <div className="mt-2 text-xs text-emerald-700">{profileNotice}</div>
            )}
          </div>
          <button
            type="button"
            onClick={() => setShowHelp((h) => !h)}
            className="flex-shrink-0 w-8 h-8 rounded-full border border-slate-300 text-slate-600 hover:bg-slate-100 flex items-center justify-center"
            title="Getting started"
          >
            ?
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          {showGettingStarted ? (
            <GettingStartedView onSuggestion={handleSuggestion} onClose={() => setShowHelp(false)} />
          ) : (
            <>
              {messages.length === 0 && !isLoading && (
                <div className="text-slate-400 text-center py-12">
                  <p>Start a conversation about your taxes.</p>
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                  <div
                    className={`max-w-[85%] rounded-lg px-4 py-3 ${
                      msg.role === 'user' ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-800'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  </div>
                  {msg.role === 'assistant' && msg.scenarioResults?.length > 0 && (
                    <div className="mt-2 max-w-[85%] w-full space-y-2">
                      {msg.scenarioResults.map((evt, j) => (
                        <div key={j} className="rounded-lg border border-slate-200 bg-white p-4 text-sm shadow-sm">
                          <div className="font-medium text-slate-800 capitalize">{evt.scenario_type?.replace(/_/g, ' ')} scenario</div>
                          {evt.result?.summary && <p className="mt-1 text-slate-600">{evt.result.summary}</p>}
                          {(evt.result?.tax_impact?.estimated_tax_savings > 0 || evt.result?.tax_impact?.estimated_tax_savings_yr1 != null) && (
                            <p className="mt-1 font-semibold text-emerald-700">
                              {evt.result.tax_impact.estimated_tax_savings > 0
                                ? `Tax savings: $${evt.result.tax_impact.estimated_tax_savings.toLocaleString('en-US', { minimumFractionDigits: 2 })}`
                                : `Year 1 tax savings: $${evt.result.tax_impact.estimated_tax_savings_yr1?.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
                            </p>
                          )}
                          <Link to="/scenarios" className="mt-2 inline-block text-slate-600 hover:text-slate-800 underline text-xs">
                            Add to comparison →
                          </Link>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {streamingContent && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-lg px-4 py-3 bg-slate-100 text-slate-800">
                    <div className="whitespace-pre-wrap">{streamingContent}</div>
                  </div>
                </div>
              )}
              {isLoading && !streamingContent && (
                <div className="flex justify-start">
                  <div className="rounded-lg px-4 py-3 bg-slate-100 text-slate-500">
                    <span className="inline-flex gap-1">
                      <span className="animate-bounce">.</span>
                      <span className="animate-bounce" style={{ animationDelay: '0.1s' }}>.</span>
                      <span className="animate-bounce" style={{ animationDelay: '0.2s' }}>.</span>
                    </span>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </>
          )}
        </div>

        {!showGettingStarted && (
          <form onSubmit={handleSubmit} className="p-6 border-t border-slate-200">
            <div className="flex gap-3 max-w-3xl mx-auto">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about your taxes..."
                className="flex-1 rounded-lg border border-slate-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-slate-400"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="px-6 py-3 bg-slate-800 text-white rounded-lg hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Send
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function GettingStartedView({ onSuggestion, onClose }) {
  const cards = [
    {
      icon: '💰',
      label: 'How much tax do I owe?',
      prefill: "Based on my profile, what's my estimated tax owed this year?",
      nav: null,
    },
    {
      icon: '🏠',
      label: 'Model an STR investment',
      prefill: "I'm thinking of buying a short term rental property. Can you help me model the tax impact?",
      nav: null,
    },
    {
      icon: '📄',
      label: 'Enter my W-2 or 1099',
      prefill: null,
      nav: '/documents',
    },
    {
      icon: '📊',
      label: 'Compare tax strategies',
      prefill: null,
      nav: '/scenarios',
    },
  ]
  return (
    <div className="max-w-2xl mx-auto">
      <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h3 className="text-xl font-semibold text-slate-800">Welcome to your Personal Tax Advisor</h3>
        <p className="text-slate-500 mt-1">Powered by Claude — your conversations stay on your machine.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-6">
          {cards.map((card) => (
            <button
              key={card.label}
              type="button"
              onClick={() => onSuggestion(card.prefill || '', card.nav)}
              className="flex items-center gap-3 p-4 rounded-lg border-2 border-slate-200 hover:border-slate-400 hover:bg-slate-50 text-left"
            >
              <span className="text-2xl">{card.icon}</span>
              <span className="font-medium text-slate-800">{card.label}</span>
            </button>
          ))}
        </div>
        <div className="mt-8 pt-6 border-t border-slate-200">
          <h4 className="font-medium text-slate-800">How it works</h4>
          <ol className="mt-2 space-y-2 text-sm text-slate-600 list-decimal list-inside">
            <li>Set up your profile (filing status, income, state) so Claude knows your situation.</li>
            <li>Enter your tax documents using manual entry — your data stays local.</li>
            <li>Ask questions or model scenarios — Claude uses your profile to give personalized answers.</li>
          </ol>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="mt-6 text-sm text-slate-500 hover:text-slate-700 underline"
          >
            Close
          </button>
        )}
      </div>
    </div>
  )
}
