import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { useAuthStore } from '@/stores/authStore'
import Layout from '@/components/Layout'
import LoginPage from '@/pages/login/LoginPage'
import RegisterPage from '@/pages/register/RegisterPage'
import OverviewPage from '@/pages/overview/OverviewPage'
import OntologyListPage from '@/pages/ontologies/list/OntologyListPage'
import EntityDetailPage from '@/pages/ontologies/detail/entity/EntityDetailPage'
import LogicDetailPage from '@/pages/ontologies/detail/logic/LogicDetailPage'
import ActionDetailPage from '@/pages/ontologies/detail/action/ActionDetailPage'
import PipelinesLayout from '@/pages/pipelines/PipelinesLayout'
import PipelineListPage from '@/pages/pipelines/PipelineListPage'

const OntologyDetailPage = lazy(() => import('@/pages/ontologies/detail/OntologyDetailPage'))
const PipelineBuilderPage = lazy(() => import('@/pages/pipelines/builder/PipelineBuilderPage'))
const StructuredDataPage = lazy(() => import('@/pages/data-management/structured/StructuredDataPage'))
const AnalyticsHubPage = lazy(() => import('@/pages/analytics/AnalyticsHubPage'))
const OntologyCreateWizard = lazy(() => import('@/pages/ontologies/new/OntologyCreateWizard'))
const ModelsPage = lazy(() => import('@/pages/models/ModelsPage'))
const SettingsPage = lazy(() => import('@/pages/settings/SettingsPage'))
const ConnectionsTab = lazy(() => import('@/pages/pipelines/connections/ConnectionsTab'))
const DatasetsTab = lazy(() => import('@/pages/pipelines/datasets/DatasetsTab'))
const TransformsTab = lazy(() => import('@/pages/pipelines/transforms/TransformsTab'))
const CuratedTab = lazy(() => import('@/pages/pipelines/curated/CuratedTab'))
const DataManagementPage = lazy(() => import('@/pages/data-management/DataManagementPage'))

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } }
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore(s => s.token)
  return token ? <Layout>{children}</Layout> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Suspense fallback={<div className="p-8 text-sm text-gray-500">Loading…</div>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<ProtectedRoute><OverviewPage /></ProtectedRoute>} />
          <Route path="/analytics" element={<ProtectedRoute><AnalyticsHubPage /></ProtectedRoute>} />

          {/* ── 数据管理 ── */}
          <Route path="/data" element={<ProtectedRoute><DataManagementPage /></ProtectedRoute>} />
          <Route path="/data/structured" element={<ProtectedRoute><StructuredDataPage /></ProtectedRoute>} />
          <Route path="/data/pipelines" element={<ProtectedRoute><PipelinesLayout /></ProtectedRoute>}>
            <Route index element={<PipelineListPage />} />
            <Route path="connections" element={<ConnectionsTab />} />
            <Route path="datasets" element={<DatasetsTab />} />
            <Route path="transforms" element={<TransformsTab />} />
            <Route path="curated" element={<CuratedTab />} />
          </Route>
          <Route path="/data/pipelines/:pipelineId" element={<ProtectedRoute><PipelineBuilderPage /></ProtectedRoute>} />

          {/* Legacy redirect — keep old /pipelines URLs working */}
          <Route path="/pipelines" element={<Navigate to="/data/pipelines" replace />} />
          <Route path="/pipelines/*" element={<Navigate to="/data/pipelines" replace />} />

          <Route path="/ontologies" element={<ProtectedRoute><OntologyListPage /></ProtectedRoute>} />
          <Route path="/ontologies/new" element={<ProtectedRoute><OntologyCreateWizard /></ProtectedRoute>} />
          <Route path="/ontologies/:id" element={<ProtectedRoute><OntologyDetailPage /></ProtectedRoute>} />
          <Route path="/ontologies/:id/entities/:eid" element={<ProtectedRoute><EntityDetailPage /></ProtectedRoute>} />
          <Route path="/ontologies/:id/logic/:lid" element={<ProtectedRoute><LogicDetailPage /></ProtectedRoute>} />
          <Route path="/ontologies/:id/actions/:aid" element={<ProtectedRoute><ActionDetailPage /></ProtectedRoute>} />
          <Route path="/models" element={<ProtectedRoute><ModelsPage /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
