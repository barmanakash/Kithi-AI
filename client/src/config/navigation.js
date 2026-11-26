import SpaceDashboardOutlined from "@mui/icons-material/SpaceDashboardOutlined";
import TravelExploreOutlined from "@mui/icons-material/TravelExploreOutlined";
import WorkOutlineOutlined from "@mui/icons-material/WorkOutlineOutlined";
import DescriptionOutlined from "@mui/icons-material/DescriptionOutlined";
import PsychologyOutlined from "@mui/icons-material/PsychologyOutlined";
import SchoolOutlined from "@mui/icons-material/SchoolOutlined";
import RecordVoiceOverOutlined from "@mui/icons-material/RecordVoiceOverOutlined";
import ForumOutlined from "@mui/icons-material/ForumOutlined";
import AssignmentOutlined from "@mui/icons-material/AssignmentOutlined";
import InsightsOutlined from "@mui/icons-material/InsightsOutlined";
import PaymentsOutlined from "@mui/icons-material/PaymentsOutlined";
import GppMaybeOutlined from "@mui/icons-material/GppMaybeOutlined";
import BuildOutlined from "@mui/icons-material/BuildOutlined";
import BusinessOutlined from "@mui/icons-material/BusinessOutlined";
import SettingsOutlined from "@mui/icons-material/SettingsOutlined";

/**
 * `ready: true`  -> page is wired to backend APIs that exist today.
 * `ready: false` -> page shows an honest "backend module pending" screen (no fake data).
 */
export const NAV_ITEMS = [
  { path: "/overview", label: "Overview", icon: SpaceDashboardOutlined, ready: true },
  { path: "/job-search", label: "AI Job Search", icon: TravelExploreOutlined, ready: true },
  { path: "/job-matches", label: "Job Matches", icon: WorkOutlineOutlined, ready: true },
  { path: "/company-research", label: "Company Research", icon: BusinessOutlined, ready: true },
  { path: "/resume", label: "My Resume", icon: DescriptionOutlined, ready: true },
  { path: "/resume-intelligence", label: "Resume Intelligence", icon: PsychologyOutlined, ready: true },
  {
    path: "/career-coach",
    label: "AI Career Coach",
    icon: SchoolOutlined,
    ready: true,
  },
  {
    path: "/interview-lab",
    label: "Interview Lab",
    icon: RecordVoiceOverOutlined,
    ready: true,
  },
  { path: "/recruiter-hub", label: "Recruiter Hub", icon: ForumOutlined, ready: true },
  { path: "/applications", label: "Applications", icon: AssignmentOutlined, ready: true },
  { path: "/analytics", label: "Career Analytics", icon: InsightsOutlined, ready: true },
  { path: "/recovery", label: "Search Recovery", icon: BuildOutlined, ready: true },
  {
    path: "/salary",
    label: "Salary Intelligence",
    icon: PaymentsOutlined,
    ready: true,
  },
  { path: "/scam-detection", label: "Scam Detection", icon: GppMaybeOutlined, ready: true },
  { path: "/settings", label: "Settings", icon: SettingsOutlined, ready: true },
];

export const PENDING_ITEMS = NAV_ITEMS.filter((item) => !item.ready);
