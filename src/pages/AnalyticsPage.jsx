import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { useApp } from '../context/AppContext'
import { useWorkspace } from '../context/WorkspaceContext'
import {
  BarChart3,
  Upload,
  Calendar,
  Users,
  Activity,
  Clock,
  Layers,
  ArrowUpRight,
  ArrowDownRight,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts'
import { Card, Badge, Button, Modal, EmptyState, LoadingState, ErrorState } from '../components/common'
import { analyticsService } from '../services/api/analyticsService'

export function AnalyticsPage() {
  const { addToast } = useApp()
  const { currentWorkspace } = useWorkspace()

  // Filter state
  const [timeRange, setTimeRange] = useState('30d') // '7d' | '30d' | '90d' | 'all' | 'custom'
  const [customStartDate, setCustomStartDate] = useState('')
  const [customEndDate, setCustomEndDate] = useState('')
  const [appliedCustomRange, setAppliedCustomRange] = useState({ startDate: null, endDate: null })
  const [dateRangeError, setDateRangeError] = useState(null)

  // Dashboard API state
  const [overview, setOverview] = useState(null)
  const [trends, setTrends] = useState(null)
  const [featuresData, setFeaturesData] = useState(null)
  const [funnelData, setFunnelData] = useState(null)
  const [featureSort, setFeatureSort] = useState('most_used') // 'most_used' | 'least_used' | 'adoption' | 'increasing' | 'declining'
  const [selectedFeature, setSelectedFeature] = useState(null)
  const [featureHistory, setFeatureHistory] = useState([])
  const [featureHistoryLoading, setFeatureHistoryLoading] = useState(false)
  const [featureHistoryError, setFeatureHistoryError] = useState(null)
  const [funnelStepsInput, setFunnelStepsInput] = useState('')
  const [appliedFunnelSteps, setAppliedFunnelSteps] = useState('')
  const [funnelLoading, setFunnelLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [isAuthError, setIsAuthError] = useState(false)
  const [refreshTick, setRefreshTick] = useState(0)

  // Upload modal state
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [uploadFile, setUploadFile] = useState(null)
  const [parsing, setParsing] = useState(false)
  const [parseResult, setParseResult] = useState(null)
  const [manualColumnMap, setManualColumnMap] = useState({})
  const [importing, setImporting] = useState(false)
  const [importProgress, setImportProgress] = useState({ current: 0, total: 0 })
  const [importSummary, setImportSummary] = useState(null)
  const [importError, setImportError] = useState(null)

  const requestIdRef = useRef(0)
  const lastWorkspaceIdRef = useRef(null)

  const fetchAnalytics = useCallback(async () => {
    const wsId = currentWorkspace?.id
    if (!wsId) {
      setOverview(null)
      setTrends(null)
      setFeaturesData(null)
      setFunnelData(null)
      setSelectedFeature(null)
      setLoading(false)
      setRefreshing(false)
      return
    }

    if (timeRange === 'custom' && (!appliedCustomRange.startDate || !appliedCustomRange.endDate)) {
      return
    }

    const reqId = ++requestIdRef.current
    const workspaceChanged = lastWorkspaceIdRef.current !== wsId
    if (workspaceChanged) {
      lastWorkspaceIdRef.current = wsId
      setOverview(null)
      setTrends(null)
      setFeaturesData(null)
      setFunnelData(null)
      setSelectedFeature(null)
      setAppliedFunnelSteps('')
      setFunnelStepsInput('')
    }

    const hasExistingData = !workspaceChanged && (overview !== null || trends !== null)
    if (hasExistingData) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)
    setIsAuthError(false)

    try {
      const queryOpts = {
        workspaceId: wsId,
        timeRange,
        startDate: timeRange === 'custom' ? appliedCustomRange.startDate : null,
        endDate: timeRange === 'custom' ? appliedCustomRange.endDate : null,
      }
      const [overviewRes, trendsRes, featuresRes, funnelRes] = await Promise.all([
        analyticsService.getOverviewMetrics(queryOpts),
        analyticsService.getUsageTrendsFromApi(queryOpts),
        analyticsService.getFeatureAnalyticsFromApi({ ...queryOpts, includeComparison: true }),
        analyticsService.getFunnelAnalyticsFromApi({
          ...queryOpts,
          steps: workspaceChanged ? null : appliedFunnelSteps || null,
        }),
      ])

      if (requestIdRef.current !== reqId) return
      setOverview(overviewRes?.data || null)
      setTrends(trendsRes?.data || null)
      setFeaturesData(featuresRes?.data || null)
      setFunnelData(funnelRes?.data || null)
    } catch (err) {
      if (requestIdRef.current !== reqId) return
      const status = err?.status || err?.response?.status
      if (status === 401) {
        setIsAuthError(true)
        setError('Your session has expired. Please sign in again to load workspace analytics.')
      } else {
        setError(
          err?.response?.data?.detail ||
            err?.message ||
            'Failed to load product analytics from MongoDB Atlas.'
        )
      }
    } finally {
      if (requestIdRef.current === reqId) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [currentWorkspace?.id, timeRange, appliedCustomRange.startDate, appliedCustomRange.endDate, refreshTick])

  useEffect(() => {
    fetchAnalytics()
  }, [fetchAnalytics])

  const handleSelectTimeRange = (nextRange) => {
    setDateRangeError(null)
    setTimeRange(nextRange)
  }

  const handleApplyCustomRange = (e) => {
    e.preventDefault()
    if (!customStartDate || !customEndDate) {
      setDateRangeError('Select both start and end dates.')
      return
    }
    if (customStartDate > customEndDate) {
      setDateRangeError('Start date must be on or before end date.')
      return
    }
    setDateRangeError(null)
    setAppliedCustomRange({ startDate: customStartDate, endDate: customEndDate })
  }

  const handleRetry = () => {
    setRefreshTick((t) => t + 1)
  }

  const handleSelectFeature = async (feat) => {
    setSelectedFeature(feat)
    setFeatureHistory([])
    setFeatureHistoryError(null)
    if (!currentWorkspace?.id) return
    setFeatureHistoryLoading(true)
    try {
      const res = await analyticsService.getUsageTrendsFromApi({
        workspaceId: currentWorkspace.id,
        timeRange,
        startDate: timeRange === 'custom' ? appliedCustomRange.startDate : null,
        endDate: timeRange === 'custom' ? appliedCustomRange.endDate : null,
        featureName: feat.name,
      })
      setFeatureHistory(res?.data?.items || [])
    } catch (err) {
      setFeatureHistoryError(
        err?.response?.data?.detail || err?.message || 'Failed to load feature history.'
      )
    } finally {
      setFeatureHistoryLoading(false)
    }
  }

  const handleEvaluateFunnel = async (e) => {
    if (e) e.preventDefault()
    if (!currentWorkspace?.id) return
    const cleaned = funnelStepsInput
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    if (cleaned.length < 2) {
      addToast('Enter at least 2 comma-separated event steps to evaluate a funnel', 'warning')
      return
    }
    setAppliedFunnelSteps(cleaned.join(','))
    setFunnelLoading(true)
    try {
      const res = await analyticsService.getFunnelAnalyticsFromApi({
        workspaceId: currentWorkspace.id,
        timeRange,
        startDate: timeRange === 'custom' ? appliedCustomRange.startDate : null,
        endDate: timeRange === 'custom' ? appliedCustomRange.endDate : null,
        steps: cleaned,
      })
      setFunnelData(res?.data || null)
    } catch (err) {
      addToast(
        err?.response?.data?.detail || err?.message || 'Failed to evaluate user funnel.',
        'error'
      )
    } finally {
      setFunnelLoading(false)
    }
  }

  const featureItems = featuresData?.items || []
  const sortedFeatures = useMemo(() => {
    const list = [...featureItems]
    if (featureSort === 'least_used') {
      return list.sort((a, b) => a.eventCount - b.eventCount)
    }
    if (featureSort === 'adoption') {
      return list.sort((a, b) => (b.adoptionPercent ?? -1) - (a.adoptionPercent ?? -1))
    }
    if (featureSort === 'increasing') {
      return list
        .filter((f) => typeof f.trendDeltaPercent === 'number' && f.trendDeltaPercent > 0)
        .sort((a, b) => b.trendDeltaPercent - a.trendDeltaPercent)
    }
    if (featureSort === 'declining') {
      return list
        .filter((f) => typeof f.trendDeltaPercent === 'number' && f.trendDeltaPercent < 0)
        .sort((a, b) => a.trendDeltaPercent - b.trendDeltaPercent)
    }
    return list.sort((a, b) => b.eventCount - a.eventCount)
  }, [featureItems, featureSort])

  const mostUsedFeature = useMemo(
    () => (featureItems.length > 0 ? [...featureItems].sort((a, b) => b.eventCount - a.eventCount)[0] : null),
    [featureItems]
  )
  const leastUsedFeature = useMemo(
    () => (featureItems.length > 0 ? [...featureItems].sort((a, b) => a.eventCount - b.eventCount)[0] : null),
    [featureItems]
  )
  const increasingCount = useMemo(
    () => featureItems.filter((f) => typeof f.trendDeltaPercent === 'number' && f.trendDeltaPercent > 0).length,
    [featureItems]
  )
  const decliningCount = useMemo(
    () => featureItems.filter((f) => typeof f.trendDeltaPercent === 'number' && f.trendDeltaPercent < 0).length,
    [featureItems]
  )

  // Handle File Input Selection
  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploadFile(file)
    setParsing(true)
    setParseResult(null)
    setImportSummary(null)
    setImportError(null)

    const reader = new FileReader()
    reader.onload = (event) => {
      const content = event.target?.result
      if (typeof content === 'string') {
        const result = analyticsService.parseAnalyticsFile(content, file.name)
        setParseResult(result)
        if (result.mappedColumns) {
          setManualColumnMap(result.mappedColumns)
        }
      }
      setParsing(false)
    }
    reader.onerror = () => {
      setParsing(false)
      setParseResult({
        success: false,
        error: 'Failed to read file from disk.',
        records: [],
        rawRecords: [],
        ingestionItems: [],
        validationErrors: [],
        missingRequired: ['File read error'],
      })
    }
    reader.readAsText(file)
  }

  // Remap column override interactively
  const handleColumnMapChange = (fieldKey, colName) => {
    if (!parseResult || !parseResult.rawRecords) return
    const nextOverrides = { ...manualColumnMap, [fieldKey]: colName }
    setManualColumnMap(nextOverrides)
    const updated = analyticsService.validateAndNormalizeDataset(
      parseResult.rawRecords,
      parseResult.detectedColumns,
      {
        sourceType: parseResult.sourceType,
        fileName: uploadFile?.name || '',
        columnOverrides: nextOverrides,
      }
    )
    setParseResult(updated)
  }

  // Confirm Import -> Persist validated events to MongoDB Atlas via backend API
  const handleConfirmImport = async () => {
    if (!parseResult || !parseResult.success || !parseResult.ingestionItems?.length) {
      addToast('Cannot import dataset with validation errors', 'warning')
      return
    }
    if (!currentWorkspace?.id) {
      setImportError('No active workspace selected. Select or create a workspace first.')
      return
    }

    setImporting(true)
    setImportError(null)
    setImportSummary(null)
    setImportProgress({ current: 0, total: Math.ceil(parseResult.ingestionItems.length / 500) })

    try {
      const summary = await analyticsService.uploadDataset({
        workspaceId: currentWorkspace.id,
        items: parseResult.ingestionItems,
        fileName: uploadFile?.name || 'analytics-events.json',
        sourceType: parseResult.sourceType || 'json',
        detectedColumns: parseResult.detectedColumns || [],
        mappedColumns: manualColumnMap,
        onProgress: (current, total) => setImportProgress({ current, total }),
      })

      setImportSummary(summary)
      setRefreshTick((t) => t + 1)
      addToast(
        `Atlas import complete: ${summary.acceptedRows} accepted, ${summary.duplicateRows} duplicates, ${summary.rejectedRows} rejected`,
        summary.rejectedRows > 0 ? 'warning' : 'success'
      )
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to upload analytics dataset to MongoDB Atlas.'
      setImportError(typeof msg === 'string' ? msg : JSON.stringify(msg))
      addToast('Analytics import failed', 'error')
    } finally {
      setImporting(false)
    }
  }

  const trendItems = trends?.items || []
  const totalEvents = overview?.totalEvents ?? 0
  const coverageState = overview?.coverage?.state || 'no_data'
  const activeRangeLabel = overview?.dateRange
    ? `${overview.dateRange.startDate} to ${overview.dateRange.endDate}`
    : timeRange.toUpperCase()

  const formatMetricValue = (val, suffix = '') => {
    if (val === null || val === undefined) return 'Unavailable'
    return `${val.toLocaleString()}${suffix}`
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Product Analytics Studio</h2>
            <Badge variant={coverageState === 'observed' ? 'success' : coverageState === 'partial' ? 'warning' : 'default'}>
              {coverageState === 'observed'
                ? 'Atlas Telemetry Active'
                : coverageState === 'partial'
                  ? 'Partial Telemetry Coverage'
                  : 'No Telemetry Data'}
            </Badge>
            {refreshing && <span className="text-xs text-brand-500 font-medium">Refreshing...</span>}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            {currentWorkspace?.name
              ? `Workspace: ${currentWorkspace.name} • Window: ${activeRangeLabel}`
              : 'Select a workspace to inspect product analytics'}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Time Range Selector */}
          <div className="flex items-center bg-white dark:bg-navy-900 border border-slate-200 dark:border-slate-800 rounded-xl p-1 shadow-sm">
            {[
              { id: '7d', label: '7 Days' },
              { id: '30d', label: '30 Days' },
              { id: '90d', label: '90 Days' },
              { id: 'all', label: 'All Time' },
              { id: 'custom', label: 'Custom' },
            ].map((range) => (
              <button
                key={range.id}
                onClick={() => handleSelectTimeRange(range.id)}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                  timeRange === range.id
                    ? 'bg-brand-600 text-white shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                {range.label}
              </button>
            ))}
          </div>

          <Button
            variant="secondary"
            size="sm"
            icon={RefreshCw}
            disabled={loading || refreshing || !currentWorkspace?.id}
            onClick={handleRetry}
          >
            Refresh
          </Button>

          {/* Upload Button */}
          <Button
            variant="primary"
            size="sm"
            icon={Upload}
            onClick={() => setShowUploadModal(true)}
          >
            Import Telemetry (CSV/JSON)
          </Button>
        </div>
      </div>

      {/* Custom Date Range Form */}
      {timeRange === 'custom' && (
        <form
          onSubmit={handleApplyCustomRange}
          className="flex flex-wrap items-end gap-3 p-3 rounded-xl bg-white dark:bg-navy-900 border border-slate-200 dark:border-slate-800"
        >
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-slate-500 font-medium">Start Date</span>
            <input
              type="date"
              aria-label="Start Date"
              value={customStartDate}
              onChange={(e) => setCustomStartDate(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-navy-950 text-xs"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-slate-500 font-medium">End Date</span>
            <input
              type="date"
              aria-label="End Date"
              value={customEndDate}
              onChange={(e) => setCustomEndDate(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-navy-950 text-xs"
            />
          </label>
          <Button type="submit" variant="primary" size="sm" icon={Calendar}>
            Apply Range
          </Button>
          {dateRangeError && <span className="text-xs text-rose-500 font-medium">{dateRangeError}</span>}
        </form>
      )}

      {/* Workspace / Loading / Error Guards */}
      {!currentWorkspace?.id ? (
        <EmptyState
          title="No workspace selected"
          description="Select or create a workspace to view MongoDB Atlas product analytics."
        />
      ) : loading ? (
        <LoadingState message="Loading workspace analytics from MongoDB Atlas..." />
      ) : error ? (
        <ErrorState
          title={isAuthError ? 'Authentication Required' : 'Analytics Unavailable'}
          error={error}
          onRetry={isAuthError ? undefined : handleRetry}
        />
      ) : (
        <>
          {/* 4 Core Real KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-4" hover>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Active Users</span>
                <div className="w-8 h-8 rounded-xl bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center">
                  <Users className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-2">
                <span className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
                  {totalEvents === 0 ? '0' : formatMetricValue(overview?.activeUsers)}
                </span>
              </div>
              <p className="text-[10px] text-slate-400 mt-1">
                {totalEvents === 0
                  ? 'No events in selected window'
                  : overview?.activeUsers !== null && overview?.activeUsers !== undefined
                    ? `100% actorId coverage (${overview?.coverage?.eventsWithActorId ?? 0} events)`
                    : `Partial actorId coverage (${overview?.coverage?.eventsWithActorId ?? 0}/${totalEvents})`}
              </p>
            </Card>

            <Card className="p-4" hover>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Total Sessions</span>
                <div className="w-8 h-8 rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400 flex items-center justify-center">
                  <Activity className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-2">
                <span className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
                  {totalEvents === 0 ? '0' : formatMetricValue(overview?.sessions)}
                </span>
              </div>
              <p className="text-[10px] text-slate-400 mt-1">
                {totalEvents === 0
                  ? 'No sessions recorded'
                  : overview?.sessions !== null && overview?.sessions !== undefined
                    ? `100% sessionId coverage (${overview?.coverage?.eventsWithSessionId ?? 0} events)`
                    : `Partial sessionId coverage (${overview?.coverage?.eventsWithSessionId ?? 0}/${totalEvents})`}
              </p>
            </Card>

            <Card className="p-4" hover>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Telemetry Events</span>
                <div className="w-8 h-8 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center">
                  <BarChart3 className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-2">
                <span className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
                  {totalEvents.toLocaleString()}
                </span>
              </div>
              <p className="text-[10px] text-slate-400 mt-1">
                Across {overview?.observedDays ?? 0} observed day(s)
              </p>
            </Card>

            <Card className="p-4" hover>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Avg Event Duration</span>
                <div className="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                  <Clock className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-2">
                <span className="text-2xl font-black text-slate-900 dark:text-white tracking-tight">
                  {overview?.avgEventDurationSeconds !== null && overview?.avgEventDurationSeconds !== undefined
                    ? `${Math.round(overview.avgEventDurationSeconds)}s`
                    : 'Unavailable'}
                </span>
              </div>
              <p className="text-[10px] text-slate-400 mt-1">
                {overview?.lastEventAt
                  ? `Last event: ${new Date(overview.lastEventAt).toISOString().split('T')[0]}`
                  : 'No duration telemetry recorded'}
              </p>
            </Card>
          </div>

          {/* Usage Trends Chart + Coverage Summary */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2 p-5">
              <div className="flex items-center justify-between pb-3 mb-2 border-b border-slate-100 dark:border-slate-800">
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">Product Usage & Activity Trends</h3>
                  <p className="text-xs text-slate-400">
                    Measured daily event volume and active users ({activeRangeLabel})
                  </p>
                </div>
                <Badge variant="brand">{timeRange.toUpperCase()}</Badge>
              </div>

              <div className="h-72 w-full pt-4">
                {trendItems.length === 0 ? (
                  <EmptyState
                    title="No usage events in this window"
                    description="Import CSV or JSON telemetry events or widen your date range filter."
                  />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={trendItems} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="eventGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
                        </linearGradient>
                        <linearGradient id="userGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0.0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#0f172a',
                          borderRadius: '0.75rem',
                          border: '1px solid #334155',
                          fontSize: '11px',
                          color: '#f8fafc',
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                      <Area
                        type="monotone"
                        dataKey="events"
                        name="Telemetry Events"
                        stroke="#6366f1"
                        strokeWidth={2}
                        connectNulls={false}
                        fillOpacity={1}
                        fill="url(#eventGradient)"
                      />
                      <Area
                        type="monotone"
                        dataKey="activeUsers"
                        name="Active Users"
                        stroke="#0ea5e9"
                        strokeWidth={2}
                        connectNulls={false}
                        fillOpacity={1}
                        fill="url(#userGradient)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Card>

            {/* Telemetry Coverage & Provenance Card */}
            <Card className="p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100 dark:border-slate-800">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">Atlas Telemetry Coverage</h3>
                    <p className="text-xs text-slate-400">Verified backend rollup provenance</p>
                  </div>
                  <Activity className="w-4 h-4 text-brand-500" />
                </div>

                <div className="space-y-3 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Coverage State</span>
                    <span className="font-semibold text-slate-900 dark:text-white capitalize">{coverageState.replace('_', ' ')}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Observed Days</span>
                    <span className="font-mono font-semibold">{overview?.observedDays ?? 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Events with Actor ID</span>
                    <span className="font-mono font-semibold">{overview?.coverage?.eventsWithActorId ?? 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Events with Session ID</span>
                    <span className="font-mono font-semibold">{overview?.coverage?.eventsWithSessionId ?? 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Date Window Capped</span>
                    <span className="font-mono font-semibold">{overview?.dateRange?.capped ? 'Yes (365d max)' : 'No'}</span>
                  </div>
                </div>
              </div>

              <div className="p-3 mt-4 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200/60 dark:border-slate-800/60 text-[11px] text-slate-500">
                All KPIs and trends reflect verified MongoDB Atlas event rollups for {activeRangeLabel}.
              </div>
            </Card>
          </div>

          {/* Feature Analytics & Comparison Section */}
          <Card className="p-5">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-4 border-b border-slate-100 dark:border-slate-800 mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Layers className="w-4 h-4 text-brand-500" />
                  Feature-Level Analytics & Comparisons
                </h3>
                <p className="text-xs text-slate-400">
                  Measured feature usage, adoption rate (unique feature users / eligible active users), and period-over-period trends
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {[
                  { id: 'most_used', label: 'Most Used' },
                  { id: 'least_used', label: 'Least Used' },
                  { id: 'adoption', label: 'Highest Adoption' },
                  { id: 'increasing', label: `Increasing (${increasingCount})` },
                  { id: 'declining', label: `Declining (${decliningCount})` },
                ].map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setFeatureSort(opt.id)}
                    className={`px-2.5 py-1 text-[11px] font-semibold rounded-lg border transition-colors cursor-pointer ${
                      featureSort === opt.id
                        ? 'bg-brand-600 text-white border-brand-600'
                        : 'bg-white dark:bg-navy-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {featureItems.length > 0 && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] text-slate-400 block">Most-Used Feature</span>
                  <span className="text-xs font-bold text-slate-900 dark:text-white truncate block mt-0.5">
                    {mostUsedFeature?.name || 'Unavailable'}
                  </span>
                  <span className="text-[11px] font-mono text-brand-600 dark:text-brand-400">
                    {mostUsedFeature ? `${mostUsedFeature.eventCount.toLocaleString()} events` : ''}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] text-slate-400 block">Least-Used Feature</span>
                  <span className="text-xs font-bold text-slate-900 dark:text-white truncate block mt-0.5">
                    {leastUsedFeature?.name || 'Unavailable'}
                  </span>
                  <span className="text-[11px] font-mono text-slate-500">
                    {leastUsedFeature ? `${leastUsedFeature.eventCount.toLocaleString()} events` : ''}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] text-slate-400 block">Increasing vs Prev Window</span>
                  <span className="text-lg font-black text-emerald-600 font-mono mt-0.5 block">
                    {increasingCount}
                  </span>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] text-slate-400 block">Declining vs Prev Window</span>
                  <span className="text-lg font-black text-rose-500 font-mono mt-0.5 block">
                    {decliningCount}
                  </span>
                </div>
              </div>
            )}

            {sortedFeatures.length === 0 ? (
              <EmptyState
                title="No feature telemetry in this view"
                description={
                  featureItems.length === 0
                    ? 'No feature-tagged events were recorded in this workspace and date range.'
                    : 'No features match the selected trend filter.'
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-800 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                      <th className="py-2.5 px-3">Feature Name</th>
                      <th className="py-2.5 px-3">Events</th>
                      <th className="py-2.5 px-3">Unique Users</th>
                      <th className="py-2.5 px-3">Adoption Rate</th>
                      <th className="py-2.5 px-3">Trend vs Prev</th>
                      <th className="py-2.5 px-3">Avg Duration</th>
                      <th className="py-2.5 px-3 text-right">History</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {sortedFeatures.map((feat) => (
                      <tr
                        key={feat.name}
                        onClick={() => handleSelectFeature(feat)}
                        className="hover:bg-slate-50 dark:hover:bg-navy-950/50 cursor-pointer transition-colors group"
                      >
                        <td className="py-3 px-3 font-semibold text-slate-900 dark:text-white">{feat.name}</td>
                        <td className="py-3 px-3 font-mono text-slate-600 dark:text-slate-300">
                          {feat.eventCount.toLocaleString()}
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-600 dark:text-slate-300">
                          {feat.uniqueUsers !== null && feat.uniqueUsers !== undefined
                            ? feat.uniqueUsers.toLocaleString()
                            : 'Unavailable'}
                        </td>
                        <td className="py-3 px-3">
                          {feat.adoptionPercent !== null && feat.adoptionPercent !== undefined ? (
                            <div className="flex items-center gap-2">
                              <span className="font-bold font-mono w-12">{feat.adoptionPercent}%</span>
                              <div className="w-20 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                                <div
                                  className="h-full rounded-full bg-brand-500"
                                  style={{ width: `${Math.min(100, feat.adoptionPercent)}%` }}
                                />
                              </div>
                            </div>
                          ) : (
                            <span className="text-slate-400">Unavailable</span>
                          )}
                        </td>
                        <td className="py-3 px-3 font-mono">
                          {feat.trendDeltaPercent !== null && feat.trendDeltaPercent !== undefined ? (
                            <span
                              className={`inline-flex items-center gap-0.5 font-semibold ${
                                feat.trendDeltaPercent >= 0 ? 'text-emerald-600' : 'text-rose-500'
                              }`}
                            >
                              {feat.trendDeltaPercent >= 0 ? (
                                <ArrowUpRight className="w-3 h-3" />
                              ) : (
                                <ArrowDownRight className="w-3 h-3" />
                              )}
                              {feat.trendDeltaPercent > 0 ? `+${feat.trendDeltaPercent}%` : `${feat.trendDeltaPercent}%`}
                            </span>
                          ) : (
                            <span className="text-slate-400">Unavailable</span>
                          )}
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-500">
                          {feat.avgEventDurationSeconds !== null && feat.avgEventDurationSeconds !== undefined
                            ? `${Math.round(feat.avgEventDurationSeconds)}s`
                            : 'Unavailable'}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <span className="text-brand-600 dark:text-brand-400 inline-flex items-center gap-1 font-semibold">
                            Inspect <ChevronRight className="w-3.5 h-3.5" />
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* User Funnel Analytics Section */}
          <Card className="p-5">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-4 border-b border-slate-100 dark:border-slate-800 mb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">Ordered User Conversion Funnel</h3>
                <p className="text-xs text-slate-400">
                  Evaluates ordered unique-user progression across explicit event stages in Atlas
                </p>
              </div>
              <form onSubmit={handleEvaluateFunnel} className="flex flex-wrap items-center gap-2">
                <input
                  type="text"
                  aria-label="Funnel Stages"
                  placeholder="e.g. view, click, complete"
                  value={funnelStepsInput}
                  onChange={(e) => setFunnelStepsInput(e.target.value)}
                  className="px-2.5 py-1.5 w-64 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-navy-950 text-xs"
                />
                <Button type="submit" variant="primary" size="sm" disabled={funnelLoading}>
                  {funnelLoading ? 'Evaluating...' : 'Evaluate Funnel'}
                </Button>
              </form>
            </div>

            {funnelData?.availableEvents?.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 mb-4 text-[11px]">
                <span className="text-slate-400 mr-1">Observed events:</span>
                {funnelData.availableEvents.slice(0, 8).map((evName) => (
                  <button
                    key={evName}
                    type="button"
                    onClick={() =>
                      setFunnelStepsInput((prev) =>
                        prev ? `${prev}, ${evName}` : evName
                      )
                    }
                    className="px-2 py-0.5 rounded-full bg-slate-100 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-600 dark:text-slate-300 hover:border-brand-500 cursor-pointer"
                  >
                    + {evName}
                  </button>
                ))}
              </div>
            )}

            {funnelData?.available && funnelData?.steps?.length > 0 ? (
              <div className="space-y-3">
                {funnelData.steps.map((st) => (
                  <div key={st.order} className="space-y-1">
                    <div className="flex items-center justify-between text-xs font-semibold">
                      <span className="text-slate-800 dark:text-slate-200">
                        {st.order}. {st.step}
                      </span>
                      <span className="text-slate-500 font-mono text-[11px]">
                        {st.users.toLocaleString()} users • {st.conversionRate}% overall ({st.stepConversionRate}% step)
                      </span>
                    </div>
                    <div className="w-full h-2.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-brand-600 to-sky-500"
                        style={{ width: `${Math.min(100, st.conversionRate)}%` }}
                      />
                    </div>
                    {st.order > 1 && (
                      <div className="flex justify-end text-[10px] font-semibold text-rose-500">
                        Drop-off: {st.dropOffCount.toLocaleString()} users ({st.dropOffRate}%)
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="Funnel Metrics Unavailable"
                description={
                  funnelData?.reason ||
                  'Define at least 2 ordered event stages above to evaluate conversion and drop-off from Atlas telemetry.'
                }
              />
            )}
          </Card>

          {/* Individual Feature Usage History Modal */}
          {selectedFeature && (
            <Modal
              isOpen={Boolean(selectedFeature)}
              onClose={() => setSelectedFeature(null)}
              title={`Feature Telemetry: ${selectedFeature.name}`}
              subtitle={`Measured usage history (${activeRangeLabel})`}
              maxWidth="max-w-3xl"
            >
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Total Events</span>
                    <span className="text-xl font-black text-slate-900 dark:text-white font-mono">
                      {selectedFeature.eventCount.toLocaleString()}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Unique Users</span>
                    <span className="text-xl font-black text-slate-900 dark:text-white font-mono">
                      {selectedFeature.uniqueUsers !== null && selectedFeature.uniqueUsers !== undefined
                        ? selectedFeature.uniqueUsers.toLocaleString()
                        : 'Unavailable'}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950/60 border border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400 block">Adoption Rate</span>
                    <span className="text-xl font-black text-brand-600 dark:text-brand-400 font-mono">
                      {selectedFeature.adoptionPercent !== null && selectedFeature.adoptionPercent !== undefined
                        ? `${selectedFeature.adoptionPercent}%`
                        : 'Unavailable'}
                    </span>
                  </div>
                </div>

                <div className="h-56 w-full p-2 rounded-xl bg-slate-50/50 dark:bg-navy-950/30 border border-slate-200 dark:border-slate-800">
                  {featureHistoryLoading ? (
                    <LoadingState message="Loading feature history from MongoDB Atlas..." />
                  ) : featureHistoryError ? (
                    <ErrorState error={featureHistoryError} onRetry={() => handleSelectFeature(selectedFeature)} />
                  ) : featureHistory.length === 0 ? (
                    <EmptyState title="No feature history" description="No daily events found in this date range." />
                  ) : (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={featureHistory} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
                        <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} />
                        <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} />
                        <Tooltip />
                        <Area
                          type="monotone"
                          dataKey="events"
                          name="Feature Events"
                          stroke="#6366f1"
                          fill="#6366f1"
                          fillOpacity={0.2}
                          connectNulls={false}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  )}
                </div>

                <div className="flex justify-end pt-2 border-t border-slate-100 dark:border-slate-800">
                  <Button variant="secondary" size="sm" onClick={() => setSelectedFeature(null)}>
                    Close Drill-Down
                  </Button>
                </div>
              </div>
            </Modal>
          )}
        </>
      )}

      {/* CSV / JSON Upload & Column Mapping Modal */}
      <Modal
        isOpen={showUploadModal}
        onClose={() => {
          setShowUploadModal(false)
          setUploadFile(null)
          setParseResult(null)
        }}
        title="Import Product Analytics Telemetry"
        subtitle="Upload CSV or JSON telemetry event logs with column validation and mapping"
        maxWidth="max-w-2xl"
      >
        <div className="space-y-4">
          {/* Dropzone */}
          <div className="p-6 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-2xl text-center hover:border-brand-500 transition-colors bg-slate-50/50 dark:bg-navy-950/30">
            <input
              type="file"
              accept=".csv,.json,text/csv,application/json"
              id="analytics-file-input"
              onChange={handleFileChange}
              className="hidden"
            />
            <label htmlFor="analytics-file-input" className="cursor-pointer block">
              <div className="w-12 h-12 rounded-2xl bg-brand-500/10 text-brand-600 dark:text-brand-400 flex items-center justify-center mx-auto mb-2">
                <Upload className="w-6 h-6" />
              </div>
              <p className="text-xs font-bold text-slate-800 dark:text-slate-200">
                Click to browse or drag and drop telemetry file
              </p>
              <p className="text-[11px] text-slate-400 mt-1">Supports standard CSV or JSON event logs</p>
            </label>
          </div>

          {/* Parsing Spinner */}
          {parsing && <LoadingState message="Analyzing file structure and validating columns..." />}

              {/* Parse Result Summary */}
          {parseResult && (
            <div className="space-y-3">
              {parseResult.success ? (
                <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                  <span>
                    Validation Ready ({parseResult.sourceType?.toUpperCase()}):{' '}
                    <strong>{parseResult.validCount ?? parseResult.records.length}</strong> valid,{' '}
                    <strong>{parseResult.invalidCount ?? 0}</strong> invalid,{' '}
                    <strong>{parseResult.duplicateInFileCount ?? 0}</strong> duplicate IDs across{' '}
                    <strong>{parseResult.totalCount ?? parseResult.records.length}</strong> rows.
                  </span>
                </div>
              ) : (
                <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
                  <span>
                    {parseResult.error ||
                      (parseResult.missingRequired?.length
                        ? `Missing required mappings: ${parseResult.missingRequired.join(', ')}`
                        : 'No valid rows found in dataset.')}
                  </span>
                </div>
              )}

              {/* Interactive Column Mapping */}
              {parseResult.detectedColumns?.length > 0 && (
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-xs">
                  <span className="font-bold text-slate-700 dark:text-slate-300 block mb-2">
                    Column Mapping ({parseResult.detectedColumns.length} columns detected)
                  </span>
                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    {[
                      { key: 'timestamp', label: 'Timestamp *' },
                      { key: 'eventName', label: 'Event Name *' },
                      { key: 'eventType', label: 'Event Type *' },
                      { key: 'userId', label: 'User / Actor ID' },
                      { key: 'featureName', label: 'Feature Name' },
                      { key: 'sessionId', label: 'Session ID' },
                      { key: 'eventId', label: 'Event ID (Dedup)' },
                      { key: 'durationSeconds', label: 'Duration (sec)' },
                    ].map(({ key, label }) => (
                      <label key={key} className="flex flex-col gap-1">
                        <span className="text-slate-500">{label}</span>
                        <select
                          value={manualColumnMap[key] || ''}
                          onChange={(e) => handleColumnMapChange(key, e.target.value)}
                          className="px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-navy-900 text-slate-800 dark:text-slate-200 font-mono text-[11px]"
                        >
                          <option value="">-- Unmapped --</option>
                          {parseResult.detectedColumns.map((col) => (
                            <option key={col} value={col}>
                              {col}
                            </option>
                          ))}
                        </select>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Invalid Row Report */}
              {parseResult.validationErrors?.length > 0 && (
                <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs">
                  <span className="font-bold text-amber-800 dark:text-amber-300 block mb-1">
                    Validation Warnings ({parseResult.validationErrors.length} invalid rows will be skipped)
                  </span>
                  <ul className="space-y-1 max-h-28 overflow-y-auto text-[11px] text-amber-700 dark:text-amber-300 font-mono">
                    {parseResult.validationErrors.slice(0, 10).map((err, i) => (
                      <li key={i}>
                        Row {err.rowNumber}: {err.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Sample Data Preview (First 3 Valid Rows) */}
              {parseResult.records.length > 0 && (
                <div>
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                    Data Preview (First 3 Valid Records):
                  </span>
                  <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                    <table className="w-full text-left text-[11px]">
                      <thead className="bg-slate-100 dark:bg-navy-950 text-slate-500">
                        <tr>
                          <th className="p-2">User ID</th>
                          <th className="p-2">Timestamp</th>
                          <th className="p-2">Feature</th>
                          <th className="p-2">Event</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                        {parseResult.records.slice(0, 3).map((r, i) => (
                          <tr key={i}>
                            <td className="p-2 font-mono text-slate-700 dark:text-slate-300">{r.userId || '—'}</td>
                            <td className="p-2 text-slate-500">{r.date}</td>
                            <td className="p-2 text-slate-700 dark:text-slate-300 font-semibold">{r.featureName || '—'}</td>
                            <td className="p-2 text-slate-500">{r.eventName || r.eventType}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Upload Progress */}
          {importing && (
            <LoadingState
              message={`Persisting to MongoDB Atlas (batch ${importProgress.current} of ${importProgress.total})...`}
            />
          )}

          {/* Import Error */}
          {importError && (
            <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300">
              {importError}
            </div>
          )}

          {/* Backend Atlas Import Result */}
          {importSummary && (
            <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 space-y-1">
              <div className="font-bold">MongoDB Atlas Import Summary ({importSummary.status})</div>
              <div className="grid grid-cols-4 gap-2 text-[11px] pt-1">
                <div>Total: <strong>{importSummary.totalRows}</strong></div>
                <div>Accepted: <strong>{importSummary.acceptedRows}</strong></div>
                <div>Duplicates: <strong>{importSummary.duplicateRows}</strong></div>
                <div>Rejected: <strong>{importSummary.rejectedRows}</strong></div>
              </div>
            </div>
          )}

          {/* Modal Actions */}
          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
            <Button
              variant="secondary"
              size="sm"
              disabled={importing}
              onClick={() => {
                setShowUploadModal(false)
                setUploadFile(null)
                setParseResult(null)
                setImportSummary(null)
                setImportError(null)
              }}
            >
              {importSummary ? 'Close' : 'Cancel'}
            </Button>
            {!importSummary && (
              <Button
                variant="primary"
                size="sm"
                disabled={importing || !parseResult || !parseResult.success}
                onClick={handleConfirmImport}
              >
                {importing ? 'Importing...' : 'Confirm & Import to Atlas'}
              </Button>
            )}
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default AnalyticsPage
