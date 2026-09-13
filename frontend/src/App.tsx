import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "@/components/Layout";
import { UploadPage } from "@/pages/UploadPage";
import { ProcessingPage } from "@/pages/ProcessingPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { TransactionsPage } from "@/pages/TransactionsPage";
import { CashFlowPage } from "@/pages/CashFlowPage";
import { RiskPage } from "@/pages/RiskPage";
import { RecommendationsPage } from "@/pages/RecommendationsPage";
import { AnomaliesPage } from "@/pages/AnomaliesPage";

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/accounts/:accountId/processing" element={<ProcessingPage />} />
        <Route path="/accounts/:accountId" element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="transactions" element={<TransactionsPage />} />
          <Route path="cash-flow" element={<CashFlowPage />} />
          <Route path="risk" element={<RiskPage />} />
          <Route path="recommendations" element={<RecommendationsPage />} />
          <Route path="anomalies" element={<AnomaliesPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
