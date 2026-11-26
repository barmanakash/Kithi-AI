import { Alert, Box, Card, CardContent, CardHeader, Grid, LinearProgress, Skeleton, Stack, Typography } from "@mui/material";
import useApi from "../../hooks/useApi";
import { careerApi } from "../../services/endpoints";
import { scoreColor } from "../../utils/format";

function Bar({ label, percent }) {
  return (
    <Box>
      <Stack direction="row" justifyContent="space-between">
        <Typography variant="body2">{label}</Typography>
        <Typography variant="body2" fontWeight={600}>{percent}%</Typography>
      </Stack>
      <LinearProgress variant="determinate" value={Math.min(100, percent)} color={scoreColor(percent)} sx={{ height: 8, borderRadius: 4 }} />
    </Box>
  );
}

function Fact({ label, value }) {
  return (
    <Stack direction="row" justifyContent="space-between" sx={{ py: 0.5 }}>
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Typography variant="body2" fontWeight={600}>{value ?? "-"}</Typography>
    </Stack>
  );
}

export default function ProgressTab() {
  const { data, loading, error } = useApi(() => careerApi.progress(), []);
  if (error) return <Alert severity="error">{error}</Alert>;
  if (loading && !data) return <Skeleton variant="rounded" height={200} />;
  const p = data;

  return (
    <Grid container spacing={2.5}>
      <Grid item xs={12} md={5}>
        <Card sx={{ height: "100%" }}>
          <CardHeader title="Overall progress" />
          <CardContent sx={{ pt: 0 }}>
            <Typography variant="h2" fontWeight={700}>{p.overall_percent == null ? "-" : `${p.overall_percent}%`}</Typography>
            <Stack spacing={1.5} sx={{ mt: 2 }}>
              {p.components.map((c) => <Bar key={c.label} label={c.label} percent={c.percent} />)}
            </Stack>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: "block" }}>{p.note}</Typography>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} md={7}>
        <Stack spacing={2.5}>
          <Card>
            <CardHeader title="Learning" />
            <CardContent sx={{ pt: 0 }}>
              <Fact label="Learning plans" value={p.learning.plans} />
              <Fact label="Milestones done" value={`${p.learning.items_done} of ${p.learning.items_total}`} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader title="Skills" />
            <CardContent sx={{ pt: 0 }}>
              <Fact label="Skills in profile and resume" value={p.skills.skills_in_profile_and_resume} />
              <Fact label="Self-assessed skills" value={p.skills.assessed} />
              <Fact label="Average self-rating (1-5)" value={p.skills.average_level} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader title="Interviews" />
            <CardContent sx={{ pt: 0 }}>
              <Fact label="Scored practice sessions" value={p.interviews.scored_sessions} />
              <Fact label="Average score (0-10)" value={p.interviews.average_score} />
              <Fact label="Trend" value={p.interviews.trend || "Needs 4+ sessions"} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader title="Applications" />
            <CardContent sx={{ pt: 0 }}>
              <Fact label="Tracked" value={p.applications.total} />
              <Fact label="Submitted" value={p.applications.submitted} />
              <Fact label="Reached interview or offer" value={p.applications.reached_interview_or_offer} />
              <Fact label="Interview rate" value={p.applications.interview_rate_percent == null ? "-" : `${p.applications.interview_rate_percent}%`} />
            </CardContent>
          </Card>
        </Stack>
      </Grid>
    </Grid>
  );
}
