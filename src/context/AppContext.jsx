import React, { createContext, useContext, useState, useEffect } from 'react'
import {
  initializeAppState,
  safeSet,
  STORAGE_KEYS,
  resetAllData,
} from '../services/storageService'
import { calculatePriorityScore } from '../data/scoringFormulas'
import { createHistoryRecord, appendHistory } from '../services/historyService'
import { feedbackService } from '../services/api/feedbackService'
import { isBackendConfigured } from '../services/api/apiClient'

const AppContext = createContext(null)

export function AppProvider({ children }) {
  // Initialize all persisted states
  const [initial] = useState(() => initializeAppState())

  const [feedback, setFeedback] = useState(initial.feedback)
  const [features, setFeatures] = useState(initial.features)
  const [personas, setPersonas] = useState(initial.personas)
  const [prds, setPrds] = useState(initial.prds)
  const [roadmap, setRoadmap] = useState(initial.roadmap)
  const [experiments, setExperiments] = useState(initial.experiments)
  const [releases, setReleases] = useState(initial.releases)
  const [competitors, setCompetitors] = useState(initial.competitors)
  const [journeys, setJourneys] = useState(initial.journeys)
  const [scenarios, setScenarios] = useState(initial.scenarios)
  const [notifications, setNotifications] = useState(initial.notifications)
  const [history, setHistory] = useState(initial.history)
  const [introSeen, setIntroSeenState] = useState(initial.introSeen)
  const [tourSeen, setTourSeenState] = useState(initial.tourSeen)
  const [savedViews, setSavedViews] = useState(initial.savedViews)
  const [dashboardLayout, setDashboardLayout] = useState(initial.dashboardLayout)

  // Ephemeral UI states
  const [toasts, setToasts] = useState([])
  const [recruiterDemoActive, setRecruiterDemoActive] = useState(false)
  const [recruiterDemoStep, setRecruiterDemoStep] = useState(0)
  const [presentationModeActive, setPresentationModeActive] = useState(false)

  // Sync to localStorage
  useEffect(() => { safeSet(STORAGE_KEYS.FEEDBACK, feedback) }, [feedback])
  useEffect(() => { safeSet(STORAGE_KEYS.FEATURES, features) }, [features])
  useEffect(() => { safeSet(STORAGE_KEYS.PERSONAS, personas) }, [personas])
  useEffect(() => { safeSet(STORAGE_KEYS.PRDS, prds) }, [prds])
  useEffect(() => { safeSet(STORAGE_KEYS.ROADMAP, roadmap) }, [roadmap])
  useEffect(() => { safeSet(STORAGE_KEYS.EXPERIMENTS, experiments) }, [experiments])
  useEffect(() => { safeSet(STORAGE_KEYS.RELEASES, releases) }, [releases])
  useEffect(() => { safeSet(STORAGE_KEYS.COMPETITORS, competitors) }, [competitors])
  useEffect(() => { safeSet(STORAGE_KEYS.JOURNEYS, journeys) }, [journeys])
  useEffect(() => { safeSet(STORAGE_KEYS.SCENARIOS, scenarios) }, [scenarios])
  useEffect(() => { safeSet(STORAGE_KEYS.NOTIFICATIONS, notifications) }, [notifications])
  useEffect(() => { safeSet(STORAGE_KEYS.HISTORY, history) }, [history])
  useEffect(() => { safeSet(STORAGE_KEYS.INTRO_SEEN, introSeen) }, [introSeen])
  useEffect(() => { safeSet(STORAGE_KEYS.TOUR_SEEN, tourSeen) }, [tourSeen])
  useEffect(() => { safeSet(STORAGE_KEYS.SAVED_VIEWS, savedViews) }, [savedViews])
  useEffect(() => { safeSet(STORAGE_KEYS.DASHBOARD_LAYOUT, dashboardLayout) }, [dashboardLayout])

  // Toast notifier
  const addToast = (message, type = 'info', undoAction = null) => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`
    setToasts(prev => [...prev, { id, message, type, undoAction }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4500)
  }

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  // Activity logger helper
  const recordActivity = (entityType, entityId, action, description, previousState, newState) => {
    const record = createHistoryRecord({
      entityType,
      entityId,
      action,
      description,
      previousState,
      newState,
    })
    setHistory(prev => appendHistory(prev, record))
  }

  // --- FEEDBACK ACTIONS ---
  const addFeedback = async (item) => {
    let newItem = {
      id: item.id || `fb-${Date.now()}`,
      title: item.title,
      description: item.description,
      customer: item.customer || 'Anonymous User',
      company: item.company || 'Enterprise Account',
      category: item.category || 'Feature Requests',
      sentiment: item.sentiment || 'Neutral',
      priority: item.priority || 'Medium',
      tags: item.tags || ['feedback'],
      date: item.date || new Date().toISOString().split('T')[0],
      linkedFeatureId: item.linkedFeatureId || null,
    }

    if (isBackendConfigured()) {
      try {
        const created = await feedbackService.createFeedback(item)
        if (created?.id) {
          newItem.id = String(created.id)
          if (created.category) newItem.category = created.category
          if (created.sentiment) newItem.sentiment = created.sentiment
        }
      } catch (err) {
        console.warn('Backend feedback creation fallback to local state:', err)
      }
    }

    setFeedback(prev => [newItem, ...prev])
    recordActivity('feedback', newItem.id, 'created', `Created feedback: "${newItem.title}"`, null, newItem)
    addToast(`Feedback "${newItem.title}" added successfully`, 'success')
    return newItem
  }

  const updateFeedback = (id, updates) => {
    const current = feedback.find(f => f.id === id)
    if (!current) return
    const updated = { ...current, ...updates }
    setFeedback(prev => prev.map(f => (f.id === id ? updated : f)))
    recordActivity('feedback', id, 'updated', `Updated feedback: "${updated.title}"`, current, updated)
    addToast('Feedback record updated', 'success')
  }

  const deleteFeedback = (id) => {
    const current = feedback.find(f => f.id === id)
    if (!current) return
    setFeedback(prev => prev.filter(f => f.id !== id))
    
    const undo = () => {
      setFeedback(prev => [current, ...prev])
      recordActivity('feedback', id, 'restored', `Restored deleted feedback: "${current.title}"`, null, current)
      addToast(`Restored feedback "${current.title}"`, 'info')
    }

    recordActivity('feedback', id, 'deleted', `Deleted feedback: "${current.title}"`, current, null)
    addToast(`Deleted feedback "${current.title}"`, 'warning', undo)
  }

  const bulkUpdateFeedback = (ids, updates) => {
    setFeedback(prev => prev.map(f => (ids.includes(f.id) ? { ...f, ...updates } : f)))
    addToast(`Updated ${ids.length} feedback items`, 'success')
  }

  const bulkDeleteFeedback = (ids) => {
    const deletedItems = feedback.filter(f => ids.includes(f.id))
    setFeedback(prev => prev.filter(f => !ids.includes(f.id)))

    const undo = () => {
      setFeedback(prev => [...deletedItems, ...prev])
      addToast(`Restored ${deletedItems.length} feedback records`, 'info')
    }

    addToast(`Deleted ${ids.length} feedback records`, 'warning', undo)
  }

  const importFeedbackBatch = (items) => {
    setFeedback(prev => [...items, ...prev])
    addToast(`Imported ${items.length} feedback records from CSV`, 'success')
    addNotification({
      title: 'CSV Import Completed',
      message: `Successfully processed and categorized ${items.length} new feedback records.`,
      type: 'success',
      link: '/feedback'
    })
  }

  // --- FEATURE ACTIONS ---
  const addFeature = (item) => {
    const score = calculatePriorityScore(item)
    const newFeature = {
      id: item.id || `feat-${Date.now()}`,
      name: item.name,
      description: item.description,
      customerImpact: Number(item.customerImpact) || 5,
      urgency: Number(item.urgency) || 5,
      demand: Number(item.demand) || 5,
      businessValue: Number(item.businessValue) || 5,
      score,
      status: item.status || 'In Planning',
      owner: item.owner || 'Alex Rivera',
      targetRelease: item.targetRelease || 'v2.4.0',
      relatedFeedbackIds: item.relatedFeedbackIds || [],
      comments: item.comments || [],
    }
    setFeatures(prev => [newFeature, ...prev])
    recordActivity('feature', newFeature.id, 'created', `Created feature: "${newFeature.name}" (Score: ${score})`, null, newFeature)
    addToast(`Feature "${newFeature.name}" created (Priority: ${score})`, 'success')
    return newFeature
  }

  const updateFeature = (id, updates) => {
    const current = features.find(f => f.id === id)
    if (!current) return
    const merged = { ...current, ...updates }
    const score = calculatePriorityScore(merged)
    const updated = { ...merged, score }

    setFeatures(prev => prev.map(f => (f.id === id ? updated : f)))
    recordActivity('feature', id, 'updated', `Updated feature "${updated.name}" (New Score: ${score})`, current, updated)
    addToast(`Feature "${updated.name}" updated (Score: ${score})`, 'success')
  }

  const deleteFeature = (id) => {
    const current = features.find(f => f.id === id)
    if (!current) return
    setFeatures(prev => prev.filter(f => f.id !== id))

    const undo = () => {
      setFeatures(prev => [current, ...prev])
      addToast(`Restored feature "${current.name}"`, 'info')
    }

    recordActivity('feature', id, 'deleted', `Deleted feature: "${current.name}"`, current, null)
    addToast(`Deleted feature "${current.name}"`, 'warning', undo)
  }

  // --- PERSONA ACTIONS ---
  const addPersona = (item) => {
    const newPersona = {
      id: item.id || `per-${Date.now()}`,
      name: item.name,
      role: item.role,
      companyType: item.companyType || 'Technology Client',
      avatar: item.avatar || item.name.slice(0, 2).toUpperCase(),
      description: item.description,
      goals: item.goals || [],
      frustrations: item.frustrations || [],
      needs: item.needs || [],
      featurePreferences: item.featurePreferences || [],
      sentimentSummary: item.sentimentSummary || 'Neutral',
      relatedFeedbackCount: item.relatedFeedbackCount || 0,
      isFavorite: false,
    }
    setPersonas(prev => [newPersona, ...prev])
    recordActivity('persona', newPersona.id, 'created', `Created persona: "${newPersona.name}"`, null, newPersona)
    addToast(`Created persona "${newPersona.name}"`, 'success')
  }

  const updatePersona = (id, updates) => {
    setPersonas(prev => prev.map(p => (p.id === id ? { ...p, ...updates } : p)))
    addToast('Persona updated', 'success')
  }

  const deletePersona = (id) => {
    const current = personas.find(p => p.id === id)
    setPersonas(prev => prev.filter(p => p.id !== id))
    addToast(`Deleted persona "${current?.name}"`, 'warning')
  }

  const regeneratePersonas = () => {
    // Simulated clustering based on actual categories
    addToast('Simulated AI clustering feedback corpus into personas...', 'info')
  }

  // --- PRD ACTIONS ---
  const createPRD = (item) => {
    const newPRD = {
      id: item.id || `prd-${Date.now()}`,
      title: item.title,
      featureId: item.featureId || null,
      version: item.version || '1.0.0',
      status: item.status || 'Draft',
      author: item.author || 'Alex Rivera',
      createdAt: new Date().toISOString().split('T')[0],
      updatedAt: new Date().toISOString().split('T')[0],
      sections: item.sections,
    }
    setPrds(prev => [newPRD, ...prev])
    recordActivity('prd', newPRD.id, 'created', `Generated PRD: "${newPRD.title}"`, null, newPRD)
    addToast(`PRD "${newPRD.title}" generated`, 'success')
    return newPRD
  }

  const updatePRD = (id, updates) => {
    const current = prds.find(p => p.id === id)
    if (!current) return
    const updated = {
      ...current,
      ...updates,
      updatedAt: new Date().toISOString().split('T')[0],
    }
    setPrds(prev => prev.map(p => (p.id === id ? updated : p)))
    recordActivity('prd', id, 'updated', `Updated PRD: "${updated.title}"`, current, updated)
    addToast(`PRD "${updated.title}" saved`, 'success')
  }

  const duplicatePRD = (id) => {
    const current = prds.find(p => p.id === id)
    if (!current) return
    const dup = {
      ...current,
      id: `prd-${Date.now()}`,
      title: `${current.title} (Copy)`,
      version: '1.0.0-copy',
      createdAt: new Date().toISOString().split('T')[0],
      updatedAt: new Date().toISOString().split('T')[0],
    }
    setPrds(prev => [dup, ...prev])
    addToast(`Duplicated PRD "${dup.title}"`, 'success')
  }

  const deletePRD = (id) => {
    const current = prds.find(p => p.id === id)
    setPrds(prev => prev.filter(p => p.id !== id))
    addToast(`Deleted PRD "${current?.title}"`, 'warning')
  }

  // --- ROADMAP ACTIONS ---
  const addRoadmapItem = (item) => {
    const newItem = {
      id: item.id || `rd-${Date.now()}`,
      title: item.title,
      description: item.description,
      featureId: item.featureId || null,
      status: item.status || 'Planned',
      priority: item.priority || 'Medium',
      owner: item.owner || 'Alex Rivera',
      startDate: item.startDate || new Date().toISOString().split('T')[0],
      targetDate: item.targetDate || '2026-12-31',
      milestone: item.milestone || 'Q4 Milestone',
      progress: Number(item.progress) || 0,
      dependencies: item.dependencies || [],
      notes: item.notes || '',
    }
    setRoadmap(prev => [...prev, newItem])
    recordActivity('roadmap', newItem.id, 'created', `Created roadmap item: "${newItem.title}"`, null, newItem)
    addToast(`Added roadmap item "${newItem.title}"`, 'success')
  }

  const updateRoadmapItem = (id, updates) => {
    setRoadmap(prev => prev.map(r => (r.id === id ? { ...r, ...updates } : r)))
    addToast('Roadmap item updated', 'success')
  }

  const deleteRoadmapItem = (id) => {
    setRoadmap(prev => prev.filter(r => r.id !== id))
    addToast('Roadmap item removed', 'warning')
  }

  // --- EXPERIMENT ACTIONS ---
  const addExperiment = (item) => {
    const newExp = {
      id: item.id || `exp-${Date.now()}`,
      name: item.name,
      problem: item.problem,
      hypothesis: item.hypothesis,
      targetAudience: item.targetAudience,
      proposedChange: item.proposedChange,
      successMetric: item.successMetric,
      baseline: Number(item.baseline) || 0,
      target: Number(item.target) || 0,
      observedValue: Number(item.observedValue) || Number(item.baseline) || 0,
      startDate: item.startDate || new Date().toISOString().split('T')[0],
      endDate: item.endDate || '2026-11-30',
      linkedFeatureId: item.linkedFeatureId || null,
      owner: item.owner || 'Marcus Chen',
      status: item.status || 'Running',
      conclusion: item.conclusion || 'Continue',
      notes: item.notes || '',
    }
    setExperiments(prev => [newExp, ...prev])
    recordActivity('experiment', newExp.id, 'created', `Created experiment: "${newExp.name}"`, null, newExp)
    addToast(`Created experiment "${newExp.name}"`, 'success')
  }

  const updateExperiment = (id, updates) => {
    setExperiments(prev => prev.map(e => (e.id === id ? { ...e, ...updates } : e)))
    addToast('Experiment updated', 'success')
  }

  const deleteExperiment = (id) => {
    setExperiments(prev => prev.filter(e => e.id !== id))
    addToast('Experiment deleted', 'warning')
  }

  // --- RELEASE READINESS ACTIONS ---
  const addRelease = (item) => {
    const newRel = {
      id: item.id || `rel-${Date.now()}`,
      name: item.name,
      version: item.version,
      description: item.description,
      plannedDate: item.plannedDate || '2026-12-15',
      owner: item.owner || 'Alex Rivera',
      status: item.status || 'In Progress',
      includedFeatureIds: item.includedFeatureIds || [],
      roadmapItemIds: item.roadmapItemIds || [],
      checklist: item.checklist || [
        { id: `chk-${Date.now()}-1`, title: 'Requirements completed & signed off by product lead', completed: false, required: true },
        { id: `chk-${Date.now()}-2`, title: 'Acceptance criteria verified across all included user stories', completed: false, required: true },
        { id: `chk-${Date.now()}-3`, title: 'High-priority customer issues & bugs reviewed (zero urgent blockers)', completed: false, required: true },
        { id: `chk-${Date.now()}-4`, title: 'Dependencies resolved across infrastructure & integrations', completed: false, required: true },
        { id: `chk-${Date.now()}-5`, title: 'Automated Vitest suite & RTL integration tests passing', completed: false, required: true },
        { id: `chk-${Date.now()}-6`, title: 'Documentation prepared & PRDs committed to repository', completed: false, required: false },
        { id: `chk-${Date.now()}-7`, title: 'Release notes written & formatted for customer portal', completed: false, required: false },
        { id: `chk-${Date.now()}-8`, title: 'Final executive approval recorded & verified', completed: false, required: true }
      ],
      releaseNotes: item.releaseNotes || 'Initial release draft notes.'
    }
    setReleases(prev => [newRel, ...prev])
    addToast(`Created release ${newRel.version}`, 'success')
  }

  const updateRelease = (id, updates) => {
    setReleases(prev => prev.map(r => (r.id === id ? { ...r, ...updates } : r)))
    addToast('Release updated', 'success')
  }

  const toggleChecklistItem = (releaseId, checkId) => {
    setReleases(prev => prev.map(r => {
      if (r.id !== releaseId) return r
      const updatedChecklist = r.checklist.map(c => {
        if (c.id !== checkId) return c
        return { ...c, completed: !c.completed }
      })
      return { ...r, checklist: updatedChecklist }
    }))
  }

  const deleteRelease = (id) => {
    setReleases(prev => prev.filter(r => r.id !== id))
    addToast('Release removed', 'warning')
  }

  // --- COMPETITOR INTEL ACTIONS ---
  const addCompetitor = (item) => {
    const newComp = {
      id: item.id || `comp-${Date.now()}`,
      name: item.name,
      productDescription: item.productDescription,
      website: item.website || 'https://example.com',
      targetAudience: item.targetAudience || 'Enterprise PM teams',
      keyFeatures: item.keyFeatures || [],
      strengths: item.strengths || [],
      weaknesses: item.weaknesses || [],
      differentiators: item.differentiators || [],
      researchNotes: item.researchNotes || '',
      lastReviewed: new Date().toISOString().split('T')[0],
    }
    setCompetitors(prev => [newComp, ...prev])
    addToast(`Added competitor "${newComp.name}"`, 'success')
  }

  const updateCompetitor = (id, updates) => {
    setCompetitors(prev => prev.map(c => (c.id === id ? { ...c, ...updates } : c)))
    addToast('Competitor research updated', 'success')
  }

  const deleteCompetitor = (id) => {
    setCompetitors(prev => prev.filter(c => c.id !== id))
    addToast('Competitor record deleted', 'warning')
  }

  // --- CUSTOMER JOURNEY ACTIONS ---
  const updateJourneyStage = (stageId, updates) => {
    setJourneys(prev => prev.map(s => (s.id === stageId ? { ...s, ...updates } : s)))
    addToast('Journey stage updated', 'success')
  }

  const addTouchpoint = (stageId, tp) => {
    const newTp = {
      id: `tp-${Date.now()}`,
      name: tp.name || 'New Touchpoint',
      sentiment: tp.sentiment || 'Positive',
      painPoints: tp.painPoints || 'None identified',
      opportunity: tp.opportunity || '',
    }
    setJourneys(prev => prev.map(s => {
      if (s.id !== stageId) return s
      return { ...s, touchpoints: [...(s.touchpoints || []), newTp] }
    }))
    addToast('Touchpoint added', 'success')
  }

  const removeTouchpoint = (stageId, tpId) => {
    setJourneys(prev => prev.map(s => {
      if (s.id !== stageId) return s
      return { ...s, touchpoints: (s.touchpoints || []).filter(t => t.id !== tpId) }
    }))
  }

  // --- WHAT-IF SCENARIO ACTIONS ---
  const createScenario = (item) => {
    const newScen = {
      id: item.id || `scen-${Date.now()}`,
      name: item.name || 'Custom What-If Scenario',
      description: item.description || '',
      createdAt: new Date().toISOString().split('T')[0],
      adjustedFeatures: item.adjustedFeatures || [],
    }
    setScenarios(prev => [newScen, ...prev])
    addToast(`Scenario "${newScen.name}" created`, 'success')
    return newScen
  }

  const updateScenario = (id, updates) => {
    setScenarios(prev => prev.map(s => (s.id === id ? { ...s, ...updates } : s)))
    addToast('Scenario updated', 'success')
  }

  const deleteScenario = (id) => {
    setScenarios(prev => prev.filter(s => s.id !== id))
    addToast('Scenario deleted', 'warning')
  }

  // --- NOTIFICATIONS ---
  const addNotification = (notif) => {
    const item = {
      id: `notif-${Date.now()}`,
      title: notif.title,
      message: notif.message,
      type: notif.type || 'info',
      timestamp: 'Just now',
      read: false,
      link: notif.link || null,
    }
    setNotifications(prev => [item, ...prev])
  }

  const markNotificationAsRead = (id) => {
    setNotifications(prev => prev.map(n => (n.id === id ? { ...n, read: true } : n)))
  }

  const markAllNotificationsAsRead = () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
  }

  const clearAllNotifications = () => {
    setNotifications([])
  }

  // --- REVERSIBLE UNDO ---
  const undoAction = (historyEventId) => {
    const event = history.find(h => h.id === historyEventId)
    if (!event || !event.canUndo) {
      addToast('This action cannot be undone.', 'warning')
      return
    }

    if (event.entityType === 'feedback') {
      if (event.action === 'created') {
        setFeedback(prev => prev.filter(f => f.id !== event.entityId))
      } else if (event.action === 'deleted' && event.previousState) {
        setFeedback(prev => [event.previousState, ...prev])
      } else if (event.action === 'updated' && event.previousState) {
        setFeedback(prev => prev.map(f => (f.id === event.entityId ? event.previousState : f)))
      }
    } else if (event.entityType === 'feature') {
      if (event.action === 'created') {
        setFeatures(prev => prev.filter(f => f.id !== event.entityId))
      } else if (event.action === 'deleted' && event.previousState) {
        setFeatures(prev => [event.previousState, ...prev])
      } else if (event.action === 'updated' && event.previousState) {
        setFeatures(prev => prev.map(f => (f.id === event.entityId ? event.previousState : f)))
      }
    }

    // Mark event as undone
    setHistory(prev => prev.map(h => (h.id === historyEventId ? { ...h, canUndo: false } : h)))
    addToast(`Successfully undid: ${event.description}`, 'success')
  }

  // --- RECRUITER DEMO & TOUR ---
  const startRecruiterDemo = (step = 0) => {
    setRecruiterDemoStep(step)
    setRecruiterDemoActive(true)
  }

  const nextDemoStep = () => {
    setRecruiterDemoStep(prev => prev + 1)
  }

  const prevDemoStep = () => {
    setRecruiterDemoStep(prev => Math.max(0, prev - 1))
  }

  const exitRecruiterDemo = () => {
    setRecruiterDemoActive(false)
  }

  // --- RESTORE / BACKUP ---
  const resetToDemo = () => {
    const fresh = resetAllData()
    setFeedback(fresh.feedback)
    setFeatures(fresh.features)
    setPersonas(fresh.personas)
    setPrds(fresh.prds)
    setRoadmap(fresh.roadmap)
    setExperiments(fresh.experiments)
    setReleases(fresh.releases)
    setCompetitors(fresh.competitors)
    setJourneys(fresh.journeys)
    setScenarios(fresh.scenarios)
    setNotifications(fresh.notifications)
    setHistory([])
    addToast('Workspace restored to pristine seed data', 'success')
  }

  const importBackup = (data) => {
    if (data.feedback) setFeedback(data.feedback)
    if (data.features) setFeatures(data.features)
    if (data.personas) setPersonas(data.personas)
    if (data.prds) setPrds(data.prds)
    if (data.roadmap) setRoadmap(data.roadmap)
    if (data.experiments) setExperiments(data.experiments)
    if (data.releases) setReleases(data.releases)
    if (data.competitors) setCompetitors(data.competitors)
    if (data.journeys) setJourneys(data.journeys)
    if (data.scenarios) setScenarios(data.scenarios)
    addToast('Backup data restored successfully', 'success')
  }

  return (
    <AppContext.Provider
      value={{
        // State entities
        feedback,
        features,
        personas,
        prds,
        roadmap,
        experiments,
        releases,
        competitors,
        journeys,
        scenarios,
        notifications,
        history,
        introSeen,
        setIntroSeen: setIntroSeenState,
        tourSeen,
        setTourSeen: setTourSeenState,
        savedViews,
        setSavedViews,
        dashboardLayout,
        setDashboardLayout,
        toasts,
        addToast,
        removeToast,

        // Actions
        addFeedback,
        updateFeedback,
        deleteFeedback,
        bulkUpdateFeedback,
        bulkDeleteFeedback,
        importFeedbackBatch,

        addFeature,
        updateFeature,
        deleteFeature,

        addPersona,
        updatePersona,
        deletePersona,
        regeneratePersonas,

        createPRD,
        updatePRD,
        duplicatePRD,
        deletePRD,

        addRoadmapItem,
        updateRoadmapItem,
        deleteRoadmapItem,

        addExperiment,
        updateExperiment,
        deleteExperiment,

        addRelease,
        updateRelease,
        toggleChecklistItem,
        deleteRelease,

        addCompetitor,
        updateCompetitor,
        deleteCompetitor,

        updateJourneyStage,
        addTouchpoint,
        removeTouchpoint,

        createScenario,
        updateScenario,
        deleteScenario,

        addNotification,
        markNotificationAsRead,
        markAllNotificationsAsRead,
        clearAllNotifications,

        undoAction,

        // Demo & Presentation
        recruiterDemoActive,
        recruiterDemoStep,
        startRecruiterDemo,
        nextDemoStep,
        prevDemoStep,
        exitRecruiterDemo,

        presentationModeActive,
        setPresentationModeActive,

        resetToDemo,
        importBackup,
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) {
    throw new Error('useApp must be used within an AppProvider')
  }
  return context
}
