import { Link as RouterLink } from "react-router-dom";
import { Alert, Box, Button, Card, CardContent, CardHeader, Chip, CircularProgress, Divider, Grid, List, ListItem, ListItemText, Stack, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import MarkEmailReadOutlined from "@mui/icons-material/MarkEmailReadOutlined";
import EventAvailableOutlined from "@mui/icons-material/EventAvailableOutlined";
import HourglassEmpty from "@mui/icons-material/HourglassEmpty";
import StarBorder from "@mui/icons-material/StarBorder";
import PageHeader from "../components/PageHeader";
import AnimatedPage from "../components/AnimatedPage";
import StatCard from "../components/StatCard";
import useApi from "../hooks/useApi";
import { dashboardApi } from "../services/endpoints";
import { statusLabel } from "../utils/statuses";

const pct = (v) => (v == null ? "-" : `${v}%`);

function ChartBox({ children, height = 280 }) {
  return <Box sx={{ width: "100%", height }}>{children}</Box>;
}

export default function Analytics() {
  const theme = useTheme();
  const { data, loading, error, reload } = useApi(() => dashboardApi.analytics());

  if (loading && !data) return <Box sx={{ textAlign: "center", py: 10 }}><CircularProgress /></Box>;
  if (error && !data) return <Alert severity="error" action={<Button color="inherit" size="small" onClick={reload}>Retry</Button>}>{error}</Alert>;

  const { rates, match_quality: mq, funnel, weekly_applications: weekly, top_missing_skills: gaps, follow_ups: followUps, status_counts: statuses } = data;
  const noSubmitted = rates.submitted === 0;
  const tooltipStyle = { background: theme.palette.background.paper, border: `1px solid ${theme.palette.divider}`, borderRadius: 8 };

  return (
    <AnimatedPage>
      <PageHeader title="Career Analytics" subtitle="Your funnel, response rates and skill gaps, calculated from your own saved data." />

      <Grid container spacing={2.5}>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={MarkEmailReadOutlined} label="Response rate" value={pct(rates.response_rate)} caption={noSubmitted ? "Submit applications to see this" : `of ${rates.submitted} submitted`} color="primary" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={EventAvailableOutlined} label="Interview rate" value={pct(rates.interview_rate)} caption={noSubmitted ? "No submitted applications yet" : "interviews or offers"} color="success" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={HourglassEmpty} label="No-response rate" value={pct(rates.no_response_rate)} caption={noSubmitted ? "No submitted applications yet" : "marked No response"} color="warning" />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <StatCard icon={StarBorder} label="Average match score" value={mq.average_score ?? "-"} caption={mq.average_score == null ? "No scored jobs yet" : "across saved jobs"} color="secondary" />
        </Grid>

        <Grid item xs={12} lg={6}>
          <Card sx={{ height: "100%" }}>
            <CardHeader title="Application funnel" subheader="From jobs found to offers" />
            <CardContent>
              <ChartBox>
                <ResponsiveContainer>
                  <BarChart data={funnel} layout="vertical" margin={{ left: 20, right: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} horizontal={false} />
                    <XAxis type="number" allowDecimals={false} stroke={theme.palette.text.secondary} />
                    <YAxis type="category" dataKey="stage" width={130} stroke={theme.palette.text.secondary} />
                    <Tooltip contentStyle={tooltipStyle} cursor={{ fill: theme.palette.action.hover }} />
                    <Bar dataKey="value" name="Count" fill={theme.palette.primary.main} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartBox>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} lg={6}>
          <Card sx={{ height: "100%" }}>
            <CardHeader title="Applications submitted per week" subheader="Last 12 weeks, by application date" />
            <CardContent>
              <ChartBox>
                <ResponsiveContainer>
                  <BarChart data={weekly} margin={{ right: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} vertical={false} />
                    <XAxis dataKey="label" stroke={theme.palette.text.secondary} fontSize={12} />
                    <YAxis allowDecimals={false} stroke={theme.palette.text.secondary} />
                    <Tooltip contentStyle={tooltipStyle} cursor={{ fill: theme.palette.action.hover }} />
                    <Bar dataKey="applications" name="Applications" fill={theme.palette.secondary.main} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </ChartBox>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card sx={{ height: "100%" }}>
            <CardHeader title="Most common missing skills" subheader="Required skills you lack, across your saved jobs" />
            <Divider />
            <CardContent>
              {gaps.length ? (
                <Stack spacing={1.5}>
                  {gaps.map((g) => (
                    <Stack key={g.skill} direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="body2">{g.skill}</Typography>
                      <Chip size="small" variant="outlined" color="warning" label={`${g.jobs} job(s)`} />
                    </Stack>
                  ))}
                </Stack>
              ) : (
                <Typography color="text.secondary">No skill gaps to show yet. Save and score some jobs first.</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card sx={{ height: "100%" }}>
            <CardHeader title="Follow-ups due" subheader="Due within 7 days, or overdue" />
            <Divider />
            <CardContent sx={{ p: 0 }}>
              {followUps.length ? (
                <List disablePadding>
                  {followUps.map((f) => (
                    <ListItem key={f.id} divider>
                      <ListItemText primary={`${f.job_title} at ${f.company}`} secondary={`${statusLabel(f.status)} - ${f.follow_up_date}`} />
                      {f.overdue && <Chip size="small" color="error" label="Overdue" />}
                    </ListItem>
                  ))}
                </List>
              ) : (
                <Typography color="text.secondary" sx={{ p: 3 }}>Nothing due. Set follow-up dates on your applications to see reminders here.</Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {Object.keys(statuses).length > 0 && (
          <Grid item xs={12}>
            <Card>
              <CardHeader title="Applications by status" />
              <CardContent>
                <Stack direction="row" flexWrap="wrap" gap={1}>
                  {Object.entries(statuses).map(([status, n]) => <Chip key={status} label={`${statusLabel(status)}: ${n}`} variant="outlined" />)}
                </Stack>
                <Button component={RouterLink} to="/applications" size="small" sx={{ mt: 2 }}>Open applications</Button>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </AnimatedPage>
  );
}
