import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute, PublicOnlyRoute } from "./components/RouteGuards";
import ComingSoon from "./components/ComingSoon";
import DashboardLayout from "./layouts/DashboardLayout";
import { PENDING_ITEMS } from "./config/navigation";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Overview from "./pages/Overview";
import MyResume from "./pages/MyResume";
import ResumeIntelligence from "./pages/ResumeIntelligence";
import JobSearch from "./pages/JobSearch";
import JobMatches from "./pages/JobMatches";
import ScamDetection from "./pages/ScamDetection";
import Applications from "./pages/Applications";
import Analytics from "./pages/Analytics";
import RecruiterHub from "./pages/RecruiterHub";
import Settings from "./pages/Settings";
import CareerCoach from "./pages/CareerCoach";
import InterviewLab from "./pages/InterviewLab";
import SalaryIntelligence from "./pages/SalaryIntelligence";
import Recovery from "./pages/Recovery";
import CompanyResearch from "./pages/CompanyResearch";
import ApplicationAssistant from "./pages/ApplicationAssistant";

export default function App() {
  return (
    <Routes>
      <Route element={<PublicOnlyRoute />}>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<DashboardLayout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/job-search" element={<JobSearch />} />
          <Route path="/job-matches" element={<JobMatches />} />
          <Route path="/resume" element={<MyResume />} />
          <Route path="/resume-intelligence" element={<ResumeIntelligence />} />
          <Route path="/scam-detection" element={<ScamDetection />} />
          <Route path="/applications" element={<Applications />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/recruiter-hub" element={<RecruiterHub />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/career-coach" element={<CareerCoach />} />
          <Route path="/interview-lab" element={<InterviewLab />} />
          <Route path="/salary" element={<SalaryIntelligence />} />
          <Route path="/recovery" element={<Recovery />} />
          <Route path="/company-research" element={<CompanyResearch />} />
          <Route path="/application-assistant" element={<ApplicationAssistant />} />
          {PENDING_ITEMS.map((item) => (
            <Route key={item.path} path={item.path} element={<ComingSoon item={item} />} />
          ))}
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/overview" replace />} />
    </Routes>
  );
}
