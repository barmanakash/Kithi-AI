import { Link as RouterLink } from "react-router-dom";
import { Alert, Box, Button, Card, CardContent, Chip, CircularProgress, Grid, List, ListItem, ListItemIcon, ListItemText, Stack, Typography } from "@mui/material";
import AssignmentOutlined from "@mui/icons-material/AssignmentOutlined";
import SendOutlined from "@mui/icons-material/SendOutlined";
import EventAvailableOutlined from "@mui/icons-material/EventAvailableOutlined";
import MarkEmailReadOutlined from "@mui/icons-material/MarkEmailReadOutlined";
import StarBorder from "@mui/icons-material/StarBorder";
import AutoAwesomeMotionOutlined from "@mui/icons-material/AutoAwesomeMotionOutlined";
import FavoriteBorder from "@mui/icons-material/FavoriteBorder";
import PersonOutline from "@mui/icons-material/PersonOutline";
import ArrowForward from "@mui/icons-material/ArrowForward";
import RefreshOutlined from "@mui/icons-material/RefreshOutlined";
import PageHeader from "../components/PageHeader";
import AnimatedPage from "../components/AnimatedPage";
import StatCard from "../components/StatCard";
import useApi from "../hooks/useApi";
import { recoveryApi } from "../services/endpoints";

const SEVERITY = {
  high: { label: "High priority", color: "error" },
  medium: { label: "Medium priority", color: "warning" },
  low: { label: "Low priority", color: "info" },
  info: { label: "Note", color: "default" },
};

// Where each finding is best acted on. Only routes that exist in the app.
const FIX_LINKS = {
  not_enough_data: { label: "Open Applications", to: "/applications" },
  low_interview_rate: { label: "Review job matches", to: "/job-matches" },
  low_match_targeting: { label: "Review job matches", to: "/job-matches" },
  no_tailoring: { label: "Tailor a resume", to: "/resume" },
  stale_applications: { label: "Draft follow-ups", to: "/recruiter-hub" },
  overdue_follow_ups: { label: "Draft follow-ups", to: "/recruiter-hub" },
  low_recent_activity: { label: "Find jobs", to: "/job-search" },
  weak_resume: { label: "Open Resume Intelligence", to: "/resume-intelligence" },
  incomplete_profile: { label: "Complete profile", to: "/resume" },
};

const pct = (v) => (v == null ? "-" : `${v}%`);

export default function Recovery() {
  const { data, loading, error, reload } = useApi(() => recoveryApi.get());

  if (loading && !data) return <Box sx={{ textAlign: "center", py: 10 }}><CircularProgress /></Box>;
  if (error && !data) {
    return (
      <AnimatedPage>
        <PageHeader title="Job Search Recovery" />
        <Alert severity="error" action={<Button color="inherit" size="small" onClick={reload}>Retry</Button>}>{error}</Alert>
      </AnimatedPage>
    );
  }

  const { summary, metrics: m, findings, limits } = data;
  const realFindings = findings.filter((f) => f.id !== "not_enough_data");
  const summarySeverity = realFindings.some((f) => f.severity === "high") ? "warning" : realFindings.length ? "info" : "success";

  return (
    <AnimatedPage>
      <PageHeader
        title="Job Search Recovery"
        subtitle="Find out what may be holding your search back, using only your own tracked applications, matches, resume and profile."
        actions={
          <Button startIcon={<RefreshOutlined />} onClick={reload} disabled={loading}>
            {loading ? "Analyzing..." : "Re-run analysis"}
          </Button>
        }
      />

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Alert severity={m.submitted < 5 ? "info" : summarySeverity} sx={{ mb: 3 }}>{summary}</Alert>

      <Grid container spacing={2.5} sx={{ mb: 1 }}>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={AssignmentOutlined} label="Applications tracked" value={m.applications_total} caption={`${m.submitted_last_14_days} submitted in the last 14 days`} color="primary" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={SendOutlined} label="Submitted" value={m.submitted} caption="Marked as applied by you" color="info" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={EventAvailableOutlined} label="Interview rate" value={pct(m.interview_rate_percent)} caption={m.submitted ? `${m.interviews_or_offers} interview(s) or offer(s)` : "No submitted applications yet"} color="success" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={MarkEmailReadOutlined} label="Response rate" value={pct(m.response_rate_percent)} caption={m.submitted ? `${m.rejections} rejection(s) included` : "No submitted applications yet"} color="secondary" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={StarBorder} label="Avg match of submitted" value={m.average_match_score_submitted ?? "-"} caption={m.average_match_score_submitted == null ? "No scored applications" : "Out of 100"} color="warning" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={AutoAwesomeMotionOutlined} label="With tailored resume" value={pct(m.share_with_tailored_resume_percent)} caption="Of submitted applications" color="info" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={FavoriteBorder} label="Resume health" value={m.resume_health_score ?? "-"} caption={m.resume_health_score == null ? "Resume not analyzed yet" : "Out of 100"} color={m.resume_health_score != null && m.resume_health_score < 60 ? "error" : "success"} />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={PersonOutline} label="Profile completeness" value={pct(m.profile_completeness_percent)} caption="Used for matching and tailoring" color="secondary" />
        </Grid>
      </Grid>

      <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>
        Findings
      </Typography>
      {findings.length === 0 ? (
        <Card>
          <CardContent>
            <Typography color="text.secondary">Nothing stands out in the data available. Keep tracking your applications so this analysis stays accurate.</Typography>
          </CardContent>
        </Card>
      ) : (
        <Stack spacing={2}>
          {findings.map((f) => {
            const sev = SEVERITY[f.severity] || SEVERITY.info;
            const link = FIX_LINKS[f.id];
            return (
              <Card key={f.id}>
                <CardContent>
                  <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 1 }}>
                    <Chip size="small" color={sev.color} label={sev.label} />
                    <Typography variant="subtitle1" fontWeight={600}>{f.title}</Typography>
                  </Stack>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                    <strong>What the data shows:</strong> {f.evidence}
                  </Typography>
                  <Typography variant="subtitle2">What to try</Typography>
                  <List dense disablePadding>
                    {f.actions.map((action) => (
                      <ListItem key={action} disableGutters alignItems="flex-start">
                        <ListItemIcon sx={{ minWidth: 28, mt: 0.5 }}><ArrowForward fontSize="small" color="primary" /></ListItemIcon>
                        <ListItemText primary={action} />
                      </ListItem>
                    ))}
                  </List>
                  {link && (
                    <Button component={RouterLink} to={link.to} size="small" sx={{ mt: 1 }}>
                      {link.label}
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </Stack>
      )}

      <Alert severity="info" variant="outlined" sx={{ mt: 3 }}>{limits}</Alert>
    </AnimatedPage>
  );
}
