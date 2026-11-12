import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { useWorkspace } from '../context/WorkspaceContext'
import { copilotService } from '../services/api/copilotService'
import {
  BotMessageSquare,
  Sparkles,
  Send,
  Plus,
  Trash2,
  Copy,
  User,
  Lightbulb,
  ExternalLink,
  AlertTriangle,
  RefreshCw,
  FolderOpen,
} from 'lucide-react'
import { Card, Button } from '../components/common'

function generateRequestId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

function formatMessageTime(isoDate) {
  if (!isoDate) return ''
  try {
    return new Date(isoDate).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

const SUGGESTED_PROMPTS = [
  'What are the most common customer complaints?',
  'Which features should we prioritize next?',
  'Explain our current prioritization results.',
  'What are our most-used product features?',
  'Summarize the latest customer feedback.',
  'What improvements should we consider for our product?',
]

export function CopilotPage() {
  const { addToast } = useApp()
  const { currentWorkspace, currentWorkspaceId } = useWorkspace()

  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')

  const [isLoadingList, setIsLoadingList] = useState(false)
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [isSending, setIsSending] = useState(false)

  const [listError, setListError] = useState(null)
  const [chatError, setChatError] = useState(null)
  const [failedSubmission, setFailedSubmission] = useState(null)

  const workspaceEpochRef = useRef(0)
  const conversationEpochRef = useRef(0)
  const inFlightSendRef = useRef(false)
  const messagesEndRef = useRef(null)

  const activeConversation = conversations.find((c) => c.id === activeConversationId) || null

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isSending, failedSubmission])

  const loadMessages = useCallback(
    async (conversationId, wsId, wsEpoch) => {
      if (!conversationId || !wsId) {
        setMessages([])
        return
      }
      const convEpoch = ++conversationEpochRef.current
      setIsLoadingMessages(true)
      setChatError(null)
      try {
        const res = await copilotService.getConversation(conversationId, wsId)
        if (
          workspaceEpochRef.current !== wsEpoch ||
          conversationEpochRef.current !== convEpoch
        ) {
          return
        }
        setMessages(res.messages || [])
      } catch (err) {
        if (
          workspaceEpochRef.current !== wsEpoch ||
          conversationEpochRef.current !== convEpoch
        ) {
          return
        }
        setMessages([])
        setChatError(err?.message || 'Failed to load conversation messages.')
      } finally {
        if (
          workspaceEpochRef.current === wsEpoch &&
          conversationEpochRef.current === convEpoch
        ) {
          setIsLoadingMessages(false)
        }
      }
    },
    []
  )

  const loadConversations = useCallback(
    async (wsId) => {
      const wsEpoch = ++workspaceEpochRef.current
      conversationEpochRef.current += 1
      setConversations([])
      setActiveConversationId(null)
      setMessages([])
      setListError(null)
      setChatError(null)
      setFailedSubmission(null)

      if (!wsId) return

      setIsLoadingList(true)
      try {
        const res = await copilotService.getConversations(wsId)
        if (workspaceEpochRef.current !== wsEpoch) return
        const list = res.conversations || []
        setConversations(list)
        if (list.length > 0) {
          setActiveConversationId(list[0].id)
          await loadMessages(list[0].id, wsId, wsEpoch)
        }
      } catch (err) {
        if (workspaceEpochRef.current !== wsEpoch) return
        setListError(err?.message || 'Failed to load Copilot conversations.')
      } finally {
        if (workspaceEpochRef.current === wsEpoch) {
          setIsLoadingList(false)
        }
      }
    },
    [loadMessages]
  )

  useEffect(() => {
    loadConversations(currentWorkspaceId)
  }, [currentWorkspaceId, loadConversations])

  const handleSelectConversation = async (conversationId) => {
    if (!currentWorkspaceId || conversationId === activeConversationId) return
    setActiveConversationId(conversationId)
    setFailedSubmission(null)
    setChatError(null)
    await loadMessages(conversationId, currentWorkspaceId, workspaceEpochRef.current)
  }

  const handleNewChat = async () => {
    if (!currentWorkspaceId || isSending) return
    const wsEpoch = workspaceEpochRef.current
    try {
      const created = await copilotService.createConversation(currentWorkspaceId, {
        title: `Strategy Session ${conversations.length + 1}`,
        requestId: generateRequestId(),
      })
      if (workspaceEpochRef.current !== wsEpoch) return
      setConversations((prev) => [created, ...prev])
      setActiveConversationId(created.id)
      setMessages([])
      setChatError(null)
      setFailedSubmission(null)
      addToast('New Copilot session created', 'info')
    } catch (err) {
      addToast(err?.message || 'Failed to create conversation', 'error')
    }
  }

  const handleArchiveConversation = async (e, conversationId) => {
    e.stopPropagation()
    if (!currentWorkspaceId) return
    const wsEpoch = workspaceEpochRef.current
    try {
      await copilotService.archiveConversation(conversationId, currentWorkspaceId)
      if (workspaceEpochRef.current !== wsEpoch) return
      const remaining = conversations.filter((c) => c.id !== conversationId)
      setConversations(remaining)
      if (activeConversationId === conversationId) {
        setFailedSubmission(null)
        setChatError(null)
        if (remaining.length > 0) {
          setActiveConversationId(remaining[0].id)
          await loadMessages(remaining[0].id, currentWorkspaceId, wsEpoch)
        } else {
          setActiveConversationId(null)
          setMessages([])
        }
      }
      addToast('Conversation archived', 'info')
    } catch (err) {
      addToast(err?.message || 'Failed to archive conversation', 'error')
    }
  }

  const submitMessage = async ({ text, conversationId, requestId }) => {
    if (!currentWorkspaceId || inFlightSendRef.current) return
    const trimmed = (text || '').trim()
    if (!trimmed) return

    const wsIdAtSend = currentWorkspaceId
    const wsEpochAtSend = workspaceEpochRef.current
    const convEpochAtSend = conversationEpochRef.current
    const effectiveRequestId = requestId || generateRequestId()

    inFlightSendRef.current = true
    setIsSending(true)
    setChatError(null)
    setFailedSubmission(null)

    if (!requestId) {
      setInputText('')
    }

    try {
      const result = await copilotService.sendMessage({
        workspaceId: wsIdAtSend,
        conversationId,
        message: trimmed,
        requestId: effectiveRequestId,
      })

      if (workspaceEpochRef.current !== wsEpochAtSend) {
        return
      }

      const returnedConv = result.conversation
      if (returnedConv) {
        setConversations((prev) => {
          const exists = prev.some((c) => c.id === returnedConv.id)
          const updated = exists
            ? prev.map((c) => (c.id === returnedConv.id ? returnedConv : c))
            : [returnedConv, ...prev]
          return [...updated].sort(
            (a, b) => new Date(b.lastMessageAt || 0) - new Date(a.lastMessageAt || 0)
          )
        })
        setActiveConversationId(returnedConv.id)
      }

      // Only append into visible stream if user has not switched to a different conversation
      const sameConvView =
        conversationId === null
          ? conversationEpochRef.current === convEpochAtSend
          : activeConversationId === conversationId &&
            conversationEpochRef.current === convEpochAtSend

      if (sameConvView) {
        setMessages((prev) => {
          const next = [...prev]
          for (const msg of [result.userMessage, result.assistantMessage]) {
            if (!msg) continue
            const idx = next.findIndex((m) => m.id === msg.id)
            if (idx >= 0) {
              next[idx] = msg
            } else {
              next.push(msg)
            }
          }
          return next
        })
      }
    } catch (err) {
      if (workspaceEpochRef.current !== wsEpochAtSend) {
        return
      }
      const errMsg = err?.message || 'Failed to get response from Copilot.'
      setChatError(errMsg)
      setFailedSubmission({
        text: trimmed,
        conversationId,
        requestId: effectiveRequestId,
        error: errMsg,
        status: err?.status || 500,
      })
    } finally {
      inFlightSendRef.current = false
      setIsSending(false)
    }
  }

  const handleSend = (textToSend = inputText) => {
    submitMessage({
      text: textToSend,
      conversationId: activeConversationId,
      requestId: null,
    })
  }

  const handleRetry = () => {
    if (!failedSubmission || isSending) return
    submitMessage({
      text: failedSubmission.text,
      conversationId: failedSubmission.conversationId || activeConversationId,
      requestId: failedSubmission.requestId,
    })
  }

  const copyMessage = (text) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text)
    }
    addToast('Copied to clipboard', 'info')
  }

  if (!currentWorkspaceId) {
    return (
      <div className="max-w-3xl mx-auto py-12">
        <Card className="p-8 text-center space-y-3">
          <FolderOpen className="w-10 h-10 text-brand-500 mx-auto" />
          <h2 className="text-base font-bold text-slate-900 dark:text-white">
            No Workspace Selected
          </h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Select or create a workspace to start an evidence-grounded Product Copilot session.
          </p>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="h-[calc(100vh-10rem)] flex flex-col lg:flex-row gap-4 max-w-7xl mx-auto">
        {/* Left Column: Chat Sessions List */}
        <Card className="w-full lg:w-72 shrink-0 p-3 flex flex-col justify-between">
          <div className="min-h-0 flex-1 flex flex-col">
            <div className="flex items-center justify-between pb-3 mb-2 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <BotMessageSquare className="w-4 h-4 text-brand-500" />
                <span className="text-xs font-bold text-slate-900 dark:text-white">
                  Copilot Sessions
                </span>
              </div>
              <Button
                variant="ghost"
                size="xs"
                icon={Plus}
                onClick={handleNewChat}
                disabled={isSending}
                aria-label="New conversation"
              />
            </div>

            {isLoadingList ? (
              <div className="text-xs text-slate-400 py-6 text-center">
                Loading conversations...
              </div>
            ) : listError ? (
              <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 text-rose-600 dark:text-rose-400 text-xs space-y-2">
                <p>{listError}</p>
                <button
                  onClick={() => loadConversations(currentWorkspaceId)}
                  className="inline-flex items-center gap-1 font-semibold underline"
                >
                  <RefreshCw className="w-3 h-3" /> Retry
                </button>
              </div>
            ) : conversations.length === 0 ? (
              <div className="text-xs text-slate-400 py-6 text-center px-2">
                No conversations yet in {currentWorkspace?.name || 'this workspace'}. Ask a question below or click + to start.
              </div>
            ) : (
              <div className="space-y-1 overflow-y-auto flex-1">
                {conversations.map((chat) => {
                  const isSelected = chat.id === activeConversationId
                  return (
                    <div
                      key={chat.id}
                      onClick={() => handleSelectConversation(chat.id)}
                      className={`group flex items-center justify-between p-2.5 rounded-xl text-xs transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-brand-50 dark:bg-brand-950/70 text-brand-700 dark:text-brand-300 font-semibold border border-brand-200 dark:border-brand-800/60'
                          : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                      }`}
                    >
                      <span className="truncate">{chat.title}</span>
                      <button
                        onClick={(e) => handleArchiveConversation(e, chat.id)}
                        aria-label={`Archive ${chat.title}`}
                        className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-500 transition-opacity"
                        title="Archive conversation"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          <div className="pt-3 border-t border-slate-100 dark:border-slate-800 text-[10px] text-slate-400 text-center leading-snug">
            Powered by MongoDB Atlas &amp; Groq AI referencing {currentWorkspace?.name || 'active workspace'}.
          </div>
        </Card>

        {/* Right Column: Chat History & Input */}
        <Card className="flex-1 flex flex-col h-full overflow-hidden">
          <div className="p-3.5 px-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-brand-500/20 text-brand-600 dark:text-brand-400 flex items-center justify-center font-bold text-xs">
                AI
              </div>
              <div>
                <h3 className="text-xs font-bold text-slate-900 dark:text-white">
                  {activeConversation?.title || 'Product Copilot'}
                </h3>
                <p className="text-[10px] text-emerald-500 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span>Connected to {currentWorkspace?.name || 'workspace'}</span>
                </p>
              </div>
            </div>
          </div>

          {/* Messages Stream */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {isLoadingMessages ? (
              <div className="text-xs text-slate-400 py-8 text-center">
                Loading conversation history...
              </div>
            ) : messages.length === 0 && !failedSubmission && !chatError ? (
              <div className="text-center py-10 space-y-2">
                <Sparkles className="w-7 h-7 text-brand-500 mx-auto" />
                <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">
                  Ask ProductMind AI about your workspace
                </p>
                <p className="text-[11px] text-slate-400 max-w-md mx-auto">
                  Answers are grounded in your MongoDB Atlas feedback, feature groups, prioritization scores, analytics, and PRDs.
                </p>
              </div>
            ) : (
              messages.map((msg) => {
                const isUser = msg.role === 'user'
                const isFailed = msg.status === 'failed'
                return (
                  <div
                    key={msg.id}
                    className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} animate-fadeIn`}
                  >
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 ${
                        isUser
                          ? 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200'
                          : 'bg-gradient-to-tr from-brand-600 to-electric-600 text-white'
                      }`}
                    >
                      {isUser ? <User className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
                    </div>

                    <div
                      className={`max-w-[85%] rounded-2xl p-3.5 text-xs leading-relaxed ${
                        isUser
                          ? 'bg-brand-600 text-white rounded-tr-none'
                          : 'bg-slate-100 dark:bg-navy-950 text-slate-800 dark:text-slate-200 border border-slate-200/80 dark:border-slate-800 rounded-tl-none whitespace-pre-line'
                      }`}
                    >
                      {isFailed ? (
                        <div className="space-y-1 text-rose-600 dark:text-rose-400">
                          <div className="flex items-center gap-1.5 font-semibold">
                            <AlertTriangle className="w-4 h-4 shrink-0" />
                            <span>Generation Failed</span>
                          </div>
                          <p className="text-[11px] text-slate-600 dark:text-slate-400">
                            {msg.errorMessage || 'Unable to generate response.'}
                          </p>
                        </div>
                      ) : (
                        <>
                          <p>{msg.content}</p>
                          {msg.evidence && msg.evidence.length > 0 && (
                            <div className="mt-3 pt-2.5 border-t border-slate-200/60 dark:border-slate-800/80">
                              <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 block mb-1.5">
                                Referenced Workspace Evidence:
                              </span>
                              <div className="flex flex-wrap gap-1.5">
                                {msg.evidence.map((ev, idx) => (
                                  <Link
                                    key={ev.entityId || idx}
                                    to={ev.path || '/copilot'}
                                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-brand-500/10 hover:bg-brand-500/20 text-brand-700 dark:text-brand-300 border border-brand-500/20 text-[10px] font-medium transition-colors"
                                  >
                                    {ev.type ? (
                                      <span className="uppercase text-[9px] font-bold opacity-70">
                                        {ev.type.replace('_', ' ')}
                                      </span>
                                    ) : null}
                                    <span>{ev.label}</span>
                                    {ev.count ? <span className="opacity-75">({ev.count})</span> : null}
                                    <ExternalLink className="w-2.5 h-2.5" />
                                  </Link>
                                ))}
                              </div>
                            </div>
                          )}
                        </>
                      )}

                      <div
                        className={`flex items-center justify-between text-[10px] mt-2 pt-1.5 border-t ${
                          isUser
                            ? 'border-brand-500/50 text-brand-200'
                            : 'border-slate-200/60 dark:border-slate-800 text-slate-400'
                        }`}
                      >
                        <span>{formatMessageTime(msg.createdAt)}</span>
                        {!isUser && !isFailed && (
                          <button
                            onClick={() => copyMessage(msg.content)}
                            className="hover:text-slate-600 dark:hover:text-slate-200 flex items-center gap-1"
                          >
                            <Copy className="w-3 h-3" />
                            <span>Copy</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })
            )}

            {failedSubmission && (
              <div className="p-3.5 rounded-2xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/60 text-xs space-y-2">
                <div className="flex items-center gap-1.5 font-semibold text-rose-600 dark:text-rose-400">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>Request Failed</span>
                </div>
                <p className="text-[11px] text-slate-700 dark:text-slate-300">
                  {failedSubmission.error}
                </p>
                <button
                  onClick={handleRetry}
                  disabled={isSending}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-300 text-[11px] font-semibold hover:bg-rose-200 transition-colors disabled:opacity-50"
                >
                  <RefreshCw className="w-3 h-3" /> Retry
                </button>
              </div>
            )}

            {chatError && !failedSubmission && (
              <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 text-rose-600 dark:text-rose-400 text-xs">
                {chatError}
              </div>
            )}

            {isSending && (
              <div className="flex gap-3 items-center text-xs text-slate-400 animate-pulse">
                <div className="w-7 h-7 rounded-lg bg-brand-500/20 text-brand-500 flex items-center justify-center">
                  <Sparkles className="w-4 h-4 animate-spin-slow" />
                </div>
                <span className="italic">Analyzing workspace data &amp; synthesizing response...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggested Prompts Pills */}
          <div className="p-3 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-navy-950/40">
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-[11px] no-scrollbar">
              <Lightbulb className="w-3.5 h-3.5 text-amber-500 shrink-0" />
              <span className="text-[10px] text-slate-400 font-bold uppercase shrink-0">
                Try Asking:
              </span>
              {SUGGESTED_PROMPTS.slice(0, 4).map((prompt) => (
                <button
                  key={prompt}
                  disabled={isSending}
                  onClick={() => handleSend(prompt)}
                  className="px-2.5 py-1 rounded-full bg-white dark:bg-navy-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:border-brand-500 hover:text-brand-600 whitespace-nowrap shrink-0 transition-colors cursor-pointer disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>

            {/* Input Box */}
            <div className="flex items-center gap-2 mt-2">
              <input
                type="text"
                value={inputText}
                disabled={isSending}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !isSending && handleSend()}
                placeholder="Ask anything about feedback, prioritization scores, analytics, or PRDs..."
                className="flex-1 px-3.5 py-2 text-xs rounded-xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 disabled:opacity-60"
              />
              <Button
                variant="electric"
                size="sm"
                disabled={!inputText.trim() || isSending}
                onClick={() => handleSend()}
                icon={Send}
              >
                {isSending ? 'Sending...' : 'Send'}
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}

export default CopilotPage
