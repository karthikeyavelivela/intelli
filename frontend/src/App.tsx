import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/layouts/AppShell";
import { PublicLayout } from "@/layouts/PublicLayout";
import { RequireAuth, RequireCap } from "@/layouts/guards";
import { Spinner } from "@/components/ui/misc";

import Landing from "@/pages/public/Landing";
import About from "@/pages/public/About";
import { Login, Register, ForgotPassword, ResetPassword } from "@/pages/public/Auth";
import { NotFound, Forbidden } from "@/pages/public/ErrorPages";
import Dashboard from "@/pages/app/Dashboard";

// heavier app pages are code-split
const Metrics = lazy(() => import("@/pages/app/Metrics"));
const MetricDetail = lazy(() => import("@/pages/app/MetricDetail"));
const Datasets = lazy(() => import("@/pages/app/Datasets"));
const DatasetDetail = lazy(() => import("@/pages/app/DatasetDetail"));
const Connections = lazy(() => import("@/pages/app/Connections"));
const Generator = lazy(() => import("@/pages/app/Generator"));
const Conflicts = lazy(() => import("@/pages/app/Conflicts"));
const ConflictDetail = lazy(() => import("@/pages/app/ConflictDetail"));
const FormulaLab = lazy(() => import("@/pages/app/FormulaLab"));
const Versions = lazy(() => import("@/pages/app/Versions"));
const AskTara = lazy(() => import("@/pages/app/AskTara"));
const Dashboards = lazy(() => import("@/pages/app/Dashboards"));
const DashboardBuilder = lazy(() => import("@/pages/app/DashboardBuilder"));
const Evaluation = lazy(() => import("@/pages/app/Evaluation"));
const Reports = lazy(() => import("@/pages/app/Reports"));
const Profile = lazy(() => import("@/pages/app/Profile"));
const AdminUsers = lazy(() => import("@/pages/app/AdminUsers"));
const AuditLog = lazy(() => import("@/pages/app/AuditLog"));
const Settings = lazy(() => import("@/pages/app/Settings"));
const Notifications = lazy(() => import("@/pages/app/Notifications"));

const G = ({ cap, children }: { cap: string; children: React.ReactNode }) => <RequireCap cap={cap}>{children}</RequireCap>;

export default function App() {
  return (
    <Suspense fallback={<div className="flex min-h-[50vh] items-center justify-center"><Spinner className="h-6 w-6" /></div>}>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route index element={<Landing />} />
          <Route path="about" element={<About />} />
        </Route>
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="forgot-password" element={<ForgotPassword />} />
        <Route path="reset-password" element={<ResetPassword />} />
        <Route path="403" element={<Forbidden />} />

        <Route path="app" element={<RequireAuth />}>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="metrics" element={<Metrics />} />
            <Route path="metrics/:id" element={<MetricDetail />} />
            <Route path="datasets" element={<Datasets />} />
            <Route path="datasets/:id" element={<DatasetDetail />} />
            <Route path="connections" element={<G cap="dataset.write"><Connections /></G>} />
            <Route path="generator" element={<G cap="ai.generate"><Generator /></G>} />
            <Route path="conflicts" element={<G cap="conflict.view"><Conflicts /></G>} />
            <Route path="conflicts/:id" element={<G cap="conflict.view"><ConflictDetail /></G>} />
            <Route path="lab" element={<G cap="formula.run"><FormulaLab /></G>} />
            <Route path="versions" element={<Versions />} />
            <Route path="versions/:id" element={<Versions />} />
            <Route path="ask" element={<G cap="chat.ask"><AskTara /></G>} />
            <Route path="dashboards" element={<Dashboards />} />
            <Route path="dashboards/:id" element={<DashboardBuilder />} />
            <Route path="evaluation" element={<G cap="evaluation.view"><Evaluation /></G>} />
            <Route path="reports" element={<G cap="report.export"><Reports /></G>} />
            <Route path="profile" element={<Profile />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="admin/users" element={<G cap="user.manage"><AdminUsers /></G>} />
            <Route path="admin/audit" element={<G cap="audit.view"><AuditLog /></G>} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<NotFound inApp />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
