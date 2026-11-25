import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink, useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Grid,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  MenuItem,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import PlayArrow from "@mui/icons-material/PlayArrow";
import LightbulbOutlined from "@mui/icons-material/LightbulbOutlined";
import PageHeader from "../components/PageHeader";
import ScoreRing from "../components/ScoreRing";
import ScoreBreakdownChart from "../components/ScoreBreakdownChart";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { resumesApi } from "../services/endpoints";
import { errorMessage, formatDateTime, scoreColor } from "../utils/format";

function SuggestionList({ items }) {
  if (!items?.length) return <Typography variant="body2" color="text.secondary">No suggestions.</Typography>;
  return (
    <List dense disablePadding>
      {items.map((item, i) => (
        <ListItem key={i} disableGutters alignItems="flex-start">
          <ListItemIcon sx={{ minWidth: 32, mt: 0.5 }}>
            <LightbulbOutlined fontSize="small" color="warning" />
          </ListItemIcon>
          <ListItemText primary={item} />
        </ListItem>
      ))}
    </List>
  );
}

export default function ResumeIntelligence() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const { data, loading, error, reload } = useApi(() => resumesApi.list());
  const [running, setRunning] = useState(false);
  const [fresh, setFresh] = useState({}); // resume_id -> latest analysis from this session

  const resumes = useMemo(() => data || [], [data]);
  const requested = params.get("resume");
  const selectedId =
    (requested && resumes.find((r) => r.id === requested)?.id) || resumes.find((r) => r.is_primary)?.id || resumes[0]?.id || "";
  const selected = resumes.find((r) => r.id === selectedId);

  // Keep the URL in sync with the selection.
  useEffect(() => {
    if (selectedId && requested !== selectedId) setParams({ resume: selectedId }, { replace: true });
  }, [selectedId, requested, setParams]);

  const analysis = selected ? fresh[selected.id] || (selected.analysis ? { ...selected.analysis, analyzed_at: selected.analyzed_at } : null) : null;

  const runAnalysis = async () => {
    if (!selected) return;
    setRunning(true);
    try {
      const result = await resumesApi.analyze(selected.id);
      setFresh((f) => ({ ...f, [selected.id]: result }));
      toast.success(result.ai ? "Analysis complete" : "Score calculated. AI extraction was unavailable.");
      reload();
    } catch (err) {
      toast.error(errorMessage(err, "Analysis failed"));
    } finally {
      setRunning(false);
    }
  };

  if (loading && !data) {
    return (
      <>
        <PageHeader title="Resume Intelligence" />
        <Skeleton variant="rounded" height={320} />
      </>
    );
  }

  if (error) {
    return (
      <>
        <PageHeader title="Resume Intelligence" />
        <Alert severity="error" action={<Button color="inherit" size="small" onClick={reload}>Retry</Button>}>
          {error}
        </Alert>
      </>
    );
  }

  if (resumes.length === 0) {
    return (
      <>
        <PageHeader title="Resume Intelligence" subtitle="Transparent resume scoring with local AI extraction." />
        <Card>
          <CardContent sx={{ textAlign: "center", py: 6 }}>
            <Typography color="text.secondary" sx={{ mb: 2 }}>
              Upload a resume first, then come back to analyze it.
            </Typography>
            <Button variant="contained" component={RouterLink} to="/resume">
              Go to My Resume
            </Button>
          </CardContent>
        </Card>
      </>
    );
  }

  const ai = analysis?.ai;
  const flags = Array.isArray(analysis?.injection_flags) ? analysis.injection_flags : [];

  return (
    <>
      <PageHeader
        title="Resume Intelligence"
        subtitle="Every score point is backed by evidence from your resume. AI extraction runs locally and can only report skills that literally appear in your text."
        actions={
          <Button variant="contained" startIcon={<PlayArrow />} onClick={runAnalysis} disabled={running}>
            {running ? "Analyzing..." : analysis ? "Re-run analysis" : "Run analysis"}
          </Button>
        }
      />

      <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }} sx={{ mb: 3 }}>
        <TextField
          select
          size="small"
          label="Resume"
          value={selectedId}
          onChange={(e) => setParams({ resume: e.target.value })}
          sx={{ minWidth: { sm: 360 } }}
          disabled={running}
        >
          {resumes.map((r) => (
            <MenuItem key={r.id} value={r.id}>
              {r.original_filename}
              {r.is_primary ? " (primary)" : ""}
            </MenuItem>
          ))}
        </TextField>
        {analysis?.analyzed_at && (
          <Typography variant="body2" color="text.secondary">
            Last analyzed {formatDateTime(analysis.analyzed_at)}
          </Typography>
        )}
      </Stack>

      {running && (
        <Alert severity="info" icon={false} sx={{ mb: 3 }}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            Running on your local model. This can take a minute on modest hardware.
          </Typography>
          <LinearProgress />
        </Alert>
      )}

      {!analysis ? (
        <Card>
          <CardContent sx={{ textAlign: "center", py: 6 }}>
            <Typography color="text.secondary">This resume has not been analyzed yet. Press "Run analysis" to start.</Typography>
          </CardContent>
        </Card>
      ) : (
        <Grid container spacing={2.5}>
          <Grid item xs={12} md={4}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Stack alignItems="center" spacing={2}>
                  <ScoreRing value={analysis.health_score} size={150} label="health score" />
                  <Chip color={scoreColor(analysis.health_score)} variant="outlined" label={analysis.health_score >= 75 ? "Strong" : analysis.health_score >= 50 ? "Needs work" : "Weak"} />
                  <Typography variant="body2" color="text.secondary">
                    {analysis.word_count} words
                  </Typography>
                </Stack>
                <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>
                  Sections found
                </Typography>
                <Stack direction="row" flexWrap="wrap" gap={1}>
                  {analysis.sections_found?.length ? analysis.sections_found.map((s) => <Chip key={s} size="small" color="success" variant="outlined" label={s} />) : <Typography variant="body2" color="text.secondary">None detected</Typography>}
                </Stack>
                {analysis.sections_missing?.length > 0 && (
                  <>
                    <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
                      Sections missing
                    </Typography>
                    <Stack direction="row" flexWrap="wrap" gap={1}>
                      {analysis.sections_missing.map((s) => (
                        <Chip key={s} size="small" color="warning" variant="outlined" label={s} />
                      ))}
                    </Stack>
                  </>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={8}>
            <Card sx={{ height: "100%" }}>
              <CardHeader title="Score breakdown" subheader="Points earned out of the maximum for each rule" />
              <CardContent sx={{ pt: 0 }}>
                <ScoreBreakdownChart breakdown={analysis.score_breakdown || []} />
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12}>
            <Card>
              <CardHeader title="Evidence" subheader="Why each rule scored the way it did" />
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Rule</TableCell>
                      <TableCell align="right">Score</TableCell>
                      <TableCell>Evidence</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(analysis.score_breakdown || []).map((row) => (
                      <TableRow key={row.label}>
                        <TableCell>{row.label}</TableCell>
                        <TableCell align="right">
                          {row.points}/{row.max}
                        </TableCell>
                        <TableCell sx={{ color: "text.secondary" }}>{row.evidence}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card sx={{ height: "100%" }}>
              <CardHeader title="Rule-based suggestions" />
              <CardContent sx={{ pt: 0 }}>
                <SuggestionList items={analysis.rule_based_suggestions} />
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card sx={{ height: "100%" }}>
              <CardHeader title="AI extraction (local model)" />
              <CardContent sx={{ pt: 0 }}>
                {analysis.ai_error && (
                  <Alert severity="warning" sx={{ mb: 2 }}>
                    The local AI could not run: {analysis.ai_error}. The rule-based score above is still valid.
                  </Alert>
                )}
                {ai ? (
                  <Stack spacing={2}>
                    {ai.summary && <Typography variant="body2">{ai.summary}</Typography>}
                    <Box>
                      <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        Skills found in your resume
                      </Typography>
                      <Stack direction="row" flexWrap="wrap" gap={1}>
                        {ai.skills?.length ? ai.skills.map((s) => <Chip key={s} size="small" label={s} />) : <Typography variant="body2" color="text.secondary">None</Typography>}
                      </Stack>
                    </Box>
                    {ai.job_titles?.length > 0 && (
                      <Box>
                        <Typography variant="subtitle2" sx={{ mb: 1 }}>
                          Job titles
                        </Typography>
                        <Stack direction="row" flexWrap="wrap" gap={1}>
                          {ai.job_titles.map((t) => (
                            <Chip key={t} size="small" variant="outlined" label={t} />
                          ))}
                        </Stack>
                      </Box>
                    )}
                    {ai.years_experience != null && (
                      <Typography variant="body2">
                        Estimated experience: <strong>{ai.years_experience} years</strong>
                      </Typography>
                    )}
                    {ai.suggestions?.length > 0 && (
                      <Box>
                        <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                          AI suggestions
                        </Typography>
                        <SuggestionList items={ai.suggestions} />
                      </Box>
                    )}
                    {ai.unsupported_items_removed > 0 && (
                      <Typography variant="caption" color="text.secondary">
                        {ai.unsupported_items_removed} AI-suggested item(s) were discarded because they did not appear in your resume text.
                      </Typography>
                    )}
                  </Stack>
                ) : (
                  !analysis.ai_error && <Typography variant="body2" color="text.secondary">No AI extraction is stored for this analysis.</Typography>
                )}
              </CardContent>
            </Card>
          </Grid>

          {flags.length > 0 && (
            <Grid item xs={12}>
              <Alert severity="warning">
                This resume contains text that looks like instructions to an AI system. It was treated as untrusted content and cannot trigger any action.
                Flags: {flags.map((f) => (typeof f === "string" ? f : JSON.stringify(f))).join(", ")}
              </Alert>
            </Grid>
          )}
        </Grid>
      )}
    </>
  );
}
