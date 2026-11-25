import { Link as RouterLink } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  Grid,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import FavoriteBorder from "@mui/icons-material/FavoriteBorder";
import PersonOutline from "@mui/icons-material/PersonOutline";
import DescriptionOutlined from "@mui/icons-material/DescriptionOutlined";
import MemoryOutlined from "@mui/icons-material/MemoryOutlined";
import TravelExploreOutlined from "@mui/icons-material/TravelExploreOutlined";
import WorkOutlineOutlined from "@mui/icons-material/WorkOutlineOutlined";
import SendOutlined from "@mui/icons-material/SendOutlined";
import HourglassEmpty from "@mui/icons-material/HourglassEmpty";
import EventAvailableOutlined from "@mui/icons-material/EventAvailableOutlined";
import CancelOutlined from "@mui/icons-material/CancelOutlined";
import TrendingUp from "@mui/icons-material/TrendingUp";
import RadioButtonUnchecked from "@mui/icons-material/RadioButtonUnchecked";
import CheckCircle from "@mui/icons-material/CheckCircle";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import ScoreBreakdownChart from "../components/ScoreBreakdownChart";
import useApi from "../hooks/useApi";
import { useAuth } from "../context/AuthContext";
import { aiApi, healthApi, jobsApi, matchesApi, profileApi, resumesApi } from "../services/endpoints";
import { COMPLETENESS_LABELS, formatDate } from "../utils/format";

// Metrics that still need backend modules. Shown without numbers (never faked).
const PENDING_METRICS = [
  { label: "Applications submitted", icon: SendOutlined, phase: "Phase 6" },
  { label: "Pending applications", icon: HourglassEmpty, phase: "Phase 6" },
  { label: "Interview invitations", icon: EventAvailableOutlined, phase: "Phase 6" },
  { label: "Rejections", icon: CancelOutlined, phase: "Phase 6" },
  { label: "Career development progress", icon: TrendingUp, phase: "Phase 7" },
];

const GOOD_MATCH_SCORE = 55; // "good" or better, same threshold the backend labels use

function aiState(ai, error) {
  if (error) return { value: "Unknown", color: "warning", caption: "Could not check the AI service" };
  if (!ai) return { value: "...", color: "primary", caption: "Checking Ollama" };
  if (!ai.reachable) return { value: "Offline", color: "error", caption: "Start Ollama: ollama serve" };
  if (!ai.model_available) return { value: "No model", color: "warning", caption: ai.message };
  return { value: "Ready", color: "success", caption: ai.model };
}

