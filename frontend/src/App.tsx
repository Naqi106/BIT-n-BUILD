import { Navigate, Route, Routes } from 'react-router-dom'
import { StoreProvider } from './lib/store'
import { Layout } from './components/Layout'
import LandingPage from './pages/LandingPage'
import DashboardPage from './pages/DashboardPage'
import AlertsPage from './pages/AlertsPage'
import ZonesPage from './pages/ZonesPage'
import CopilotPage from './pages/CopilotPage'
import BillingAuditPage from './pages/BillingAuditPage'
import LeakLocationPage from './pages/LeakLocationPage'
import ContaminationPage from './pages/ContaminationPage'
import AnalyticsPage from './pages/AnalyticsPage'
import ReportsPage from './pages/ReportsPage'
import RevenuePage from './pages/RevenuePage'
import DataUploadPage from './pages/DataUploadPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
    return (
        <StoreProvider>
            <Routes>
                <Route path="/" element={<LandingPage />} />
                <Route path="/app" element={<Layout />}>
                    <Route index element={<Navigate to="dashboard" replace />} />
                    <Route path="dashboard" element={<DashboardPage />} />
                    <Route path="alerts" element={<AlertsPage />} />
                    <Route path="zones" element={<ZonesPage />} />
                    <Route path="copilot" element={<CopilotPage />} />
                    <Route path="billing" element={<BillingAuditPage />} />
                    <Route path="leak" element={<LeakLocationPage />} />
                    <Route path="contamination" element={<ContaminationPage />} />
                    <Route path="analytics" element={<AnalyticsPage />} />
                    <Route path="reports" element={<ReportsPage />} />
                    <Route path="revenue" element={<RevenuePage />} />
                    <Route path="upload" element={<DataUploadPage />} />
                    <Route path="settings" element={<SettingsPage />} />
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </StoreProvider>
    )
}
