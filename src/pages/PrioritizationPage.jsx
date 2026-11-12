import React, { useState, useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import {
  SlidersHorizontal,
  Plus,
  Search,
  Filter,
  LayoutGrid,
  Table as TableIcon,
  Columns3,
  Edit2,
  Trash2,
  Link as LinkIcon,
  Sparkles,
  TrendingUp,
  MessageSquare,
  Send,
  HelpCircle,
  FileText,
  ChevronRight,
  ArrowUpDown,
  Layers,
  Calculator,
  ExternalLink,
  GitCompare,
  Brain,
  Loader2,
  Quote,
} from 'lucide-react'
import { Card, Badge, Button, Modal, DemoModeBanner } from '../components/common'
import { calculatePriorityScore, getScoreBreakdown, getPriorityTier, FACTOR_WEIGHTS } from '../data/scoringFormulas'
import { prioritizationService } from '../services/api/prioritizationService'
import { useWorkspace } from '../context/WorkspaceContext'
import { SimulatorPage } from './SimulatorPage'

export function PrioritizationPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') === 'simulator' ? 'simulator' : 'matrix'

  const handleTabChange = (tab) => {
    if (tab === 'simulator') {
      setSearchParams({ tab: 'simulator' })
    } else {
      setSearchParams({})
    }
  }
  const {
    features,
    feedback,
    addFeature,
    updateFeature,
    deleteFeature,
    addToast,
  } = useApp()
  const { currentWorkspace } = useWorkspace()

  // AI Prioritization state
  const [aiPrioritizationResults, setAiPrioritizationResults] = useState([])
  const [isLoadingAiPrioritization, setIsLoadingAiPrioritization] = useState(false)
  const [aiError, setAiError] = useState(null)

  // Fetch stored prioritization results from backend
  const loadPrioritization = React.useCallback(async () => {
    if (!currentWorkspace?.id) return
    try {
      const results = await prioritizationService.getPrioritizationResults(currentWorkspace.id)
      if (Array.isArray(results) && results.length > 0) {
        setAiPrioritizationResults(results)
      }
    } catch (err) {
      console.warn('Could not load prioritization results:', err)
    }
  }, [currentWorkspace?.id])

  React.useEffect(() => {
    loadPrioritization()
  }, [loadPrioritization])

  // Run AI Prioritization Engine
  const handleRunAIPrioritization = async () => {
    if (!currentWorkspace?.id) {
      addToast('Please select a workspace first.', 'warning')
      return
    }

    setIsLoadingAiPrioritization(true)
    setAiError(null)

    try {
      const res = await prioritizationService.analyzePrioritization({
        workspaceId: currentWorkspace.id,
      })

      if (res?.results) {
        setAiPrioritizationResults(res.results)
        addToast(`Prioritization Agent evaluated ${res.total_evaluated || res.results.length} features!`, 'success')
      } else {
        await loadPrioritization()
      }
    } catch (err) {
      const msg = err?.message || 'Prioritization evaluation failed.'
      setAiError(msg)
      addToast(msg, 'error')
    } finally {
      setIsLoadingAiPrioritization(false)
    }
  }

  // View modes: 'table', 'card', 'kanban'
  const [viewMode, setViewMode] = useState('table')

  // Search & Filter
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [releaseFilter, setReleaseFilter] = useState('All')

  // Modals
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingFeature, setEditingFeature] = useState(null)
  const [inspectingFeature, setInspectingFeature] = useState(null)

  // Form state
  const [formName, setFormName] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formImpact, setFormImpact] = useState(7)
  const [formUrgency, setFormUrgency] = useState(7)
  const [formDemand, setFormDemand] = useState(7)
  const [formValue, setFormValue] = useState(7)
  const [formStatus, setFormStatus] = useState('In Planning')
  const [formOwner, setFormOwner] = useState('Alex Rivera')
  const [formRelease, setFormRelease] = useState('v2.4.0')

  // New comment input for inspecting modal
  const [newCommentText, setNewCommentText] = useState('')

  const statuses = ['All', 'Backlog', 'Evaluating', 'In Planning', 'In Development', 'Ready for Release', 'Launched']
  const releasesList = ['All', 'v2.3.0', 'v2.4.0', 'v2.5.0', 'v3.0.0']

  // Real-time score preview for modal
  const previewScore = calculatePriorityScore({
    customerImpact: formImpact,
    urgency: formUrgency,
    demand: formDemand,
    businessValue: formValue,
  })

  const previewBreakdown = getScoreBreakdown({
    customerImpact: formImpact,
    urgency: formUrgency,
    demand: formDemand,
    businessValue: formValue,
  })

  // Filter and sort features strictly by priority score
  const sortedFeatures = useMemo(() => {
    return [...features]
      .filter(f => {
        if (searchTerm) {
          const q = searchTerm.toLowerCase()
          if (!f.name.toLowerCase().includes(q) && !f.description.toLowerCase().includes(q)) return false
        }
        if (statusFilter !== 'All' && f.status !== statusFilter) return false
        if (releaseFilter !== 'All' && f.targetRelease !== releaseFilter) return false
        return true
      })
      .sort((a, b) => b.score - a.score)
  }, [features, searchTerm, statusFilter, releaseFilter])

  const handleOpenCreate = () => {
    setEditingFeature(null)
    setFormName('')
    setFormDescription('')
    setFormImpact(7)
    setFormUrgency(7)
    setFormDemand(7)
    setFormValue(7)
    setFormStatus('In Planning')
    setFormOwner('Alex Rivera')
    setFormRelease('v2.4.0')
    setShowCreateModal(true)
  }

  const handleOpenEdit = (feat) => {
    setEditingFeature(feat)
    setFormName(feat.name)
    setFormDescription(feat.description)
    setFormImpact(feat.customerImpact)
    setFormUrgency(feat.urgency)
    setFormDemand(feat.demand)
    setFormValue(feat.businessValue)
    setFormStatus(feat.status)
    setFormOwner(feat.owner)
    setFormRelease(feat.targetRelease)
    setShowCreateModal(true)
  }

  const handleSave = (e) => {
    e.preventDefault()
    if (!formName.trim()) {
      addToast('Please provide a feature name', 'warning')
      return
    }

    const payload = {
      name: formName,
      description: formDescription,
      customerImpact: Number(formImpact),
      urgency: Number(formUrgency),
      demand: Number(formDemand),
      businessValue: Number(formValue),
      status: formStatus,
      owner: formOwner,
      targetRelease: formRelease,
    }

    if (editingFeature) {
      updateFeature(editingFeature.id, payload)
    } else {
      addFeature(payload)
    }

    setShowCreateModal(false)
  }

  // Quick slider adjustment from list
  const handleQuickAdjust = (featId, factor, val) => {
    updateFeature(featId, { [factor]: Number(val) })
  }

  // Add comment
  const handleAddComment = () => {
    if (!newCommentText.trim() || !inspectingFeature) return
    const newComment = {
      id: `c-${Date.now()}`,
      author: 'Alex Rivera',
      text: newCommentText.trim(),
      date: new Date().toISOString().split('T')[0],
    }
    const updatedComments = [...(inspectingFeature.comments || []), newComment]
    updateFeature(inspectingFeature.id, { comments: updatedComments })
    setInspectingFeature({ ...inspectingFeature, comments: updatedComments })
    setNewCommentText('')
    addToast('Comment added', 'success')
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Primary Workflow Sub-Tabs: Matrix vs Simulator */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
        <button
          onClick={() => handleTabChange('matrix')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'matrix'
              ? 'bg-brand-600 text-white shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <SlidersHorizontal className="w-4 h-4" />
          <span>Prioritization Matrix</span>
        </button>

        <button
          onClick={() => handleTabChange('simulator')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'simulator'
              ? 'bg-brand-600 text-white shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <GitCompare className="w-4 h-4" />
          <span>What-If Simulator</span>
          <span
            className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
              activeTab === 'simulator'
                ? 'bg-white/20 text-white'
                : 'bg-electric-500/10 text-electric-600 dark:text-electric-400 border border-electric-500/20'
            }`}
          >
            Sandbox
          </span>
        </button>
      </div>

      {activeTab === 'simulator' ? (
        <SimulatorPage />
      ) : (
        <>
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">Feature Prioritization Matrix</h2>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20">
                  Formulaic Model
                </span>
              </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 font-mono">
            Score = (0.35 × Impact) + (0.30 × Urgency) + (0.20 × Demand) + (0.15 × Business Value)
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* View mode toggle */}
          <div className="flex items-center border border-slate-200 dark:border-slate-800 rounded-lg p-0.5 bg-slate-50 dark:bg-navy-950">
            <button
              onClick={() => setViewMode('table')}
              className={`p-1.5 rounded-md ${viewMode === 'table' ? 'bg-white dark:bg-navy-900 text-brand-600 shadow-xs' : 'text-slate-400'}`}
              title="Table View"
            >
              <TableIcon className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode('card')}
              className={`p-1.5 rounded-md ${viewMode === 'card' ? 'bg-white dark:bg-navy-900 text-brand-600 shadow-xs' : 'text-slate-400'}`}
              title="Card View"
            >
              <LayoutGrid className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setViewMode('kanban')}
              className={`p-1.5 rounded-md ${viewMode === 'kanban' ? 'bg-white dark:bg-navy-900 text-brand-600 shadow-xs' : 'text-slate-400'}`}
              title="Kanban Board View"
            >
              <Columns3 className="w-3.5 h-3.5" />
            </button>
          </div>

          <Button
            variant="primary"
            size="sm"
            disabled={isLoadingAiPrioritization}
            onClick={handleRunAIPrioritization}
            icon={isLoadingAiPrioritization ? Loader2 : Brain}
          >
            {isLoadingAiPrioritization ? 'Evaluating Features...' : 'Run AI Prioritization'}
          </Button>

          <Link to="/aggregation">
            <Button variant="secondary" size="sm" icon={Layers}>
              Aggregation Clusters
            </Button>
          </Link>

          <Button variant="outline" size="sm" icon={Plus} onClick={handleOpenCreate}>
            New Feature
          </Button>
        </div>
      </div>

      {aiError && (
        <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-600 dark:text-rose-400 text-xs">
          {aiError}
        </div>
      )}

      {/* AI 6-Factor Prioritization Engine Results */}
      {aiPrioritizationResults.length > 0 && (
        <Card className="p-4 border border-brand-200/80 dark:border-brand-800/70 bg-white dark:bg-navy-900 space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
            <div>
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-brand-600 dark:text-brand-400" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                  AI 6-Factor Prioritization Results ({aiPrioritizationResults.length})
                </h3>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  Live 0–100 Composite Engine
                </span>
              </div>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 font-mono">
                Composite = 0.25 Demand + 0.20 Urgency + 0.20 Business Impact + 0.15 Strategic Alignment + 0.10 Sentiment + 0.10 Usage Impact
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {aiPrioritizationResults.map((res, idx) => {
              const factorDefs = [
                { key: 'customer_demand', label: 'Customer Demand', defaultWeight: 0.25, color: 'bg-brand-500' },
                { key: 'urgency', label: 'Urgency', defaultWeight: 0.20, color: 'bg-rose-500' },
                { key: 'business_impact', label: 'Business Impact', defaultWeight: 0.20, color: 'bg-indigo-500' },
                { key: 'strategic_alignment', label: 'Strategic Alignment', defaultWeight: 0.15, color: 'bg-sky-500' },
                { key: 'sentiment', label: 'Sentiment', defaultWeight: 0.10, color: 'bg-amber-500' },
                { key: 'usage_impact', label: 'Usage Impact', defaultWeight: 0.10, color: 'bg-emerald-500' },
              ]
              const factorScores = res.factor_scores || {}
              const factorWeights = res.factor_weights || {}
              const missingList = res.missing_data || []

              return (
                <div
                  key={res.result_id || res.feature_group_id || idx}
                  className="p-3.5 rounded-2xl bg-slate-50/80 dark:bg-navy-950/70 border border-slate-200/80 dark:border-slate-800 space-y-3"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <span className="w-7 h-7 rounded-lg bg-brand-600/10 text-brand-600 dark:text-brand-400 font-bold text-xs inline-flex items-center justify-center">
                        #{idx + 1}
                      </span>
                      <div>
                        <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                          {res.group_name}
                        </h4>
                        <span className="text-[10px] text-slate-500 dark:text-slate-400">
                          Data Coverage: {Number(res.coverage_percentage ?? 100).toFixed(1)}%
                          {missingList.length > 0 ? ` • Reweighted (missing: ${missingList.join(', ')})` : ' • All 6 Factors Measured'}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="text-right">
                        <span className="text-base font-black text-brand-600 dark:text-brand-400 font-mono">
                          {Number(res.final_score ?? 0).toFixed(2)}
                        </span>
                        <span className="text-[10px] text-slate-400 ml-1">/ 100</span>
                      </div>
                      <Badge variant={res.priority_level === 'Critical' ? 'danger' : res.priority_level === 'High' ? 'warning' : 'brand'}>
                        {res.priority_level}
                      </Badge>
                      {res.feature_group_id && (
                        <Button
                          variant="outline"
                          size="xs"
                          icon={FileText}
                          onClick={() => navigate(`/prd-generator?featureId=${res.feature_group_id}`, { state: { featureId: res.feature_group_id } })}
                        >
                          Generate PRD
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* All 6 Factor Scores */}
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
                    {factorDefs.map(f => {
                      const rawScore = factorScores[f.key]
                      const isMeasured = rawScore !== undefined && rawScore !== null
                      const weightVal = factorWeights[f.key]
                      const weightPct = weightVal !== undefined ? `${(Number(weightVal) * 100).toFixed(1)}%` : `${(f.defaultWeight * 100).toFixed(0)}%`
                      return (
                        <div
                          key={f.key}
                          className="p-2 rounded-xl bg-white dark:bg-navy-900 border border-slate-200/70 dark:border-slate-800 text-[11px]"
                        >
                          <div className="flex items-center justify-between text-slate-500 dark:text-slate-400 mb-1">
                            <span className="truncate font-medium">{f.label}</span>
                            <span className="text-[10px] font-mono">{weightPct}</span>
                          </div>
                          {isMeasured ? (
                            <>
                              <div className="font-bold text-slate-900 dark:text-white font-mono">
                                {Number(rawScore).toFixed(1)}
                              </div>
                              <div className="w-full h-1 rounded-full bg-slate-100 dark:bg-slate-800 mt-1 overflow-hidden">
                                <div className={f.color + ' h-full'} style={{ width: `${Math.min(100, Math.max(0, Number(rawScore)))}%` }} />
                              </div>
                            </>
                          ) : (
                            <div className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">
                              Unmeasured
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>

                  {res.explanation && (
                    <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">
                      {res.explanation}
                    </p>
                  )}

                  {/* Usage Analytics Evidence Explainability */}
                  {(() => {
                    const ue = res.agent_metadata?.usage_analytics_evidence
                    if (ue && ue.available) {
                      return (
                        <div className="p-2.5 rounded-xl bg-emerald-50/60 dark:bg-emerald-950/25 border border-emerald-200/70 dark:border-emerald-800/50 text-[11px] space-y-1">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="font-bold text-emerald-800 dark:text-emerald-300">
                              Usage Analytics Evidence ({ue.matched_feature || res.group_name})
                            </span>
                            <span className="font-mono text-[10px] text-emerald-700 dark:text-emerald-400">
                              Coverage: {ue.coverage_status || 'measured'} • Weight: {(Number(ue.weight_applied ?? 0.1) * 100).toFixed(1)}%
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-700 dark:text-slate-300 font-mono text-[10px]">
                            <span>Events: {ue.event_count ?? 'Unavailable'}</span>
                            <span>Unique Users: {ue.unique_users ?? 'Unavailable'}</span>
                            <span>Adoption: {ue.adoption_rate !== null && ue.adoption_rate !== undefined ? `${ue.adoption_rate}%` : 'Unavailable'}</span>
                            <span>Trend: {ue.trend_direction || 'stable'}</span>
                          </div>
                        </div>
                      )
                    }
                    if (missingList.includes('usage_impact') || (ue && !ue.available)) {
                      return (
                        <div className="p-2.5 rounded-xl bg-amber-50/60 dark:bg-amber-950/25 border border-amber-200/70 dark:border-amber-800/50 text-[11px] text-amber-800 dark:text-amber-300">
                          <strong>Usage Analytics Unavailable:</strong>{' '}
                          {ue?.missing_reason || 'No matching feature usage telemetry found in workspace MongoDB Atlas rollups; 10% weight reweighted across measured factors.'}
                        </div>
                      )
                    }
                    return null
                  })()}
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {/* Verified Mathematical Formula & Priority Thresholds Architecture */}
      <Card className="p-4 bg-gradient-to-r from-brand-50/60 via-slate-50 to-sky-50/60 dark:from-brand-950/40 dark:via-navy-900 dark:to-sky-950/40 border border-brand-200/70 dark:border-brand-800/60">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Calculator className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <span className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                Verified Scoring Model & Thresholds Architecture
              </span>
            </div>
            <p className="text-xs text-slate-600 dark:text-slate-300 font-mono">
              Score = (0.35 × Customer Impact) + (0.30 × Urgency) + (0.20 × Demand) + (0.15 × Business Value)
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-[10px] font-bold font-mono">
            <span className="px-2 py-0.5 rounded-md border text-red-600 bg-red-500/10 border-red-500/20">
              Urgent: ≥ 8.00
            </span>
            <span className="px-2 py-0.5 rounded-md border text-amber-600 bg-amber-500/10 border-amber-500/20">
              High: ≥ 6.50
            </span>
            <span className="px-2 py-0.5 rounded-md border text-blue-600 bg-blue-500/10 border-blue-500/20">
              Medium: ≥ 4.50
            </span>
            <span className="px-2 py-0.5 rounded-md border text-slate-600 bg-slate-500/10 border-slate-500/20">
              Low: &lt; 4.50
            </span>
          </div>
        </div>
      </Card>

      {/* Filter and Search Bar */}
      <Card className="p-3.5 flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            placeholder="Search prioritized features..."
            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200"
          >
            {statuses.map(s => (
              <option key={s} value={s}>Status: {s}</option>
            ))}
          </select>

          <select
            value={releaseFilter}
            onChange={e => setReleaseFilter(e.target.value)}
            className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200"
          >
            {releasesList.map(r => (
              <option key={r} value={r}>Release: {r}</option>
            ))}
          </select>
        </div>
      </Card>

      {/* TABLE VIEW */}
      {viewMode === 'table' && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 dark:bg-navy-950/60 border-b border-slate-200 dark:border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                  <th className="py-3 px-4 w-12 text-center">Rank</th>
                  <th className="py-3 px-4">Feature Name & Details</th>
                  <th className="py-3 px-4 text-center">Score</th>
                  <th className="py-3 px-4">Factors (Impact / Urg / Dem / Val)</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Target</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                {sortedFeatures.map((feat, idx) => {
                  const breakdown = getScoreBreakdown(feat)
                  const tier = getPriorityTier(feat.score)
                  return (
                    <tr key={feat.id} className="hover:bg-slate-50/70 dark:hover:bg-navy-950/40 transition-colors">
                      <td className="py-3 px-4 text-center">
                        <span className="w-7 h-7 rounded-lg bg-brand-500/10 text-brand-600 dark:text-brand-400 font-bold text-xs inline-flex items-center justify-center">
                          #{idx + 1}
                        </span>
                      </td>
                      <td className="py-3 px-4 max-w-sm">
                        <div className="flex flex-col">
                          <button
                            onClick={() => setInspectingFeature(feat)}
                            className="font-bold text-slate-900 dark:text-white hover:text-brand-600 dark:hover:text-brand-400 text-left line-clamp-1"
                          >
                            {feat.name}
                          </button>
                          <span className="text-slate-400 line-clamp-1 mt-0.5">{feat.description}</span>
                          <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
                            <span>Owner: {feat.owner}</span>
                            <span>•</span>
                            <span>{feat.relatedFeedbackIds?.length || 0} Linked Feedback</span>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className="text-base font-black text-brand-600 dark:text-brand-400 block font-mono">
                          {feat.score.toFixed(2)}
                        </span>
                        <span className={`text-[9px] font-bold px-1.5 py-0.2 rounded border ${tier.color}`}>
                          {tier.label}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="space-y-1 w-44">
                          <div className="flex justify-between text-[10px] text-slate-400">
                            <span>Imp: {feat.customerImpact}</span>
                            <span>Urg: {feat.urgency}</span>
                            <span>Dem: {feat.demand}</span>
                            <span>Val: {feat.businessValue}</span>
                          </div>
                          {/* Visual factor breakdown bar */}
                          <div className="w-full h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 flex overflow-hidden">
                            <div className="bg-brand-500" style={{ width: `${(breakdown.customerImpactContribution / 10) * 100}%` }} title={`Impact: ${breakdown.customerImpactContribution}`} />
                            <div className="bg-rose-500" style={{ width: `${(breakdown.urgencyContribution / 10) * 100}%` }} title={`Urgency: ${breakdown.urgencyContribution}`} />
                            <div className="bg-electric-500" style={{ width: `${(breakdown.demandContribution / 10) * 100}%` }} title={`Demand: ${breakdown.demandContribution}`} />
                            <div className="bg-amber-500" style={{ width: `${(breakdown.businessValueContribution / 10) * 100}%` }} title={`Value: ${breakdown.businessValueContribution}`} />
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant="default">{feat.status}</Badge>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant="brand">{feat.targetRelease}</Badge>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => handleTabChange('simulator')}
                            className="p-1 text-slate-400 hover:text-electric-500 rounded-md"
                            title="Simulate in What-If Sandbox"
                          >
                            <TrendingUp className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => navigate(`/prd-generator?featureId=${feat.id}`, { state: { featureId: feat.id } })}
                            className="p-1 text-slate-400 hover:text-brand-600 rounded-md"
                            title="Generate PRD"
                          >
                            <FileText className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleOpenEdit(feat)}
                            className="p-1 text-slate-400 hover:text-brand-600 rounded-md"
                            title="Edit Feature"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => deleteFeature(feat.id)}
                            className="p-1 text-slate-400 hover:text-rose-600 rounded-md"
                            title="Delete Feature"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* CARD VIEW */}
      {viewMode === 'card' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {sortedFeatures.map((feat, idx) => {
            const breakdown = getScoreBreakdown(feat)
            const tier = getPriorityTier(feat.score)
            return (
              <Card key={feat.id} className="p-5 flex flex-col justify-between" hover>
                <div>
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 rounded-lg bg-brand-500/10 text-brand-600 dark:text-brand-400 text-xs font-bold flex items-center justify-center shrink-0">
                        #{idx + 1}
                      </span>
                      <h3 className="text-sm font-bold text-slate-900 dark:text-white line-clamp-1">{feat.name}</h3>
                    </div>
                    <div className="text-right">
                      <span className="text-base font-black text-brand-600 dark:text-brand-400 font-mono">
                        {feat.score.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed mb-4">
                    {feat.description}
                  </p>

                  {/* Factor sliders */}
                  <div className="grid grid-cols-2 gap-3 p-3 rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200/80 dark:border-slate-800 text-xs">
                    <div>
                      <div className="flex justify-between text-[11px] mb-1">
                        <span className="text-slate-400">Impact (35%)</span>
                        <span className="font-bold text-slate-800 dark:text-slate-200">{feat.customerImpact}/10</span>
                      </div>
                      <input
                        type="range"
                        min="1"
                        max="10"
                        value={feat.customerImpact}
                        onChange={e => handleQuickAdjust(feat.id, 'customerImpact', e.target.value)}
                        className="w-full accent-brand-500 cursor-pointer"
                      />
                    </div>
                    <div>
                      <div className="flex justify-between text-[11px] mb-1">
                        <span className="text-slate-400">Urgency (30%)</span>
                        <span className="font-bold text-slate-800 dark:text-slate-200">{feat.urgency}/10</span>
                      </div>
                      <input
                        type="range"
                        min="1"
                        max="10"
                        value={feat.urgency}
                        onChange={e => handleQuickAdjust(feat.id, 'urgency', e.target.value)}
                        className="w-full accent-rose-500 cursor-pointer"
                      />
                    </div>
                    <div>
                      <div className="flex justify-between text-[11px] mb-1">
                        <span className="text-slate-400">Demand (20%)</span>
                        <span className="font-bold text-slate-800 dark:text-slate-200">{feat.demand}/10</span>
                      </div>
                      <input
                        type="range"
                        min="1"
                        max="10"
                        value={feat.demand}
                        onChange={e => handleQuickAdjust(feat.id, 'demand', e.target.value)}
                        className="w-full accent-electric-500 cursor-pointer"
                      />
                    </div>
                    <div>
                      <div className="flex justify-between text-[11px] mb-1">
                        <span className="text-slate-400">Business Val (15%)</span>
                        <span className="font-bold text-slate-800 dark:text-slate-200">{feat.businessValue}/10</span>
                      </div>
                      <input
                        type="range"
                        min="1"
                        max="10"
                        value={feat.businessValue}
                        onChange={e => handleQuickAdjust(feat.id, 'businessValue', e.target.value)}
                        className="w-full accent-amber-500 cursor-pointer"
                      />
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <Badge variant="default">{feat.status}</Badge>
                    <Badge variant="brand">{feat.targetRelease}</Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => navigate(`/prd-generator?featureId=${feat.id}`, { state: { featureId: feat.id } })}
                      className="text-slate-500 hover:text-brand-600 flex items-center gap-1"
                      title="Generate PRD"
                    >
                      <FileText className="w-3 h-3" />
                      <span>PRD</span>
                    </button>
                    <button onClick={() => setInspectingFeature(feat)} className="text-brand-600 dark:text-brand-400 hover:underline">
                      Details
                    </button>
                    <button onClick={() => handleOpenEdit(feat)} className="text-slate-500 hover:text-slate-800 dark:hover:text-slate-200">
                      Edit
                    </button>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* KANBAN VIEW */}
      {viewMode === 'kanban' && (
        <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-3">
          {statuses.filter(s => s !== 'All').map(colStatus => {
            const colFeatures = sortedFeatures.filter(f => f.status === colStatus)
            return (
              <div key={colStatus} className="flex flex-col rounded-2xl bg-slate-100/60 dark:bg-navy-900/60 border border-slate-200 dark:border-slate-800 p-3 min-h-[500px]">
                <div className="flex items-center justify-between pb-2.5 mb-2 border-b border-slate-200 dark:border-slate-800">
                  <span className="text-xs font-bold text-slate-800 dark:text-slate-200 truncate">{colStatus}</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                    {colFeatures.length}
                  </span>
                </div>

                <div className="space-y-2 flex-1 overflow-y-auto">
                  {colFeatures.map(feat => (
                    <Card
                      key={feat.id}
                      onClick={() => setInspectingFeature(feat)}
                      className="p-3 cursor-pointer hover:border-brand-500/50 transition-all"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] font-bold text-brand-600 dark:text-brand-400 font-mono">
                          Score {feat.score.toFixed(2)}
                        </span>
                        <span className="text-[9px] px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                          {feat.targetRelease}
                        </span>
                      </div>
                      <h4 className="text-xs font-bold text-slate-900 dark:text-white line-clamp-2">{feat.name}</h4>
                      <p className="text-[11px] text-slate-400 line-clamp-2 mt-1">{feat.description}</p>
                    </Card>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Create / Edit Feature Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title={editingFeature ? 'Edit Feature & Adjust Scoring' : 'Prioritize New Feature'}
        subtitle="Priority scores are calculated automatically from the 4 weighted factors"
      >
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Feature Name *
            </label>
            <input
              type="text"
              required
              value={formName}
              onChange={e => setFormName(e.target.value)}
              placeholder="e.g. High-Performance Virtualized Data Grid"
              className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Description & Scope
            </label>
            <textarea
              rows={2}
              value={formDescription}
              onChange={e => setFormDescription(e.target.value)}
              placeholder="Describe user story and architectural goal..."
              className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {/* Real-time score preview card */}
          <div className="p-3.5 rounded-2xl bg-brand-50/60 dark:bg-brand-950/40 border border-brand-200 dark:border-brand-800 flex items-center justify-between">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-brand-700 dark:text-brand-300">
                Calculated Priority Score
              </span>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                ({previewBreakdown.customerImpactContribution} + {previewBreakdown.urgencyContribution} + {previewBreakdown.demandContribution} + {previewBreakdown.businessValueContribution})
              </p>
            </div>
            <span className="text-2xl font-black text-brand-600 dark:text-brand-400 font-mono">
              {previewScore.toFixed(2)} <span className="text-xs text-slate-400 font-normal">/ 10</span>
            </span>
          </div>

          {/* Sliders for 4 factors */}
          <div className="space-y-3 p-4 rounded-2xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-slate-700 dark:text-slate-300">
                  Customer Impact (Weight: 35%)
                </span>
                <span className="font-bold text-brand-600 dark:text-brand-400">{formImpact} / 10</span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                value={formImpact}
                onChange={e => setFormImpact(Number(e.target.value))}
                className="w-full accent-brand-500 cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-slate-700 dark:text-slate-300">
                  Urgency (Weight: 30%)
                </span>
                <span className="font-bold text-rose-500">{formUrgency} / 10</span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                value={formUrgency}
                onChange={e => setFormUrgency(Number(e.target.value))}
                className="w-full accent-rose-500 cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-slate-700 dark:text-slate-300">
                  Customer Demand (Weight: 20%)
                </span>
                <span className="font-bold text-electric-500">{formDemand} / 10</span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                value={formDemand}
                onChange={e => setFormDemand(Number(e.target.value))}
                className="w-full accent-electric-500 cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="font-semibold text-slate-700 dark:text-slate-300">
                  Business Value (Weight: 15%)
                </span>
                <span className="font-bold text-amber-500">{formValue} / 10</span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                value={formValue}
                onChange={e => setFormValue(Number(e.target.value))}
                className="w-full accent-amber-500 cursor-pointer"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Status</label>
              <select
                value={formStatus}
                onChange={e => setFormStatus(e.target.value)}
                className="w-full px-2.5 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
              >
                {statuses.filter(s => s !== 'All').map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Owner</label>
              <input
                type="text"
                value={formOwner}
                onChange={e => setFormOwner(e.target.value)}
                className="w-full px-2.5 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Target Release</label>
              <select
                value={formRelease}
                onChange={e => setFormRelease(e.target.value)}
                className="w-full px-2.5 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
              >
                {releasesList.filter(r => r !== 'All').map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowCreateModal(false)}>Cancel</Button>
            <Button variant="primary" type="submit">
              {editingFeature ? 'Update Priority' : 'Add to Prioritization'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Feature Details & Discussion Modal */}
      {inspectingFeature && (
        <Modal
          isOpen={!!inspectingFeature}
          onClose={() => setInspectingFeature(null)}
          title={inspectingFeature.name}
          subtitle={`Calculated Priority Score: ${inspectingFeature.score.toFixed(2)}/10 • ${inspectingFeature.status}`}
        >
          <div className="space-y-4">
            <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              {inspectingFeature.description}
            </p>

            {/* Score breakdown metrics */}
            <div className="grid grid-cols-4 gap-2 text-center text-xs p-3 rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800">
              <div>
                <span className="text-[10px] text-slate-400 block">Impact (35%)</span>
                <span className="font-bold text-brand-600">{inspectingFeature.customerImpact}/10</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block">Urgency (30%)</span>
                <span className="font-bold text-rose-500">{inspectingFeature.urgency}/10</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block">Demand (20%)</span>
                <span className="font-bold text-electric-500">{inspectingFeature.demand}/10</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 block">Business Val (15%)</span>
                <span className="font-bold text-amber-500">{inspectingFeature.businessValue}/10</span>
              </div>
            </div>

            {/* Linked Feedback Section */}
            <div>
              <span className="text-xs font-bold text-slate-900 dark:text-white block mb-2">
                Linked Customer Feedback ({inspectingFeature.relatedFeedbackIds?.length || 0})
              </span>
              <div className="space-y-1.5 max-h-32 overflow-y-auto">
                {feedback.filter(f => inspectingFeature.relatedFeedbackIds?.includes(f.id)).map(fb => (
                  <div
                    key={fb.id}
                    onClick={() => {
                      setInspectingFeature(null)
                      navigate('/feedback')
                    }}
                    className="p-2 rounded-lg bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-[11px] hover:border-brand-500 cursor-pointer transition-colors group flex items-center justify-between"
                    title="Click to view feedback record in Feedback Explorer"
                  >
                    <div>
                      <span className="font-semibold text-slate-800 dark:text-slate-200 group-hover:text-brand-600 dark:group-hover:text-brand-400">
                        {fb.title}
                      </span>
                      <span className="text-slate-400 block mt-0.5">{fb.customer} ({fb.company})</span>
                    </div>
                    <ExternalLink className="w-3.5 h-3.5 text-slate-400 group-hover:text-brand-500 shrink-0 ml-2" />
                  </div>
                ))}
              </div>
            </div>

            {/* Comments & Discussion */}
            <div>
              <span className="text-xs font-bold text-slate-900 dark:text-white block mb-2">
                Team Notes & Discussion ({inspectingFeature.comments?.length || 0})
              </span>
              <div className="space-y-2 mb-3 max-h-36 overflow-y-auto">
                {(inspectingFeature.comments || []).map(comm => (
                  <div key={comm.id} className="p-2.5 rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-xs">
                    <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
                      <span className="font-bold text-slate-700 dark:text-slate-300">{comm.author}</span>
                      <span>{comm.date}</span>
                    </div>
                    <p className="text-slate-600 dark:text-slate-300">{comm.text}</p>
                  </div>
                ))}
              </div>

              {/* Add comment */}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newCommentText}
                  onChange={e => setNewCommentText(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAddComment()}
                  placeholder="Add note or rationale..."
                  className="flex-1 px-3 py-1.5 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
                />
                <Button size="sm" onClick={handleAddComment} icon={Send}>Post</Button>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-between items-center">
              <Button
                variant="outline"
                size="xs"
                icon={FileText}
                onClick={() => {
                  const featId = inspectingFeature.id
                  setInspectingFeature(null)
                  navigate(`/prd-generator?featureId=${featId}`, { state: { featureId: featId } })
                }}
              >
                Generate PRD
              </Button>
              <Button size="xs" onClick={() => setInspectingFeature(null)}>Close</Button>
            </div>
          </div>
        </Modal>
      )}
        </>
      )}
    </div>
  )
}

export default PrioritizationPage