export default function Overview() {
  const { user } = useAuth();
  const resumes = useApi(() => resumesApi.list());
  const profile = useApi(() => profileApi.get());
  const ai = useApi(() => aiApi.status());
  const health = useApi(() => healthApi.get());
  const jobs = useApi(() => jobsApi.list({ limit: 1 }));
  const goodMatches = useApi(() => matchesApi.list({ min_score: GOOD_MATCH_SCORE, limit: 1 }));

  const resumeList = resumes.data || [];
  const primary = resumeList.find((r) => r.is_primary) || resumeList[0];
  const analysis = primary?.analysis;
  const completeness = profile.data?.completeness;
  const ais = aiState(ai.data, ai.error);

  const steps = [
    { done: resumeList.length > 0, label: "Upload your resume", to: "/resume" },
    { done: Boolean(profile.data?.exists), label: "Save your candidate profile", to: "/resume" },
    { done: Boolean(analysis), label: "Run Resume Intelligence on your primary resume", to: "/resume-intelligence" },
    { done: (jobs.data?.total ?? 0) > 0, label: "Find or add your first jobs", to: "/job-search" },
    { done: Boolean(ai.data?.reachable && ai.data?.model_available), label: "Start Ollama and install the local model", to: "/settings" },
  ];

  const firstError = resumes.error || profile.error;

  return (
    <>
      <PageHeader title={`Welcome back, ${user?.full_name?.split(" ")[0] || "there"}`} subtitle="Here is where your career workspace stands today." />

      {firstError && (
        <Alert severity="error" sx={{ mb: 3 }} action={<Button color="inherit" size="small" onClick={() => { resumes.reload(); profile.reload(); }}>Retry</Button>}>
          {firstError}
        </Alert>
      )}

      <Grid container spacing={2.5}>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            icon={FavoriteBorder}
            label="Resume health score"
            value={analysis ? analysis.health_score : "-"}
            caption={analysis ? `Analyzed ${formatDate(primary.analyzed_at)}` : primary ? "Not analyzed yet" : "No resume uploaded"}
            color={analysis ? (analysis.health_score >= 75 ? "success" : analysis.health_score >= 50 ? "warning" : "error") : "primary"}
            loading={resumes.loading && !resumes.data}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            icon={PersonOutline}
            label="Profile completeness"
            value={completeness ? `${completeness.percent}%` : "-"}
            caption={completeness?.missing?.length ? `${completeness.missing.length} section(s) to complete` : completeness ? "Complete" : ""}
            color="secondary"
            loading={profile.loading && !profile.data}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            icon={DescriptionOutlined}
            label="Resumes uploaded"
            value={resumeList.length}
            caption={primary ? `Primary: ${primary.original_filename}` : "Upload a PDF or DOCX"}
            color="info"
            loading={resumes.loading && !resumes.data}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={MemoryOutlined} label="Local AI (Ollama)" value={ais.value} caption={ais.caption} color={ais.color} loading={ai.loading && !ai.data && !ai.error} />
        </Grid>

        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            icon={TravelExploreOutlined}
            label="Jobs discovered"
            value={jobs.error ? "-" : jobs.data?.total ?? 0}
            caption={jobs.error ? "Could not load" : "Saved to your account"}
            color="primary"
            loading={jobs.loading && !jobs.data}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard
            icon={WorkOutlineOutlined}
            label="Matching opportunities"
            value={goodMatches.error ? "-" : goodMatches.data?.total ?? 0}
            caption={goodMatches.error ? "Could not load" : `Score ${GOOD_MATCH_SCORE}+ ("good" or better)`}
            color="success"
            loading={goodMatches.loading && !goodMatches.data}
          />
        </Grid>

        <Grid item xs={12} lg={7}>
          <Card sx={{ height: "100%" }}>
            <CardHeader title="Resume score breakdown" subheader={analysis ? `Primary resume: ${primary.original_filename}` : undefined} />
            <CardContent>
              {analysis?.score_breakdown?.length ? (
                <ScoreBreakdownChart breakdown={analysis.score_breakdown} />
              ) : (
                <Stack alignItems="center" spacing={2} sx={{ py: 6 }}>
                  <Typography color="text.secondary" align="center">
                    {primary ? "Analyze your primary resume to see exactly where its score comes from." : "Upload a resume to get a transparent, evidence-based health score."}
                  </Typography>
                  <Button component={RouterLink} to={primary ? "/resume-intelligence" : "/resume"} variant="contained">
                    {primary ? "Analyze resume" : "Upload resume"}
                  </Button>
                </Stack>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={5}>
          <Stack spacing={2.5} sx={{ height: "100%" }}>
            <Card>
              <CardHeader title="Next steps" />
              <CardContent sx={{ pt: 0 }}>
                <List dense disablePadding>
                  {steps.map((step) => (
                    <ListItem
                      key={step.label}
                      disableGutters
                      secondaryAction={
                        !step.done && (
                          <Button size="small" component={RouterLink} to={step.to}>
                            Go
                          </Button>
                        )
                      }
                    >
                      <ListItemIcon sx={{ minWidth: 32 }}>
                        {step.done ? <CheckCircle fontSize="small" color="success" /> : <RadioButtonUnchecked fontSize="small" color="disabled" />}
                      </ListItemIcon>
                      <ListItemText primary={step.label} primaryTypographyProps={{ color: step.done ? "text.secondary" : "text.primary", sx: step.done ? { textDecoration: "line-through" } : undefined }} />
                    </ListItem>
                  ))}
                </List>
              </CardContent>
            </Card>

            {completeness?.missing?.length > 0 && (
              <Card>
                <CardHeader title="Profile gaps" subheader={`${completeness.percent}% complete`} />
                <CardContent sx={{ pt: 0 }}>
                  <LinearProgress variant="determinate" value={completeness.percent} sx={{ mb: 2, height: 8, borderRadius: 4 }} />
                  <Stack direction="row" flexWrap="wrap" gap={1}>
                    {completeness.missing.map((key) => (
                      <Chip key={key} size="small" variant="outlined" label={COMPLETENESS_LABELS[key] || key} />
                    ))}
                  </Stack>
                  <Button component={RouterLink} to="/resume" size="small" sx={{ mt: 2 }}>
                    Complete profile
                  </Button>
                </CardContent>
              </Card>
            )}
          </Stack>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardHeader
              title="Application pipeline"
              subheader="These metrics appear once the applications and interview modules are built. No placeholder numbers are shown."
            />
            <Divider />
            <CardContent>
              <Grid container spacing={2}>
                {PENDING_METRICS.map(({ label, icon: Icon, phase }) => (
                  <Grid item xs={12} sm={6} md={4} lg={3} key={label}>
                    <Stack direction="row" spacing={1.5} alignItems="center" sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 2 }}>
                      <Icon color="disabled" />
                      <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                        <Typography variant="body2" noWrap>
                          {label}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Awaiting backend
                        </Typography>
                      </Box>
                      <Chip size="small" label={phase} variant="outlined" />
                    </Stack>
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {health.data && (
          <Grid item xs={12}>
            <Typography variant="caption" color="text.secondary">
              Backend {health.data.app} v{health.data.version} ({health.data.environment}) - database {health.data.database?.connected ? "connected" : "unavailable"}
            </Typography>
          </Grid>
        )}
      </Grid>
    </>
  );
}
