import React, { useState, useMemo, useEffect, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { useWorkspace } from '../context/WorkspaceContext'
import {
  Layers,
  Sparkles,
  GitMerge,
  CheckCircle2,
  ExternalLink,
  MessageSquare,
  AlertTriangle,
  ArrowRight,
  Filter,
  Search,
  SlidersHorizontal,
  ChevronRight,
  Plus,
  RefreshCw,
  FolderPlus,
  Brain,
  Loader2,
  Users,
} from 'lucide-react'
import { Card, Badge, Button, Modal, DemoModeBanner, EmptyState, LoadingState } from '../components/common'
import { aggregationService } from '../services/api/aggregationService'

export function AggregationPage() {
  const navigate = useNavigate()
  const { feedback, features, addFeature, addToast, updateFeedback } = useApp()
  const { currentWorkspace } = useWorkspace()

  const [searchTerm, setSearchTerm] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('All')

  // Modals
  const [mergeModalSource, setMergeModalSource] = useState(null)
  const [selectedMergeTargetId, setSelectedMergeTargetId] = useState('')
  const [editingGroup, setEditingGroup] = useState(null)
  const [newTitle, setNewTitle] = useState('')

  // Backend state
  const [backendGroups, setBackendGroups] = useState([])
  const [isLoadingBackend, setIsLoadingBackend] = useState(false)
  const [isClustering, setIsClustering] = useState(false)
  const [clusteringError, setClusteringError] = useState(null)

  // Fetch groups from backend on mount or workspace change
  const loadGroups = useCallback(async () => {
    if (!currentWorkspace?.id) return
    setIsLoadingBackend(true)
    try {
      const res = await aggregationService.getFeatureGroups(currentWorkspace.id)
      if (Array.isArray(res) && res.length > 0) {
        setBackendGroups(res)
      }
    } catch (err) {
      console.warn('Could not fetch backend groups:', err)
    } finally {
      setIsLoadingBackend(false)
    }
  }, [currentWorkspace?.id])

  useEffect(() => {
    loadGroups()
  }, [loadGroups])

  // Run AI Grouping
  const handleRunAIGrouping = async () => {
    if (!currentWorkspace?.id) {
      addToast('Please select a workspace first.', 'warning')
      return
    }

    setIsClustering(true)
    setClusteringError(null)

    try {
      const res = await aggregationService.groupFeatures({
        workspaceId: currentWorkspace.id,
        forceRegroup: true,
      })

      if (res?.feature_groups) {
        setBackendGroups(res.feature_groups)
        addToast(
          `AI clustered ${res.total_requests_grouped || 0} feedback items into ${res.total_feature_groups || res.feature_groups.length} feature groups!`,
          'success'
        )
      } else {
        await loadGroups()
      }
    } catch (err) {
      const msg = err?.message || 'Feature Intelligence grouping failed.'
      setClusteringError(msg)
      addToast(msg, 'error')
    } finally {
      setIsClustering(false)
    }
  }

  // Fallback initial groups from local data
  const initialLocalGroups = useMemo(() => {
    return aggregationService.generateAggregatedGroups(feedback, features)
  }, [feedback, features])

  // Map backend groups if available, else local
  const normalizedGroups = useMemo(() => {
    if (backendGroups.length > 0) {
      return backendGroups.map((g) => {
        const title = g.name || g.title || 'Untitled Group'
        const existing = features.find((f) => f.name.toLowerCase() === title.toLowerCase())
        return {
          id: g.id || `grp-${Math.random().toString(36).substring(2, 7)}`,
          title,
          category: g.category || 'Feature',
          primaryTag: g.category || 'General',
          count: g.request_count ?? g.feedback_ids?.length ?? 1,
          uniqueCustomers: g.unique_customers_count ?? 1,
          sentimentDistribution: {
            Positive: g.average_sentiment_score && g.average_sentiment_score > 0 ? 1 : 0,
            Neutral: g.average_sentiment_score === 0 ? 1 : 0,
            Negative: g.average_sentiment_score && g.average_sentiment_score < 0 ? 1 : 0,
          },
          painPoints: g.recurring_pain_points || (g.customer_pain_point ? [g.customer_pain_point] : []),
          excerpts: (g.evidence_quotes || []).map((quote, idx) => ({
            id: `ev-${idx}`,
            customer: 'Customer Voice',
            company: 'Verified Demand',
            snippet: quote,
          })),
          isPromoted: Boolean(existing || g.status === 'promoted' || g.status === 'prioritized'),
          promotedFeatureName: existing?.name || null,
          promotedFeatureScore: existing?.score || null,
          feedbackItems: (g.feedback_ids || []).map((fid) => ({ id: fid })),
          isAIGenerated: true,
        }
      })
    }
    return initialLocalGroups
  }, [backendGroups, initialLocalGroups, features])

  const [customGroups, setCustomGroups] = useState(null)
  const activeGroups = customGroups || normalizedGroups

  const filteredGroups = useMemo(() => {
    return activeGroups.filter(grp => {
      if (searchTerm) {
        const q = searchTerm.toLowerCase()
        const matchTitle = grp.title.toLowerCase().includes(q)
        const matchCat = grp.category.toLowerCase().includes(q)
        const matchTag = grp.primaryTag.toLowerCase().includes(q)
        if (!matchTitle && !matchCat && !matchTag) return false
      }
      if (categoryFilter !== 'All' && grp.category !== categoryFilter) return false
      return true
    })
  }, [activeGroups, searchTerm, categoryFilter])

  // Merge Action
  const handleMergeConfirm = () => {
    if (!mergeModalSource || !selectedMergeTargetId) return
    const merged = aggregationService.mergeGroups(mergeModalSource.id, selectedMergeTargetId, activeGroups)
    setCustomGroups(merged)
    setMergeModalSource(null)
    setSelectedMergeTargetId('')
    addToast('Successfully merged feature request groups', 'success')
  }

  // Promote / Approve group into Prioritization
  const handlePromoteToFeature = (group) => {
    const existing = features.find(f => f.name.toLowerCase() === group.title.toLowerCase())
    if (existing) {
      addToast(`Feature "${existing.name}" is already in the prioritization pipeline`, 'info')
      navigate('/prioritization')
      return
    }

    // Default factors derived from group metrics
    const urgency = group.sentimentDistribution.Negative > 0 ? 8 : 6
    const demand = Math.min(10, Math.max(3, group.count * 2))
    const customerImpact = group.count >= 3 ? 8 : 6
    const businessValue = 7

    const created = addFeature({
      name: group.title,
      description: `Aggregated feature request derived from ${group.count} customer feedback submissions. Primary focus: ${group.primaryTag}.`,
      customerImpact,
      urgency,
      demand,
      businessValue,
      status: 'Evaluating',
      owner: 'Alex Rivera',
      targetRelease: 'v2.5.0',
      relatedFeedbackIds: group.feedbackItems.map(f => f.id),
    })

    // Update feedback items to link to created feature
    group.feedbackItems.forEach(f => {
      updateFeedback(f.id, { linkedFeatureId: created.id })
    })

    addToast(`Approved and promoted "${group.title}" to Feature Prioritization!`, 'success')
    navigate('/prioritization')
  }

  const categories = ['All', 'Performance', 'Integrations', 'Usability', 'Reliability', 'Pricing', 'Satisfaction']

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Demo Banner */}
      <DemoModeBanner
        message="Feature Aggregation identifies common customer requests from raw feedback into clustered decision initiatives. Ready for backend clustering API."
      />

      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Feature Request Aggregation</h2>
            <Badge variant="brand">Cluster Pipeline</Badge>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Group, review, merge, and approve recurring customer demands before scoring in Feature Prioritization
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="primary"
            size="sm"
            disabled={isClustering}
            onClick={handleRunAIGrouping}
            icon={isClustering ? Loader2 : Brain}
          >
            {isClustering ? 'Clustering Feedback...' : 'Run AI Grouping'}
          </Button>

          <Link to="/feedback?tab=insights">
            <Button variant="outline" size="sm" icon={Sparkles}>
              AI Insights
            </Button>
          </Link>
          <Link to="/prioritization">
            <Button variant="secondary" size="sm" icon={SlidersHorizontal}>
              Prioritization Matrix
            </Button>
          </Link>
          <Link to="/feedback">
            <Button variant="outline" size="sm" icon={MessageSquare}>
              Feedback Explorer
            </Button>
          </Link>
        </div>
      </div>

      {clusteringError && (
        <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-600 dark:text-rose-400 text-xs">
          {clusteringError}
        </div>
      )}

      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row items-center gap-3 bg-white dark:bg-navy-900 p-3 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            placeholder="Search aggregated requests by theme, category, or customer excerpt..."
            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <select
            value={categoryFilter}
            onChange={e => setCategoryFilter(e.target.value)}
            className="w-full sm:w-auto px-3 py-1.5 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {categories.map(cat => (
              <option key={cat} value={cat}>
                {cat === 'All' ? 'All Categories' : cat}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Aggregated Feature Cards Grid */}
      {filteredGroups.length === 0 ? (
        <EmptyState
          icon={Layers}
          title="No aggregated request groups found"
          description="Try broadening your search term or importing additional customer feedback."
          actionLabel="Go to Feedback Explorer"
          onAction={() => navigate('/feedback')}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredGroups.map(group => {
            return (
              <Card key={group.id} className="p-5 flex flex-col justify-between" hover>
                <div>
                  {/* Category & Count Pill */}
                  <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300 border border-brand-200 dark:border-brand-800/60">
                      {group.category}
                    </span>
                    <span className="text-xs font-bold text-slate-600 dark:text-slate-300 font-mono flex items-center gap-1">
                      <MessageSquare className="w-3.5 h-3.5 text-brand-500" />
                      {group.count} feedback {group.count === 1 ? 'record' : 'records'}
                    </span>
                  </div>

                  {/* Title */}
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-snug">
                    {group.title}
                  </h3>

                  {/* Sentiment Breakdown Pill */}
                  <div className="flex items-center gap-2 mt-2.5">
                    <span className="text-[10px] text-slate-400">Sentiment:</span>
                    {group.sentimentDistribution.Positive > 0 && (
                      <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                        {group.sentimentDistribution.Positive} Pos
                      </span>
                    )}
                    {group.sentimentDistribution.Neutral > 0 && (
                      <span className="text-[10px] font-semibold text-sky-600 dark:text-sky-400">
                        {group.sentimentDistribution.Neutral} Neu
                      </span>
                    )}
                    {group.sentimentDistribution.Negative > 0 && (
                      <span className="text-[10px] font-semibold text-rose-600 dark:text-rose-400">
                        {group.sentimentDistribution.Negative} Neg
                      </span>
                    )}
                  </div>

                  {/* Recurring Pain Points */}
                  {group.painPoints.length > 0 && (
                    <div className="mt-3 p-2.5 rounded-xl bg-rose-50/60 dark:bg-rose-950/30 border border-rose-200/60 dark:border-rose-900/40 text-[11px] text-rose-800 dark:text-rose-300">
                      <span className="font-bold block mb-1 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3 text-rose-500" />
                        Top Customer Pain Point:
                      </span>
                      <p className="line-clamp-2 italic">"{group.painPoints[0]}"</p>
                    </div>
                  )}

                  {/* Supporting Feedback Excerpts */}
                  <div className="mt-4 space-y-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                      Supporting Customer Excerpts ({group.excerpts.length})
                    </span>
                    {group.excerpts.map(ex => (
                      <div
                        key={ex.id}
                        onClick={() => navigate('/feedback')}
                        className="p-2 rounded-lg bg-slate-50 dark:bg-navy-950/60 border border-slate-100 dark:border-slate-800/80 hover:border-brand-300 dark:hover:border-brand-700 transition-colors cursor-pointer group"
                        title="Click to view original feedback in Feedback Explorer"
                      >
                        <div className="flex items-center justify-between text-[10px] text-slate-400 mb-0.5">
                          <span className="font-semibold text-slate-700 dark:text-slate-300 truncate">
                            {ex.customer} ({ex.company})
                          </span>
                          <span className="font-mono text-[9px] text-brand-600 dark:text-brand-400 group-hover:underline">
                            {ex.id}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-600 dark:text-slate-400 line-clamp-2 leading-relaxed">
                          {ex.snippet}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Bottom Actions: Merge & Approve */}
                <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-2">
                  <Button
                    variant="ghost"
                    size="xs"
                    icon={GitMerge}
                    onClick={() => setMergeModalSource(group)}
                    title="Merge this group with another request group"
                  >
                    Merge
                  </Button>

                  {group.isPromoted ? (
                    <div className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 font-semibold">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Promoted (Score: {group.promotedFeatureScore?.toFixed(2) || 'Active'})</span>
                    </div>
                  ) : (
                    <Button
                      variant="primary"
                      size="xs"
                      icon={ArrowRight}
                      iconPosition="right"
                      onClick={() => handlePromoteToFeature(group)}
                    >
                      Approve for Prioritization
                    </Button>
                  )}
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Merge Groups Modal */}
      {mergeModalSource && (
        <Modal
          isOpen={Boolean(mergeModalSource)}
          onClose={() => setMergeModalSource(null)}
          title={`Merge: "${mergeModalSource.title}"`}
          subtitle="Combine feedback records into another aggregated feature request"
          maxWidth="max-w-md"
        >
          <div className="space-y-4">
            <p className="text-xs text-slate-600 dark:text-slate-300">
              Select the destination feature group. All {mergeModalSource.count} feedback submissions from this group will be appended to the target group.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Target Feature Group
              </label>
              <select
                value={selectedMergeTargetId}
                onChange={e => setSelectedMergeTargetId(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
              >
                <option value="">-- Choose destination group --</option>
                {activeGroups
                  .filter(g => g.id !== mergeModalSource.id)
                  .map(g => (
                    <option key={g.id} value={g.id}>
                      {g.title} ({g.count} feedback items)
                    </option>
                  ))}
              </select>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
              <Button variant="secondary" size="sm" onClick={() => setMergeModalSource(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={!selectedMergeTargetId}
                onClick={handleMergeConfirm}
              >
                Confirm Merge
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

export default AggregationPage
