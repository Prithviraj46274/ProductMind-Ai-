import React, { useState, useMemo } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import {
  Search,
  Filter,
  Plus,
  Upload,
  Download,
  Trash2,
  Edit2,
  Link as LinkIcon,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  Tag,
  ArrowUpDown,
  LayoutGrid,
  Table as TableIcon,
  ChevronLeft,
  ChevronRight,
  X,
  FileSpreadsheet,
  Eye,
  Layers,
  ExternalLink,
  MessageSquareText,
  Loader2,
  Brain,
  Quote,
} from 'lucide-react'
import { Card, Badge, Button, Modal, DemoModeBanner, AIClassificationCard } from '../components/common'
import { parseFeedbackCSV, generateSampleCSV, exportFeedbackToCSV } from '../services/csvService'
import { feedbackService } from '../services/api/feedbackService'
import { useWorkspace } from '../context/WorkspaceContext'
import { InsightsPage } from './InsightsPage'

export function FeedbackPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get('tab') === 'insights' ? 'insights' : 'feedback'

  const handleTabChange = (tab) => {
    if (tab === 'insights') {
      setSearchParams({ tab: 'insights' })
    } else {
      setSearchParams({})
    }
  }

  const {
    feedback,
    features,
    addFeedback,
    updateFeedback,
    deleteFeedback,
    bulkUpdateFeedback,
    bulkDeleteFeedback,
    importFeedbackBatch,
    savedViews,
    setSavedViews,
    addToast,
  } = useApp()

  // View mode
  const [viewMode, setViewMode] = useState('table') // 'table' or 'card'

  // Search & Filter state
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('All')
  const [selectedSentiment, setSelectedSentiment] = useState('All')
  const [selectedPriority, setSelectedPriority] = useState('All')
  const [linkedFilter, setLinkedFilter] = useState('all') // 'all', 'linked', 'unlinked'
  const [sortBy, setSortBy] = useState('newest') // 'newest', 'oldest', 'priority'

  // Pagination state
  const [pageSize, setPageSize] = useState(8)
  const [currentPage, setCurrentPage] = useState(1)

  // Selection for bulk actions
  const [selectedIds, setSelectedIds] = useState([])

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const { currentWorkspace } = useWorkspace()
  const [inspectingFeedbackItem, setInspectingFeedbackItem] = useState(null)
  const [aiAnalysis, setAiAnalysis] = useState(null)
  const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false)
  const [analysisError, setAnalysisError] = useState(null)
  const [isBatchAnalyzing, setIsBatchAnalyzing] = useState(false)
  const [showCSVModal, setShowCSVModal] = useState(false)
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(null) // holds matched duplicates

  // Create/Edit form state
  const [formTitle, setFormTitle] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formCustomer, setFormCustomer] = useState('')
  const [formCompany, setFormCompany] = useState('')
  const [formCategory, setFormCategory] = useState('Feature Requests')
  const [formSentiment, setFormSentiment] = useState('Neutral')
  const [formPriority, setFormPriority] = useState('Medium')
  const [formTags, setFormTags] = useState([])
  const [formTagInput, setFormTagInput] = useState('')
  const [formLinkedFeatureId, setFormLinkedFeatureId] = useState('')

  // CSV Import state
  const [csvPreview, setCsvPreview] = useState(null)
  const [csvError, setCsvError] = useState('')

  // Categories list
  const categories = ['All', 'Performance', 'Integrations', 'Usability', 'Reliability', 'Pricing', 'Feature Requests', 'Satisfaction']
  const sentiments = ['All', 'Positive', 'Neutral', 'Negative']
  const priorities = ['All', 'Urgent', 'High', 'Medium', 'Low']

  // Update title
  const handleTitleChange = (val) => {
    setFormTitle(val)
  }

  // Filtered and Sorted list
  const filteredFeedback = useMemo(() => {
    return feedback.filter(item => {
      // Text search
      if (searchTerm) {
        const q = searchTerm.toLowerCase()
        const matchTitle = item.title.toLowerCase().includes(q)
        const matchDesc = item.description.toLowerCase().includes(q)
        const matchCust = item.customer.toLowerCase().includes(q)
        const matchComp = item.company.toLowerCase().includes(q)
        const matchTags = item.tags?.some(t => t.toLowerCase().includes(q))
        if (!matchTitle && !matchDesc && !matchCust && !matchComp && !matchTags) return false
      }

      // Category filter
      if (selectedCategory !== 'All' && item.category !== selectedCategory) return false

      // Sentiment filter
      if (selectedSentiment !== 'All' && item.sentiment !== selectedSentiment) return false

      // Priority filter
      if (selectedPriority !== 'All' && item.priority !== selectedPriority) return false

      // Linked status filter
      if (linkedFilter === 'linked' && !item.linkedFeatureId) return false
      if (linkedFilter === 'unlinked' && item.linkedFeatureId) return false

      return true
    }).sort((a, b) => {
      if (sortBy === 'newest') return new Date(b.date) - new Date(a.date)
      if (sortBy === 'oldest') return new Date(a.date) - new Date(b.date)
      if (sortBy === 'priority') {
        const pOrder = { Urgent: 4, High: 3, Medium: 2, Low: 1 }
        return (pOrder[b.priority] || 0) - (pOrder[a.priority] || 0)
      }
      return 0
    })
  }, [feedback, searchTerm, selectedCategory, selectedSentiment, selectedPriority, linkedFilter, sortBy])

  // Pagination slicing
  const totalPages = Math.ceil(filteredFeedback.length / pageSize) || 1
  const paginatedFeedback = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredFeedback.slice(start, start + pageSize)
  }, [filteredFeedback, currentPage, pageSize])

  // Clear filters
  const clearFilters = () => {
    setSearchTerm('')
    setSelectedCategory('All')
    setSelectedSentiment('All')
    setSelectedPriority('All')
    setLinkedFilter('all')
    setSortBy('newest')
    setCurrentPage(1)
  }

  // Active filters count
  const hasActiveFilters = searchTerm || selectedCategory !== 'All' || selectedSentiment !== 'All' || selectedPriority !== 'All' || linkedFilter !== 'all'

  // Open Inspect and load AI Intelligence
  const handleOpenInspect = async (item) => {
    setInspectingFeedbackItem(item)
    setAiAnalysis(item.analysis || null)
    setAnalysisError(null)

    if (item.id) {
      try {
        const cached = await feedbackService.getFeedbackAnalysis(item.id)
        if (cached?.analysis) {
          setAiAnalysis(cached.analysis)
        }
      } catch {
        // Not analyzed yet
      }
    }
  }

  // Trigger real Feedback Intelligence Agent analysis
  const handleRunAIAnalysis = async (force = true) => {
    if (!inspectingFeedbackItem?.id) return
    setIsLoadingAnalysis(true)
    setAnalysisError(null)
    try {
      const res = await feedbackService.analyzeFeedback(inspectingFeedbackItem.id, force)
      if (res?.analysis) {
        setAiAnalysis(res.analysis)
        // Also update local feedback item with new category/sentiment
        updateFeedback(inspectingFeedbackItem.id, {
          category: res.analysis.category,
          sentiment: res.analysis.sentiment,
          priority: res.analysis.urgency === 'Critical' ? 'Urgent' : res.analysis.urgency,
          analysis: res.analysis,
        })
        addToast('Feedback Intelligence analysis complete!', 'success')
      }
    } catch (err) {
      const msg = err?.message || 'AI analysis request failed'
      setAnalysisError(msg)
      addToast(msg, 'error')
    } finally {
      setIsLoadingAnalysis(false)
    }
  }

  // Submit Feedback
  const handleSaveFeedback = async (forceProceed = false) => {
    if (!formTitle.trim()) {
      addToast('Please provide a feedback title', 'warning')
      return
    }

    // Check duplicates if creating new
    if (!editingItem && !forceProceed) {
      const duplicates = feedback.filter(
        f => f.title.toLowerCase().trim() === formTitle.toLowerCase().trim()
      )
      if (duplicates.length > 0) {
        setShowDuplicateWarning(duplicates)
        return
      }
    }

    const payload = {
      title: formTitle,
      description: formDescription,
      customer: formCustomer || 'Anonymous Customer',
      company: formCompany || 'Independent Account',
      category: formCategory,
      sentiment: formSentiment,
      priority: formPriority,
      tags: formTags.length > 0 ? formTags : ['general'],
      linkedFeatureId: formLinkedFeatureId || null,
      workspaceId: currentWorkspace?.id,
    }

    if (editingItem) {
      updateFeedback(editingItem.id, payload)
    } else {
      await addFeedback(payload)
    }

    setShowCreateModal(false)
    setEditingItem(null)
    setShowDuplicateWarning(null)
    resetForm()
  }

  const resetForm = () => {
    setFormTitle('')
    setFormDescription('')
    setFormCustomer('')
    setFormCompany('')
    setFormCategory('Feature Requests')
    setFormSentiment('Neutral')
    setFormPriority('Medium')
    setFormTags([])
    setFormLinkedFeatureId('')
  }

  const handleEdit = (item) => {
    setEditingItem(item)
    setFormTitle(item.title)
    setFormDescription(item.description)
    setFormCustomer(item.customer)
    setFormCompany(item.company)
    setFormCategory(item.category)
    setFormSentiment(item.sentiment)
    setFormPriority(item.priority)
    setFormTags(item.tags || [])
    setFormLinkedFeatureId(item.linkedFeatureId || '')
    setShowCreateModal(true)
  }

  // Tag helper
  const addTag = () => {
    if (formTagInput.trim() && !formTags.includes(formTagInput.trim())) {
      setFormTags([...formTags, formTagInput.trim().toLowerCase()])
      setFormTagInput('')
    }
  }

  const removeTag = (t) => {
    setFormTags(formTags.filter(x => x !== t))
  }

  // Bulk actions
  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedIds(paginatedFeedback.map(f => f.id))
    } else {
      setSelectedIds([])
    }
  }

  const toggleSelectOne = (id) => {
    setSelectedIds(prev => (prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]))
  }

  // CSV file upload handler
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (event) => {
      const text = event.target?.result
      if (typeof text === 'string') {
        const parsed = parseFeedbackCSV(text)
        if (parsed.success) {
          setCsvPreview(parsed)
          setCsvError('')
        } else {
          setCsvError(parsed.error || 'Failed to parse CSV file.')
          setCsvPreview(null)
        }
      }
    }
    reader.readAsText(file)
  }

  const confirmCSVImport = () => {
    if (csvPreview && csvPreview.records.length > 0) {
      importFeedbackBatch(csvPreview.records)
      setShowCSVModal(false)
      setCsvPreview(null)
    }
  }

  const downloadSample = () => {
    const sample = generateSampleCSV()
    const blob = new Blob([sample], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', 'product_mind_sample_feedback.csv')
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const exportCurrentFiltered = () => {
    const csvContent = exportFeedbackToCSV(filteredFeedback)
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `feedback_export_${new Date().toISOString().split('T')[0]}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    addToast(`Exported ${filteredFeedback.length} feedback items to CSV`, 'success')
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Primary Workflow Sub-Tabs: Feedback Triage vs AI Insights */}
      <div className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-800 pb-2">
        <button
          onClick={() => handleTabChange('feedback')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'feedback'
              ? 'bg-brand-600 text-white shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <MessageSquareText className="w-4 h-4" />
          <span>Feedback Records & Triage</span>
        </button>

        <button
          onClick={() => handleTabChange('insights')}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
            activeTab === 'insights'
              ? 'bg-brand-600 text-white shadow-sm'
              : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span>AI Insights & Clustering</span>
          <span
            className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
              activeTab === 'insights'
                ? 'bg-white/20 text-white'
                : 'bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20'
            }`}
          >
            NLP Intelligence
          </span>
        </button>
      </div>

      {activeTab === 'insights' ? (
        <InsightsPage />
      ) : (
        <>
          {/* Demo / Live Status Banner */}
          <DemoModeBanner
            message="Displaying sample feedback intelligence with deterministic sentiment, smart tagging, and duplicate detection. Connected to local workspace store."
          />

          {/* Header bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">Customer Feedback Explorer</h2>
                <Badge variant="brand">Intelligence Corpus</Badge>
              </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Manage qualitative user sentiment, duplicate detection, smart tagging, and feature linking
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Aggregation pipeline shortcut */}
          <Link to="/aggregation">
            <Button variant="secondary" size="sm" icon={Layers}>
              Aggregation Clusters
            </Button>
          </Link>

          {/* CSV Import button */}
          <Button
            variant="outline"
            size="sm"
            icon={Upload}
            onClick={() => setShowCSVModal(true)}
          >
            Import CSV
          </Button>

          {/* Export CSV button */}
          <Button
            variant="outline"
            size="sm"
            icon={Download}
            onClick={exportCurrentFiltered}
          >
            Export
          </Button>

          {/* New Feedback button */}
          <Button
            variant="primary"
            size="sm"
            icon={Plus}
            onClick={() => {
              resetForm()
              setEditingItem(null)
              setShowCreateModal(true)
            }}
          >
            Add Feedback
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <Card className="p-4 space-y-3">
        <div className="flex flex-col md:flex-row md:items-center gap-3">
          {/* Search box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={e => {
                setSearchTerm(e.target.value)
                setCurrentPage(1)
              }}
              placeholder="Search feedback titles, descriptions, customers, or tags..."
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          {/* Category Dropdown */}
          <div className="flex items-center gap-2">
            <select
              value={selectedCategory}
              onChange={e => {
                setSelectedCategory(e.target.value)
                setCurrentPage(1)
              }}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none"
            >
              {categories.map(c => (
                <option key={c} value={c}>Category: {c}</option>
              ))}
            </select>

            {/* Sentiment Dropdown */}
            <select
              value={selectedSentiment}
              onChange={e => {
                setSelectedSentiment(e.target.value)
                setCurrentPage(1)
              }}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none"
            >
              {sentiments.map(s => (
                <option key={s} value={s}>Sentiment: {s}</option>
              ))}
            </select>

            {/* Priority Dropdown */}
            <select
              value={selectedPriority}
              onChange={e => {
                setSelectedPriority(e.target.value)
                setCurrentPage(1)
              }}
              className="px-2.5 py-1.5 text-xs font-medium rounded-lg bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none"
            >
              {priorities.map(p => (
                <option key={p} value={p}>Priority: {p}</option>
              ))}
            </select>

            {/* View Mode Toggle */}
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
            </div>
          </div>
        </div>

        {/* Active Filters Row */}
        <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-100 dark:border-slate-800/80">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] text-slate-400">
              Showing <strong>{filteredFeedback.length}</strong> records
            </span>
            {hasActiveFilters && (
              <button
                onClick={clearFilters}
                className="text-[11px] font-semibold text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1"
              >
                <X className="w-3 h-3" />
                <span>Clear Filters</span>
              </button>
            )}
          </div>

          {/* Bulk Action Bar (when items selected) */}
          {selectedIds.length > 0 && (
            <div className="flex items-center gap-2 animate-fadeIn">
              <span className="text-xs font-bold text-brand-600 dark:text-brand-400">
                {selectedIds.length} selected
              </span>
              <button
                onClick={() => {
                  bulkDeleteFeedback(selectedIds)
                  setSelectedIds([])
                }}
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-rose-50 text-rose-600 dark:bg-rose-950/60 dark:text-rose-300 text-xs font-semibold hover:bg-rose-100"
              >
                <Trash2 className="w-3 h-3" />
                <span>Delete Selected</span>
              </button>
            </div>
          )}
        </div>
      </Card>

      {/* Main Content: Table or Card View */}
      {filteredFeedback.length === 0 ? (
        <Card className="p-12 text-center">
          <MessageSquareText className="w-12 h-12 text-slate-300 dark:text-slate-700 mx-auto mb-3" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">No feedback records match your filters</h3>
          <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
            Try adjusting your search query, clearing filters, or adding new customer tickets.
          </p>
          <Button variant="outline" size="sm" onClick={clearFilters} className="mt-4">
            Reset Filters
          </Button>
        </Card>
      ) : viewMode === 'table' ? (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 dark:bg-navy-950/60 border-b border-slate-200 dark:border-slate-800 text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                  <th className="py-3 px-4 w-8">
                    <input
                      type="checkbox"
                      onChange={handleSelectAll}
                      checked={selectedIds.length === paginatedFeedback.length && paginatedFeedback.length > 0}
                      className="rounded text-brand-600 focus:ring-brand-500"
                    />
                  </th>
                  <th className="py-3 px-4">Title & Context</th>
                  <th className="py-3 px-4">Customer</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4">Sentiment</th>
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Linked Feature</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                {paginatedFeedback.map(item => {
                  const linkedFeat = features.find(f => f.id === item.linkedFeatureId)
                  return (
                    <tr
                      key={item.id}
                      className="hover:bg-slate-50/70 dark:hover:bg-navy-950/40 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(item.id)}
                          onChange={() => toggleSelectOne(item.id)}
                          className="rounded text-brand-600 focus:ring-brand-500"
                        />
                      </td>
                      <td className="py-3 px-4 max-w-sm">
                        <div className="flex flex-col">
                          <button
                            onClick={() => handleOpenInspect(item)}
                            className="font-bold text-slate-900 dark:text-white line-clamp-1 text-left hover:text-brand-600 dark:hover:text-brand-400 cursor-pointer"
                            title="Click to view full detail and AI classification"
                          >
                            {item.title}
                          </button>
                          <span className="text-slate-400 line-clamp-1 mt-0.5">
                            {item.description}
                          </span>
                          <div className="flex items-center gap-1.5 mt-1">
                            {item.tags?.map(t => (
                              <span key={t} className="text-[9px] px-1.5 py-0.2 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                                #{t}
                              </span>
                            ))}
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="font-semibold text-slate-800 dark:text-slate-200 block">{item.customer}</span>
                        <span className="text-[10px] text-slate-400 block">{item.company}</span>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant="brand">{item.category}</Badge>
                      </td>
                      <td className="py-3 px-4">
                        <Badge
                          variant={item.sentiment === 'Positive' ? 'success' : item.sentiment === 'Negative' ? 'danger' : 'default'}
                        >
                          {item.sentiment}
                        </Badge>
                      </td>
                      <td className="py-3 px-4">
                        <Badge
                          variant={item.priority === 'Urgent' ? 'danger' : item.priority === 'High' ? 'warning' : 'default'}
                        >
                          {item.priority}
                        </Badge>
                      </td>
                      <td className="py-3 px-4">
                        {linkedFeat ? (
                          <button
                            onClick={() => navigate('/prioritization')}
                            className="inline-flex items-center gap-1 text-[11px] font-semibold text-brand-600 dark:text-brand-400 hover:underline cursor-pointer"
                            title="View in Prioritization Matrix"
                          >
                            <LinkIcon className="w-3 h-3" />
                            <span className="truncate max-w-[120px]">{linkedFeat.name}</span>
                          </button>
                        ) : (
                          <span className="text-[11px] text-slate-400 italic">Unlinked</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => handleOpenInspect(item)}
                            className="p-1 text-slate-400 hover:text-brand-600 dark:hover:text-brand-400 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800"
                            title="Inspect AI Classification & Traceability"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleEdit(item)}
                            className="p-1 text-slate-400 hover:text-brand-600 dark:hover:text-brand-400 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800"
                            title="Edit Feedback"
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => deleteFeedback(item.id)}
                            className="p-1 text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 rounded-md hover:bg-slate-100 dark:hover:bg-slate-800"
                            title="Delete Feedback"
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
      ) : (
        /* Card View */
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {paginatedFeedback.map(item => {
            const linkedFeat = features.find(f => f.id === item.linkedFeatureId)
            return (
              <Card key={item.id} className="p-4 flex flex-col justify-between" hover>
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <button
                      onClick={() => handleOpenInspect(item)}
                      className="text-sm font-bold text-slate-900 dark:text-white line-clamp-1 text-left hover:text-brand-600 dark:hover:text-brand-400 cursor-pointer"
                    >
                      {item.title}
                    </button>
                    <Badge variant={item.priority === 'Urgent' ? 'danger' : item.priority === 'High' ? 'warning' : 'default'}>
                      {item.priority}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 leading-relaxed line-clamp-2">
                    {item.description}
                  </p>
                  <div className="flex items-center gap-2 mt-3 flex-wrap">
                    <Badge variant="brand">{item.category}</Badge>
                    <Badge variant={item.sentiment === 'Positive' ? 'success' : item.sentiment === 'Negative' ? 'danger' : 'default'}>
                      {item.sentiment}
                    </Badge>
                    {item.tags?.slice(0, 3).map(t => (
                      <span key={t} className="text-[10px] text-slate-400">#{t}</span>
                    ))}
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">{item.customer} • {item.company}</span>
                  <div className="flex items-center gap-2">
                    <button onClick={() => handleEdit(item)} className="text-brand-600 dark:text-brand-400 hover:underline">Edit</button>
                    <button onClick={() => deleteFeedback(item.id)} className="text-rose-500 hover:underline">Delete</button>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Pagination Controls */}
      <div className="flex items-center justify-between pt-2">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>Show per page:</span>
          <select
            value={pageSize}
            onChange={e => {
              setPageSize(Number(e.target.value))
              setCurrentPage(1)
            }}
            className="px-2 py-1 rounded bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-xs"
          >
            <option value={5}>5</option>
            <option value={8}>8</option>
            <option value={15}>15</option>
            <option value={30}>30</option>
          </select>
        </div>

        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <span>Page {currentPage} of {totalPages}</span>
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="p-1 rounded border border-slate-200 dark:border-slate-800 disabled:opacity-40"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button
            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="p-1 rounded border border-slate-200 dark:border-slate-800 disabled:opacity-40"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Create / Edit Feedback Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => {
          setShowCreateModal(false)
          setEditingItem(null)
        }}
        title={editingItem ? 'Edit Feedback Record' : 'Record New Customer Feedback'}
        subtitle="Automatic AI categorization and duplicate detection enabled"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Feedback Title *
            </label>
            <input
              type="text"
              value={formTitle}
              onChange={e => handleTitleChange(e.target.value)}
              placeholder="e.g. Slow table rendering with 5,000+ customer records"
              className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Customer Quote or Detailed Description
            </label>
            <textarea
              rows={3}
              value={formDescription}
              onChange={e => setFormDescription(e.target.value)}
              placeholder="What specifically happened? What pain or opportunity was described?"
              className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Customer Name
              </label>
              <input
                type="text"
                value={formCustomer}
                onChange={e => setFormCustomer(e.target.value)}
                placeholder="e.g. Sarah Jenkins"
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Company / Account
              </label>
              <input
                type="text"
                value={formCompany}
                onChange={e => setFormCompany(e.target.value)}
                placeholder="e.g. FinTech Dynamics"
                className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Category
              </label>
              <select
                value={formCategory}
                onChange={e => setFormCategory(e.target.value)}
                className="w-full px-2.5 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
              >
                {categories.filter(c => c !== 'All').map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Sentiment
              </label>
              <select
                value={formSentiment}
                onChange={e => setFormSentiment(e.target.value)}
                className="w-full px-2.5 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
              >
                <option value="Positive">Positive</option>
                <option value="Neutral">Neutral</option>
                <option value="Negative">Negative</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
                Priority
              </label>
              <select
                value={formPriority}
                onChange={e => setFormPriority(e.target.value)}
                className="w-full px-2.5 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
              >
                <option value="Urgent">Urgent</option>
                <option value="High">High</option>
                <option value="Medium">Medium</option>
                <option value="Low">Low</option>
              </select>
            </div>
          </div>

          {/* Link to Feature */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Associated Feature
            </label>
            <select
              value={formLinkedFeatureId}
              onChange={e => setFormLinkedFeatureId(e.target.value)}
              className="w-full px-2.5 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
            >
              <option value="">None (Unlinked)</option>
              {features.map(f => (
                <option key={f.id} value={f.id}>{f.name} (Score: {f.score.toFixed(2)})</option>
              ))}
            </select>
          </div>

          {/* Smart Tags */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Smart Tags
            </label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={formTagInput}
                onChange={e => setFormTagInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addTag())}
                placeholder="Type tag and press Enter"
                className="flex-1 px-3 py-1.5 text-xs rounded-lg bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
              />
              <Button size="sm" variant="outline" onClick={addTag}>Add</Button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {formTags.map(tag => (
                <span key={tag} className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300 border border-brand-200 dark:border-brand-800/60">
                  #{tag}
                  <button type="button" onClick={() => removeTag(tag)} className="hover:text-rose-500">×</button>
                </span>
              ))}
            </div>
          </div>

          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowCreateModal(false)}>Cancel</Button>
            <Button variant="primary" onClick={() => handleSaveFeedback(false)}>
              {editingItem ? 'Save Changes' : 'Create Record'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* Duplicate Detection Warning Modal */}
      <Modal
        isOpen={!!showDuplicateWarning}
        onClose={() => setShowDuplicateWarning(null)}
        title="Potential Duplicate Feedback Detected"
        subtitle="Our similarity engine identified similar tickets in your workspace"
      >
        <div className="space-y-4">
          <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-200 flex items-start gap-2.5">
            <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Similar Customer Request Found</p>
              <p className="mt-0.5 leading-relaxed">
                To prevent backlog clutter, consider consolidating this feedback or linking to the existing master feature.
              </p>
            </div>
          </div>

          <div className="space-y-2">
            {showDuplicateWarning?.map(({ feedback: dup, similarity }) => (
              <div key={dup.id} className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-slate-900 dark:text-white">{dup.title}</span>
                  <Badge variant="warning">{similarity}% Match</Badge>
                </div>
                <p className="text-slate-500 dark:text-slate-400 line-clamp-2">{dup.description}</p>
                <div className="flex items-center justify-between text-[10px] text-slate-400 mt-2">
                  <span>Customer: {dup.customer} ({dup.company})</span>
                  <span>ID: {dup.id}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowDuplicateWarning(null)}>
              Cancel & Review
            </Button>
            <Button variant="primary" onClick={() => handleSaveFeedback(true)}>
              Proceed Anyway
            </Button>
          </div>
        </div>
      </Modal>

      {/* CSV Import Modal */}
      <Modal
        isOpen={showCSVModal}
        onClose={() => {
          setShowCSVModal(false)
          setCsvPreview(null)
          setCsvError('')
        }}
        title="Import Customer Feedback via CSV"
        subtitle="Batch upload with automatic column mapping, validation, and smart tagging"
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-xs">
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="w-5 h-5 text-brand-500" />
              <div>
                <p className="font-bold text-slate-800 dark:text-slate-200">Need a CSV template?</p>
                <p className="text-[11px] text-slate-400">Download formatted sample containing required headers</p>
              </div>
            </div>
            <Button variant="outline" size="xs" onClick={downloadSample} icon={Download}>
              Download Sample
            </Button>
          </div>

          <div className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-2xl p-6 text-center hover:border-brand-500 transition-colors">
            <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
            <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Drag & drop CSV file or click to browse
            </p>
            <p className="text-[10px] text-slate-400 mt-1">Accepts standard .csv exports</p>
            <input
              type="file"
              accept=".csv"
              onChange={handleFileUpload}
              className="mt-3 block w-full text-xs text-slate-500 file:mr-4 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100 dark:file:bg-brand-950/60 dark:file:text-brand-300 cursor-pointer"
            />
          </div>

          {csvError && (
            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300">
              {csvError}
            </div>
          )}

          {csvPreview && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Validated {csvPreview.records.length} records ready to import</span>
                </span>
                {csvPreview.errors.length > 0 && (
                  <span className="text-amber-500 text-[11px]">{csvPreview.errors.length} skipped</span>
                )}
              </div>

              <div className="max-h-48 overflow-y-auto border border-slate-200 dark:border-slate-800 rounded-xl divide-y divide-slate-100 dark:divide-slate-800">
                {csvPreview.records.slice(0, 5).map((r, i) => (
                  <div key={i} className="p-2.5 text-xs">
                    <p className="font-semibold text-slate-900 dark:text-white line-clamp-1">{r.title}</p>
                    <p className="text-[11px] text-slate-400">{r.customer} • {r.category} • {r.priority}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowCSVModal(false)}>Cancel</Button>
            <Button
              variant="primary"
              disabled={!csvPreview || csvPreview.records.length === 0}
              onClick={confirmCSVImport}
            >
              Confirm Import ({csvPreview?.records?.length || 0})
            </Button>
          </div>
        </div>
      </Modal>

      {/* Feedback Detail & AI Classification Modal */}
      {inspectingFeedbackItem && (
        <Modal
          isOpen={Boolean(inspectingFeedbackItem)}
          onClose={() => setInspectingFeedbackItem(null)}
          title={inspectingFeedbackItem.title}
          subtitle={`Source Record ID: ${inspectingFeedbackItem.id} • ${inspectingFeedbackItem.customer} (${inspectingFeedbackItem.company})`}
          maxWidth="max-w-2xl"
        >
          <div className="space-y-4">
            {/* Full description */}
            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-200 leading-relaxed">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                Original Customer Feedback Statement
              </span>
              <p>{inspectingFeedbackItem.description}</p>
            </div>

            {/* AI Analysis Trigger Header */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-brand-600 dark:text-brand-400" />
                <span className="text-xs font-bold text-slate-900 dark:text-white">
                  Feedback Intelligence Agent
                </span>
              </div>
              <Button
                variant="primary"
                size="xs"
                disabled={isLoadingAnalysis}
                onClick={() => handleRunAIAnalysis(Boolean(aiAnalysis))}
                icon={isLoadingAnalysis ? Loader2 : Sparkles}
              >
                {isLoadingAnalysis
                  ? 'Analyzing with AI...'
                  : aiAnalysis
                  ? 'Re-analyze with AI'
                  : 'Analyze with AI'}
              </Button>
            </div>

            {analysisError && (
              <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-600 dark:text-rose-400 text-xs">
                {analysisError}
              </div>
            )}

            {/* AI Classification Card Component */}
            <AIClassificationCard
              category={aiAnalysis?.category || inspectingFeedbackItem.category}
              sentiment={aiAnalysis?.sentiment || inspectingFeedbackItem.sentiment}
              themes={aiAnalysis?.secondary_tags || aiAnalysis?.subthemes || inspectingFeedbackItem.tags || []}
              confidence={aiAnalysis?.confidence ?? 0.92}
              status={isLoadingAnalysis ? 'processing' : aiAnalysis ? 'completed' : 'pending'}
            />

            {/* Grounded AI Analysis Findings */}
            {aiAnalysis && (
              <div className="space-y-3">
                {/* Pain Point & Suggested Action */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-900 dark:text-amber-200">
                    <span className="text-[10px] font-bold uppercase tracking-wider block text-amber-600 dark:text-amber-400 mb-1">
                      Customer Pain Point
                    </span>
                    <p>{aiAnalysis.customer_pain_point}</p>
                  </div>

                  <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-900 dark:text-emerald-200">
                    <span className="text-[10px] font-bold uppercase tracking-wider block text-emerald-600 dark:text-emerald-400 mb-1">
                      Recommended Action
                    </span>
                    <p>{aiAnalysis.suggested_action}</p>
                  </div>
                </div>

                {/* Urgency & Urgency Explanation */}
                {aiAnalysis.urgency && (
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-slate-800 text-xs">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Operational Urgency:
                      </span>
                      <Badge
                        variant={
                          aiAnalysis.urgency === 'Critical' || aiAnalysis.urgency === 'High'
                            ? 'danger'
                            : 'warning'
                        }
                      >
                        {aiAnalysis.urgency}
                      </Badge>
                    </div>
                    {aiAnalysis.urgency_explanation && (
                      <p className="text-slate-600 dark:text-slate-400 mt-1">
                        {aiAnalysis.urgency_explanation}
                      </p>
                    )}
                  </div>
                )}

                {/* Grounded Evidence Excerpts */}
                {aiAnalysis.evidence && aiAnalysis.evidence.length > 0 && (
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-slate-800 text-xs space-y-1.5">
                    <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                      <Quote className="w-3 h-3 text-brand-500" />
                      <span>Grounded Evidence Excerpts</span>
                    </div>
                    <ul className="list-disc list-inside space-y-1 text-slate-700 dark:text-slate-300 italic">
                      {aiAnalysis.evidence.map((quote, idx) => (
                        <li key={idx} className="line-clamp-2">
                          &ldquo;{quote}&rdquo;
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Traceability & Navigation to Downstream Artifacts */}
            <div className="p-3.5 rounded-xl bg-brand-50/50 dark:bg-brand-950/30 border border-brand-200/60 dark:border-brand-800/60 text-xs space-y-2">
              <span className="text-[10px] font-bold text-brand-700 dark:text-brand-300 uppercase tracking-wider block">
                Workflow Traceability & Requirements Linking
              </span>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="xs"
                  icon={Layers}
                  onClick={() => {
                    setInspectingFeedbackItem(null)
                    navigate('/aggregation')
                  }}
                >
                  View in Feature Aggregation
                </Button>

                <Button
                  variant="outline"
                  size="xs"
                  icon={LinkIcon}
                  onClick={() => {
                    setInspectingFeedbackItem(null)
                    navigate('/prioritization')
                  }}
                >
                  View Prioritization Matrix
                </Button>

                <Button
                  variant="outline"
                  size="xs"
                  icon={ExternalLink}
                  onClick={() => {
                    const linkedId = inspectingFeedbackItem.linkedFeatureId
                    setInspectingFeedbackItem(null)
                    if (linkedId) {
                      navigate(`/prd-generator?featureId=${linkedId}`, { state: { featureId: linkedId } })
                    } else {
                      navigate('/prd-generator')
                    }
                  }}
                >
                  Specifications (PRDs)
                </Button>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setInspectingFeedbackItem(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}
        </>
      )}
    </div>
  )
}

export default FeedbackPage
