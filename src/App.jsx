import React from 'react'
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from './context/ThemeContext'
import { AuthProvider } from './context/AuthContext'
import { WorkspaceProvider } from './context/WorkspaceContext'
import { AppProvider } from './context/AppContext'
import { AppShell } from './components/layout/AppShell'
import { ProtectedRoute } from './components/layout/ProtectedRoute'
import { ErrorBoundary } from './components/common/ErrorBoundary'

// Auth Pages
import SignInPage from './pages/auth/SignInPage'
import SignUpPage from './pages/auth/SignUpPage'
import ForgotPasswordPage from './pages/auth/ForgotPasswordPage'

// Main Application Pages
import DashboardPage from './pages/DashboardPage'
import AnalyticsPage from './pages/AnalyticsPage'
import FeedbackPage from './pages/FeedbackPage'
import AggregationPage from './pages/AggregationPage'
import InsightsPage from './pages/InsightsPage'
import PersonasPage from './pages/PersonasPage'
import PrioritizationPage from './pages/PrioritizationPage'
import SimulatorPage from './pages/SimulatorPage'
import PRDGeneratorPage from './pages/PRDGeneratorPage'
import RoadmapPage from './pages/RoadmapPage'
import ExperimentsPage from './pages/ExperimentsPage'
import ReleaseReadinessPage from './pages/ReleaseReadinessPage'
import CopilotPage from './pages/CopilotPage'
import CompetitorIntelPage from './pages/CompetitorIntelPage'
import CustomerJourneyPage from './pages/CustomerJourneyPage'
import ReportsPage from './pages/ReportsPage'
import ActivityHistoryPage from './pages/ActivityHistoryPage'
import SettingsPage from './pages/SettingsPage'
import NotFoundPage from './pages/NotFoundPage'

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <WorkspaceProvider>
          <AppProvider>
            <HashRouter>
            <Routes>
              {/* Public Authentication Routes */}
              <Route path="/signin" element={<SignInPage />} />
              <Route path="/signup" element={<SignUpPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />

              {/* Protected Workspace Routes inside AppShell */}
              <Route
                element={
                  <ProtectedRoute>
                    <AppShell />
                  </ProtectedRoute>
                }
              >
                <Route path="/" element={<DashboardPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/product-analytics" element={<Navigate to="/analytics" replace />} />
                <Route path="/feedback" element={<FeedbackPage />} />
                <Route path="/aggregation" element={<AggregationPage />} />
                <Route path="/feature-aggregation" element={<Navigate to="/aggregation" replace />} />
                <Route path="/insights" element={<Navigate to="/feedback?tab=insights" replace />} />
                <Route path="/personas" element={<PersonasPage />} />
                <Route path="/prioritization" element={<PrioritizationPage />} />
                <Route path="/simulator" element={<Navigate to="/prioritization?tab=simulator" replace />} />

                {/* PRD Generator (support both /prd-generator and /prds) */}
                <Route path="/prd-generator" element={<PRDGeneratorPage />} />
                <Route path="/prds" element={<Navigate to="/prd-generator" replace />} />

                <Route path="/roadmap" element={<RoadmapPage />} />
                <Route path="/experiments" element={<ExperimentsPage />} />
                <Route path="/release-readiness" element={<Navigate to="/roadmap?tab=readiness" replace />} />
                <Route path="/copilot" element={<CopilotPage />} />
                <Route path="/competitors" element={<CompetitorIntelPage />} />

                {/* Customer Journey (support both /journey and /customer-journey) */}
                <Route path="/journey" element={<CustomerJourneyPage />} />
                <Route path="/customer-journey" element={<Navigate to="/journey" replace />} />

                <Route path="/reports" element={<Navigate to="/?report=true" replace />} />

                {/* Activity History & Audit (support both /history and /activity-history) */}
                <Route path="/history" element={<ActivityHistoryPage />} />
                <Route path="/activity-history" element={<Navigate to="/history" replace />} />

                <Route path="/settings" element={<SettingsPage />} />

                {/* 404 Catch-all */}
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </HashRouter>
        </AppProvider>
      </WorkspaceProvider>
    </AuthProvider>
    </ThemeProvider>
    </ErrorBoundary>
  )
}
