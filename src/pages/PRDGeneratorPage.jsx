import React, { useState, useEffect } from 'react'
import { Link, useNavigate, useSearchParams, useLocation } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import {
  FileText,
  Plus,
  Sparkles,
  Download,
  Copy,
  Printer,
  Save,
  CheckCircle2,
  Trash2,
  Edit2,
  ChevronRight,
  ExternalLink,
  RotateCcw,
  Layers,
  Link as LinkIcon,
  Brain,
  Loader2,
  Check,
  XCircle,
} from 'lucide-react'
import { Card, Badge, Button, Modal, DemoModeBanner } from '../components/common'
import { prdService } from '../services/api/prdService'
import { useWorkspace } from '../context/WorkspaceContext'

export function PRDGeneratorPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const targetFeatureId = searchParams.get('featureId') || location.state?.featureId

  const {
    prds,
    features,
    feedback,
    createPRD,
    updatePRD,
    duplicatePRD,
    deletePRD,
    addToast,
  } = useApp()
  const { currentWorkspace } = useWorkspace()

  const [activePRDId, setActivePRDId] = useState(() => {
    if (targetFeatureId) {
      const match = prds.find(p => p.featureId === targetFeatureId)
      if (match) return match.id
    }
    return prds[0]?.id || ''
  })
  const [isEditing, setIsEditing] = useState(false)
  const [showNewModal, setShowNewModal] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationError, setGenerationError] = useState(null)

  // Selection for generating from feature
  const [selectedFeatureId, setSelectedFeatureId] = useState(() => targetFeatureId || features[0]?.id || '')
  const [customTitle, setCustomTitle] = useState('')

  const activePRD = prds.find(p => p.id === activePRDId) || prds[0]

  // Draft editing state
  const [editableSections, setEditableSections] = useState(() => activePRD?.sections || {})

  // Synchronize targetFeatureId from navigation state or URL
  useEffect(() => {
    if (targetFeatureId) {
      setSelectedFeatureId(targetFeatureId)
      const existingPRD = prds.find(p => p.featureId === targetFeatureId)
      if (existingPRD) {
        setActivePRDId(existingPRD.id)
        setEditableSections(existingPRD.sections)
        setIsEditing(false)
      } else {
        const feat = features.find(f => f.id === targetFeatureId)
        if (feat) {
          setCustomTitle(`${feat.name} Specification`)
        }
        setShowNewModal(true)
      }
    }
  }, [targetFeatureId, prds, features])

  const handleSelectPRD = (id) => {
    setActivePRDId(id)
    const target = prds.find(p => p.id === id)
    if (target) {
      setEditableSections(target.sections)
      setIsEditing(false)
    }
  }

  // Auto-generate from selected feature via service
  const handleGenerateFromFeature = async () => {
    const feat = features.find(f => f.id === selectedFeatureId)
    setIsGenerating(true)
    setGenerationError(null)

    try {
      let generatedSections = null
      let docTitle = customTitle || (feat ? `${feat.name} Specification` : 'Product Requirements Document')
      let reviewStatus = 'Pending Review'

      // Attempt real AI Product Planning Agent call
      if (currentWorkspace?.id && selectedFeatureId) {
        try {
          const plan = await prdService.generateProductPlan({
            workspaceId: currentWorkspace.id,
            featureGroupId: selectedFeatureId,
            strategicContext: docTitle,
          })

          if (plan?.prd) {
            const p = plan.prd
            const formatReq = (r) =>
              typeof r === 'string'
                ? r
                : `[${r.requirement_id || 'REQ'}] (${r.origin || 'ai_recommendation'}) ${r.title}: ${r.description}${r.source_reference ? ` — Ref: "${r.source_reference}"` : ''}`

            generatedSections = {
              overview: p.executive_summary || p.overview || `Executive overview for ${docTitle}`,
              problemStatement: p.problem_statement || 'Customer workflow friction identified from raw feedback.',
              targetUsers: Array.isArray(p.target_users) ? p.target_users.join(', ') : (p.target_audience || 'Enterprise Product Teams'),
              customerPainPoints: Array.isArray(p.customer_pain_points) ? p.customer_pain_points.join('\n• ') : (p.customer_pain_points || 'Operational latency and manual steps.'),
              proposedSolution: p.proposed_solution || `Implement comprehensive ${docTitle} solution.`,
              goalsAndSuccessMetrics: (plan.success_metrics || [])
                .map(m => `• ${m.metric_name || m.name}: Target ${m.suggested_target || m.target || 'Pending PM confirmation'} (Baseline: ${m.baseline ?? 'unmeasured'})`)
                .join('\n') || (Array.isArray(p.success_metrics) ? p.success_metrics.join('\n• ') : 'Pending confirmation'),
              functionalRequirements: Array.isArray(p.functional_requirements)
                ? p.functional_requirements.map(formatReq).join('\n• ')
                : (p.functional_requirements || 'Core API & UI endpoints'),
              nonFunctionalRequirements: Array.isArray(p.non_functional_requirements) && p.non_functional_requirements.length > 0
                ? p.non_functional_requirements.map(formatReq).join('\n• ')
                : ((plan.technical_requirements || []).map(t => `[${t.category}] ${t.title}: ${t.description}`).join('\n• ') || 'To be benchmarked by engineering review'),
              userStories: (plan.user_stories || [])
                .map(us => `### ${us.story_id || us.id || 'US'}: ${us.title || ''}\n${us.description || us.story || ''}`)
                .join('\n\n') || 'As a PM, I want structured planning...',
              acceptanceCriteria: (plan.user_stories || [])
                .flatMap(us => (us.acceptance_criteria || us.given_when_then || []).map(ac =>
                  typeof ac === 'string' ? ac : `[${ac.criterion_id || 'AC'}] ${ac.description}`
                ))
                .map(ac => `• ${ac}`)
                .join('\n') || 'Given valid input, When executed, Then response is saved.',
              dependenciesAndConstraints: Array.isArray(p.dependencies) && p.dependencies.length > 0
                ? p.dependencies.join('\n• ')
                : 'FastAPI backend, MongoDB database, Groq LLM inference',
              risksAndMitigations: (plan.risk_analysis || [])
                .map(r => `• [${r.category}] ${r.description} (Mitigation: ${r.mitigation})`)
                .join('\n') || 'Mitigated via bounded token allocations and backoff.',
              releasePlan: (plan.roadmap_recommendations || [])
                .map(rp => `${rp.phase_name}: ${rp.objective}`)
                .join('\n') || `Review status: ${plan.status || 'Pending Review'}.`,
            }
            reviewStatus = plan.status || 'Pending Review'
          }
        } catch (backendErr) {
          console.warn('Backend planning agent fallback to template:', backendErr)
        }
      }

      if (!generatedSections) {
        const res = await prdService.generatePRD(feat, docTitle)
        generatedSections = res.data?.sections || {
          overview: `Specification for ${docTitle}`,
          problemStatement: 'Problem statement grounded in customer feedback.',
          targetUsers: 'Product Managers, Engineers, Designers',
          customerPainPoints: 'Customer pain points identified from feedback analysis.',
          proposedSolution: 'Automated solution with structured workflows.',
          goalsAndSuccessMetrics: 'Adoption target: 40% within 30 days (Baseline: unmeasured)',
          functionalRequirements: '1. Ingestion endpoint\n2. Real-time clustering\n3. Algorithmic ranking',
          nonFunctionalRequirements: 'Security: RBAC with workspace isolation.\nReliability: 99.9% availability.',
          userStories: 'As a PM, I want AI assistance in PRD generation so that specs are grounded in evidence.',
          acceptanceCriteria: 'Given customer feedback exists, When AI generation is triggered, Then a 13-section PRD is generated.',
          dependenciesAndConstraints: 'FastAPI, MongoDB, Groq inference',
          risksAndMitigations: 'Latency risks mitigated via async processing.',
          releasePlan: 'Target Release: v2.5.0 (Pending Review)',
        }
      }

      const newDoc = createPRD({
        title: docTitle,
        featureId: selectedFeatureId || null,
        version: '1.0.0',
        status: reviewStatus,
        sections: generatedSections,
      })

      setActivePRDId(newDoc.id)
      setEditableSections(generatedSections)
      setShowNewModal(false)
      setCustomTitle('')
      addToast('Product Requirements Document generated with AI grounding!', 'success')
    } catch (err) {
      setGenerationError(err?.message || 'Failed to generate PRD')
      addToast(err?.message || 'Failed to generate PRD', 'error')
    } finally {
      setIsGenerating(false)
    }
  }

  // Save changes to PRD
  const handleSaveSections = () => {
    if (!activePRD) return
    updatePRD(activePRD.id, { sections: editableSections })
    setIsEditing(false)
    addToast('PRD saved successfully', 'success')
  }

  // Copy section text
  const copySection = (title, text) => {
    navigator.clipboard.writeText(`### ${title}\n\n${text}`)
    addToast(`Copied section "${title}" to clipboard`, 'info')
  }

  // Copy full document
  const copyFullDocument = () => {
    if (!activePRD) return
    let full = `# ${activePRD.title}\nVersion: ${activePRD.version} | Status: ${activePRD.status}\n\n`
    Object.entries(editableSections).forEach(([k, text]) => {
      full += `## ${k.toUpperCase()}\n${text}\n\n`
    })
    navigator.clipboard.writeText(full)
    addToast('Full PRD copied to clipboard as Markdown', 'success')
  }

  // Export as Markdown file
  const exportMarkdown = () => {
    if (!activePRD) return
    let full = `# ${activePRD.title}\n\n**Version:** ${activePRD.version}\n**Status:** ${activePRD.status}\n**Last Updated:** ${activePRD.updatedAt}\n\n---\n\n`
    const sectionNames = [
      { key: 'overview', title: '1. Overview' },
      { key: 'problemStatement', title: '2. Problem Statement' },
      { key: 'targetUsers', title: '3. Target Users' },
      { key: 'customerPainPoints', title: '4. Customer Pain Points' },
      { key: 'proposedSolution', title: '5. Proposed Solution' },
      { key: 'goalsAndSuccessMetrics', title: '6. Goals and Success Metrics' },
      { key: 'functionalRequirements', title: '7. Functional Requirements' },
      { key: 'nonFunctionalRequirements', title: '8. Non-Functional Requirements' },
      { key: 'userStories', title: '9. User Stories' },
      { key: 'acceptanceCriteria', title: '10. Acceptance Criteria' },
      { key: 'dependenciesAndConstraints', title: '11. Dependencies and Constraints' },
      { key: 'risksAndMitigations', title: '12. Risks and Mitigations' },
      { key: 'releasePlan', title: '13. Release Plan' },
    ]

    sectionNames.forEach(s => {
      full += `## ${s.title}\n\n${editableSections[s.key] || 'N/A'}\n\n`
    })

    const blob = new Blob([full], { type: 'text/markdown;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `${activePRD.title.replace(/\s+/g, '_')}_PRD.md`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    addToast('Exported clean Markdown PRD file', 'success')
  }

  const sectionsConfig = [
    { key: 'overview', title: '1. Overview' },
    { key: 'problemStatement', title: '2. Problem Statement' },
    { key: 'targetUsers', title: '3. Target Users' },
    { key: 'customerPainPoints', title: '4. Customer Pain Points' },
    { key: 'proposedSolution', title: '5. Proposed Solution' },
    { key: 'goalsAndSuccessMetrics', title: '6. Goals and Success Metrics' },
    { key: 'functionalRequirements', title: '7. Functional Requirements' },
    { key: 'nonFunctionalRequirements', title: '8. Non-Functional Requirements' },
    { key: 'userStories', title: '9. User Stories' },
    { key: 'acceptanceCriteria', title: '10. Acceptance Criteria' },
    { key: 'dependenciesAndConstraints', title: '11. Dependencies and Constraints' },
    { key: 'risksAndMitigations', title: '12. Risks and Mitigations' },
    { key: 'releasePlan', title: '13. Release Plan' },
  ]

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Demo Mode Banner */}
      <DemoModeBanner
        message="PRD Studio: 13-section specifications generated from workspace context and deterministic templates in Demo Mode. Prepared for future backend LLM generation API."
      />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Product Requirements Document Studio</h2>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
              13-Section Spec
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Auto-generate comprehensive engineering PRDs directly from prioritized features and customer pain points
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="outline" size="sm" icon={Copy} onClick={copyFullDocument}>
            Copy All
          </Button>
          <Button variant="outline" size="sm" icon={Download} onClick={exportMarkdown}>
            Export .MD
          </Button>
          <Button variant="outline" size="sm" icon={Printer} onClick={() => window.print()}>
            Print View
          </Button>
          <Button variant="primary" size="sm" icon={Sparkles} onClick={() => setShowNewModal(true)}>
            AI PRD Generator
          </Button>
        </div>
      </div>

      {/* Traceability Bar */}
      {activePRD && (
        <div className="p-3 rounded-xl bg-slate-50 dark:bg-navy-950/70 border border-slate-200/80 dark:border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-bold text-slate-700 dark:text-slate-300">
              Artifact Traceability:
            </span>
            {features.find(f => f.id === activePRD.featureId) ? (
              <span className="text-slate-600 dark:text-slate-300 flex items-center gap-1">
                Linked to Feature: <strong className="text-brand-600 dark:text-brand-400">{features.find(f => f.id === activePRD.featureId)?.name}</strong>
              </span>
            ) : (
              <span className="text-slate-400 italic">Standalone PRD Document</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Link to="/prioritization">
              <button className="px-2.5 py-1 text-[11px] font-semibold rounded-lg bg-white dark:bg-navy-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:text-brand-600 flex items-center gap-1 cursor-pointer">
                <LinkIcon className="w-3 h-3 text-brand-500" />
                <span>Prioritization Matrix</span>
              </button>
            </Link>
            <Link to="/aggregation">
              <button className="px-2.5 py-1 text-[11px] font-semibold rounded-lg bg-white dark:bg-navy-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:text-brand-600 flex items-center gap-1 cursor-pointer">
                <Layers className="w-3 h-3 text-brand-500" />
                <span>Aggregated Feedback</span>
              </button>
            </Link>
          </div>
        </div>
      )}

      {/* Main Layout: PRD Sidebar & Document Viewer */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Column: Documents List */}
        <div className="space-y-3">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
            PRD Documents ({prds.length})
          </span>

          <div className="space-y-2">
            {prds.map(doc => {
              const isSelected = doc.id === activePRD?.id
              return (
                <Card
                  key={doc.id}
                  onClick={() => handleSelectPRD(doc.id)}
                  className={`p-3 cursor-pointer transition-all ${
                    isSelected
                      ? 'border-brand-500 bg-brand-50/50 dark:bg-brand-950/40 shadow-sm'
                      : 'hover:border-slate-300 dark:hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-mono text-slate-400">v{doc.version}</span>
                    <Badge variant={doc.status === 'Completed' ? 'success' : 'default'} size="xs">
                      {doc.status}
                    </Badge>
                  </div>
                  <h4 className="text-xs font-bold text-slate-900 dark:text-white line-clamp-1">{doc.title}</h4>
                  <p className="text-[10px] text-slate-400 mt-1">Updated {doc.updatedAt}</p>
                </Card>
              )
            })}
          </div>
        </div>

        {/* Right 3-Columns: Active Document Viewer & Editor */}
        <div className="lg:col-span-3 space-y-4">
          {activePRD ? (
            <Card className="p-6">
              {/* Document Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 mb-6 border-b border-slate-200 dark:border-slate-800">
                <div>
                  <h1 className="text-xl font-black text-slate-900 dark:text-white">{activePRD.title}</h1>
                  <p className="text-xs text-slate-400 mt-1">
                    Author: <strong className="text-slate-300">{activePRD.author}</strong> • Version: {activePRD.version} • Status: <span className="text-emerald-400 font-semibold">{activePRD.status}</span>
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {isEditing ? (
                    <Button variant="primary" size="sm" icon={Save} onClick={handleSaveSections}>
                      Save Revisions
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" icon={Edit2} onClick={() => setIsEditing(true)}>
                      Edit Sections
                    </Button>
                  )}
                  <button
                    onClick={() => duplicatePRD(activePRD.id)}
                    className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
                    title="Duplicate document"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => deletePRD(activePRD.id)}
                    className="p-2 text-slate-400 hover:text-rose-500 rounded-lg hover:bg-slate-800"
                    title="Delete document"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* 13 Structured Sections */}
              <div className="space-y-6">
                {sectionsConfig.map(({ key, title }) => (
                  <div key={key} className="p-4 rounded-xl bg-slate-50/60 dark:bg-navy-950/60 border border-slate-200/80 dark:border-slate-800/80">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-xs font-bold uppercase tracking-wider text-brand-600 dark:text-brand-400">
                        {title}
                      </h3>
                      <button
                        onClick={() => copySection(title, editableSections[key] || '')}
                        className="text-[10px] text-slate-400 hover:text-slate-200 flex items-center gap-1"
                      >
                        <Copy className="w-3 h-3" />
                        <span>Copy</span>
                      </button>
                    </div>

                    {isEditing ? (
                      <textarea
                        rows={3}
                        value={editableSections[key] || ''}
                        onChange={e => setEditableSections({ ...editableSections, [key]: e.target.value })}
                        className="w-full p-2.5 text-xs rounded-lg bg-white dark:bg-navy-900 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white"
                      />
                    ) : (
                      <div className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-line font-normal">
                        {editableSections[key] || 'No specification written.'}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          ) : (
            <Card className="p-12 text-center">
              <FileText className="w-12 h-12 text-slate-300 dark:text-slate-700 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">No PRD Selected</p>
              <Button size="sm" onClick={() => setShowNewModal(true)} className="mt-3">
                Generate PRD
              </Button>
            </Card>
          )}
        </div>
      </div>

      {/* Auto-Generate PRD Modal */}
      <Modal
        isOpen={showNewModal}
        onClose={() => setShowNewModal(false)}
        title="AI Product Planning Agent (PRD Studio)"
        subtitle="Transform prioritized backlog features into complete 13-section specifications with user stories and acceptance criteria"
      >
        <div className="space-y-4">
          {generationError && (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-600 dark:text-rose-400 text-xs">
              {generationError}
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Select Feature to Specify *
            </label>
            <select
              value={selectedFeatureId}
              onChange={e => {
                const val = e.target.value
                setSelectedFeatureId(val)
                const f = features.find(item => item.id === val)
                if (f) setCustomTitle(`${f.name} Specification`)
              }}
              className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
            >
              {features.map(f => (
                <option key={f.id} value={f.id}>
                  {f.name} (Priority Score: {f.score.toFixed(2)})
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">
              Custom Document Title (Optional)
            </label>
            <input
              type="text"
              value={customTitle}
              onChange={e => setCustomTitle(e.target.value)}
              placeholder="e.g. Enterprise Dark Mode Architecture PRD v2"
              className="w-full px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-navy-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white"
            />
          </div>

          <div className="p-3.5 rounded-xl bg-brand-50/60 dark:bg-brand-950/40 border border-brand-200 dark:border-brand-800 text-xs text-slate-600 dark:text-slate-300">
            <span className="font-bold text-brand-600 dark:text-brand-400 block mb-1">
              ⚡ Grounded AI Specification Architecture:
            </span>
            <p className="text-[11px] leading-relaxed">
              Synthesizes 13 sections grounded strictly in customer feedback quotes, user stories with Given/When/Then acceptance criteria, engineering technical specs, and null baseline metrics in accordance with product governance standards.
            </p>
          </div>

          <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowNewModal(false)}>Cancel</Button>
            <Button
              variant="electric"
              disabled={isGenerating}
              icon={isGenerating ? Loader2 : Sparkles}
              onClick={handleGenerateFromFeature}
            >
              {isGenerating ? 'Synthesizing with AI...' : 'Generate 13 Sections with AI'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default PRDGeneratorPage
