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
import SettingsOutlined from "@mui/icons-material/SettingsOutlined";

/**
 * `ready: true`  -> page is wired to backend APIs that exist today.
 * `ready: false` -> page shows an honest "backend module pending" screen (no fake data).
 */
export const NAV_ITEMS = [
  { path: "/overview", label: "Overview", icon: SpaceDashboardOutlined, ready: true },
  { path: "/job-search", label: "AI Job Search", icon: TravelExploreOutlined, ready: true },
  { path: "/job-matches", label: "Job Matches", icon: WorkOutlineOutlined, ready: true },
  { path: "/resume", label: "My Resume", icon: DescriptionOutlined, ready: true },
  { path: "/resume-intelligence", label: "Resume Intelligence", icon: PsychologyOutlined, ready: true },
  {
    path: "/career-coach",
    label: "AI Career Coach",
    icon: SchoolOutlined,
    ready: false,
    phase: "Phase 7",
    description: "Skill-gap analysis, career paths, learning roadmaps and portfolio project ideas.",
    needs: "Career Intelligence agent API.",
    features: ["Skill gap identification", "Learning roadmap", "Practical portfolio project suggestions"],
  },
  {
    path: "/interview-lab",
    label: "Interview Lab",
    icon: RecordVoiceOverOutlined,
    ready: false,
    phase: "Phase 7",
    description: "Technical and HR question practice, mock interviews and answer feedback.",
    needs: "Interview Preparation agent API and interview storage.",
    features: ["Generated technical and HR questions", "Mock interview sessions", "Answer evaluation and feedback"],
  },
  {
    path: "/recruiter-hub",
    label: "Recruiter Hub",
    icon: ForumOutlined,
    ready: false,
    phase: "Phase 6",
    description: "Personalized recruiter messages, referral requests and follow-ups. Nothing is sent without your approval.",
    needs: "Recruiter Outreach agent API and recruiter storage.",
    features: ["Draft recruiter messages", "Referral requests", "Follow-up reminders (approval required before sending)"],
  },
  {
    path: "/applications",
    label: "Applications",
    icon: AssignmentOutlined,
    ready: false,
    phase: "Phase 6",
    description: "Track every application across Kanban, table and timeline views.",
    needs: "Applications API (status workflow from Saved to Offer / Rejected).",
    features: ["Kanban, table and timeline views", "Resume version per application", "Follow-up dates and notes"],
  },
  {
    path: "/analytics",
    label: "Career Analytics",
    icon: InsightsOutlined,
    ready: false,
    phase: "Phase 9",
    description: "Application funnel, response rates and career progress over time.",
    needs: "Application and interview data to analyze.",
    features: ["Application funnel", "Response and interview rates", "Skill and progress tracking"],
  },
  {
    path: "/salary",
    label: "Salary Intelligence",
    icon: PaymentsOutlined,
    ready: false,
    phase: "Phase 7",
    description: "Compare offers, break down CTC, estimate in-hand pay and prepare negotiation messages.",
    needs: "Salary Intelligence agent API and offer storage.",
    features: ["CTC breakdown (fixed / variable)", "In-hand salary estimate", "Negotiation message drafts"],
  },
  { path: "/scam-detection", label: "Scam Detection", icon: GppMaybeOutlined, ready: true },
  { path: "/settings", label: "Settings", icon: SettingsOutlined, ready: true },
];

export const PENDING_ITEMS = NAV_ITEMS.filter((item) => !item.ready);
