import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  LinearProgress,
  MenuItem,
  Slider,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import RefreshOutlined from "@mui/icons-material/RefreshOutlined";
import AutoAwesomeOutlined from "@mui/icons-material/AutoAwesomeOutlined";
import AddTaskOutlined from "@mui/icons-material/AddTaskOutlined";
import NoteAddOutlined from "@mui/icons-material/NoteAddOutlined";
import PageHeader from "../components/PageHeader";
import AnimatedPage from "../components/AnimatedPage";
import ScoreRing from "../components/ScoreRing";
import GenerateDialog from "../components/GenerateDialog";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { applicationsApi, matchesApi } from "../services/endpoints";
import { errorMessage, scoreColor } from "../utils/format";
import { MATCH_LABEL_COLORS } from "../utils/statuses";

const WEIGHT_KEYS = [
  ["skills", "Skills"],
  ["experience", "Experience"],
  ["responsibilities", "Responsibilities"],
  ["education", "Education"],
  ["location", "Location"],
  ["preferences", "Preferences"],
];

function WeightsPanel({ onSaved }) {
  const toast = useToast();
  const weights = useApi(() => matchesApi.weights());
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (weights.data) setDraft(weights.data.weights);
  }, [weights.data]);

  if (!draft) return weights.error ? <Alert severity="error">{weights.error}</Alert> : null;

  const total = Object.values(draft).reduce((a, b) => a + Number(b), 0);

  const save = async () => {
    setSaving(true);
    try {
      const res = await matchesApi.saveWeights(draft);
      toast.success(`Weights saved. ${res.rescored} job(s) re-scored.`);
      onSaved();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardHeader title="Match weights" subheader="Choose what matters most. Weights are normalised, and components with no usable data are excluded rather than guessed." />
      <CardContent>
        <Grid container spacing={3}>
          {WEIGHT_KEYS.map(([key, label]) => (
            <Grid item xs={12} sm={6} md={4} key={key}>
              <Typography variant="body2" gutterBottom>
                {label}: {draft[key]}{total > 0 ? ` (${Math.round((100 * draft[key]) / total)}%)` : ""}
              </Typography>
              <Slider value={Number(draft[key])} min={0} max={100} step={5} onChange={(_, v) => setDraft((d) => ({ ...d, [key]: v }))} />
            </Grid>
          ))}
        </Grid>
        <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
          <Button variant="contained" onClick={save} disabled={saving || total <= 0}>
            {saving ? "Saving..." : "Save and re-score"}
          </Button>
          <Button color="inherit" onClick={() => setDraft(weights.data.defaults)} disabled={saving}>
            Reset to defaults
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}

function MatchDialog({ jobId, onClose, onTrack, onGenerate }) {
  const toast = useToast();
  const detail = useApi(() => (jobId ? matchesApi.detail(jobId) : Promise.resolve(null)), [jobId]);
  const [explaining, setExplaining] = useState(false);
  const [explanation, setExplanation] = useState(null);

  useEffect(() => setExplanation(null), [jobId]);

  const explain = async () => {
    setExplaining(true);
    try {
      const res = await matchesApi.explain(jobId);
      setExplanation(res);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setExplaining(false);
    }
  };

  const job = detail.data?.job;
  const match = detail.data?.match;

  return (
    <Dialog open={Boolean(jobId)} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{job ? `${job.title} - ${job.company}` : "Match details"}</DialogTitle>
      <DialogContent dividers>
        {detail.loading && !detail.data && <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress /></Box>}
        {detail.error && <Alert severity="error">{detail.error}</Alert>}
        {match && (
          <Stack spacing={3}>
            <Stack direction="row" spacing={3} alignItems="center">
              {match.score != null ? <ScoreRing value={match.score} size={96} label={match.label} /> : <Chip label="Not enough data to score" />}
              <Box>
                {(match.notes || []).map((n) => (
                  <Typography key={n} variant="body2" color="text.secondary">{n}</Typography>
                ))}
              </Box>
            </Stack>

            <Box>
              <Typography variant="subtitle2" gutterBottom>How the score is built</Typography>
              <Stack spacing={2}>
                {match.components.map((c) => (
                  <Box key={c.key}>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="body2" fontWeight={600}>{c.label} <Typography component="span" variant="caption" color="text.secondary">(weight {c.weight})</Typography></Typography>
                      <Typography variant="body2">{c.score_percent == null ? "no data" : `${c.score_percent}%`}</Typography>
                    </Stack>
                    <LinearProgress variant="determinate" value={c.score_percent ?? 0} color={c.score_percent == null ? "inherit" : scoreColor(c.score_percent)} sx={{ height: 6, borderRadius: 3, my: 0.5, opacity: c.score_percent == null ? 0.3 : 1 }} />
                    <Typography variant="caption" color="text.secondary">{c.detail}</Typography>
                  </Box>
                ))}
              </Stack>
            </Box>

            <Divider />
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>Matching skills ({match.matched_skills.length})</Typography>
                <Stack direction="row" flexWrap="wrap" gap={1}>
                  {match.matched_skills.length ? match.matched_skills.map((m) => (
                    <Chip key={m.skill} size="small" color="success" variant="outlined" label={`${m.skill} (${m.candidate_source})`} />
                  )) : <Typography variant="body2" color="text.secondary">None found.</Typography>}
                </Stack>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle2" gutterBottom>Missing skills ({match.missing_skills.length})</Typography>
                <Stack spacing={1}>
                  {match.missing_skills.length ? match.missing_skills.map((m) => (
                    <Box key={m.skill}>
                      <Chip size="small" color={m.optional ? "default" : "warning"} variant="outlined" label={`${m.skill}${m.optional ? " (preferred)" : ""}`} />
                      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                        Job says: "{m.job_evidence}"
                      </Typography>
                    </Box>
                  )) : <Typography variant="body2" color="text.secondary">Nothing missing.</Typography>}
                </Stack>
              </Grid>
            </Grid>

            {explanation && (
              <Alert severity={explanation.explanation ? "info" : "warning"}>
                {explanation.explanation || `The local AI could not write a summary: ${explanation.ai_error}`}
              </Alert>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={explain} disabled={!match || explaining} startIcon={explaining ? <CircularProgress size={16} /> : <AutoAwesomeOutlined />}>
          {explaining ? "Asking local AI..." : "Explain with local AI"}
        </Button>
        <span style={{ flexGrow: 1 }} />
        {job && <Button startIcon={<NoteAddOutlined />} onClick={() => onGenerate(job)}>Tailor documents</Button>}
        {job && <Button startIcon={<AddTaskOutlined />} onClick={() => onTrack(job)}>Track application</Button>}
        <Button onClick={onClose} variant="contained">Close</Button>
      </DialogActions>
    </Dialog>
  );
}

export default function JobMatches() {
  const toast = useToast();
  const [minScore, setMinScore] = useState("");
  const [openId, setOpenId] = useState(null);
  const [genJob, setGenJob] = useState(null);
  const navigate = useNavigate();
  const [recomputing, setRecomputing] = useState(false);
  const matches = useApi(() => matchesApi.list({ min_score: minScore === "" ? undefined : minScore, limit: 100 }), [minScore]);

  const recompute = async () => {
    setRecomputing(true);
    try {
      const res = await matchesApi.recompute();
      if (res.note) toast.info(res.note);
      else toast.success(`${res.rescored} job(s) re-scored.`);
      matches.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setRecomputing(false);
    }
  };

  const track = async (job) => {
    try {
      const res = await applicationsApi.fromJob(job.id);
      toast[res.created ? "success" : "info"](res.created ? "Added to Applications as Saved." : "Already in your Applications.");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const items = matches.data?.matches || [];

  return (
    <AnimatedPage>
      <PageHeader
        title="Job Matches"
        subtitle="Transparent compatibility scores. Open any match to see the exact evidence behind it."
        actions={
          <Button variant="outlined" startIcon={recomputing ? <CircularProgress size={16} /> : <RefreshOutlined />} onClick={recompute} disabled={recomputing}>
            Re-score all
          </Button>
        }
      />

      <WeightsPanel onSaved={matches.reload} />

      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <TextField select size="small" label="Minimum score" value={minScore} onChange={(e) => setMinScore(e.target.value)} sx={{ minWidth: 180 }}>
          <MenuItem value="">All jobs</MenuItem>
          {[35, 55, 75].map((n) => (
            <MenuItem key={n} value={n}>{n}+ ({n === 35 ? "partial and up" : n === 55 ? "good and up" : "strong"})</MenuItem>
          ))}
        </TextField>
        <Typography variant="body2" color="text.secondary">{items.length} match(es)</Typography>
      </Stack>

      {matches.error && <Alert severity="error" sx={{ mb: 2 }}>{matches.error}</Alert>}
      {matches.loading && !matches.data ? (
        <Box sx={{ textAlign: "center", py: 6 }}><CircularProgress /></Box>
      ) : items.length ? (
        <Stack spacing={2}>
          {items.map((m) => (
            <Card key={m.job.id} variant="outlined">
              <CardActionArea onClick={() => setOpenId(m.job.id)}>
                <CardContent>
                  <Stack direction="row" spacing={2} alignItems="center">
                    {m.score != null ? <ScoreRing value={m.score} size={64} label="" /> : <Chip label="n/a" variant="outlined" />}
                    <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                      <Typography variant="subtitle1" fontWeight={600} noWrap>{m.job.title}</Typography>
                      <Typography variant="body2" color="text.secondary" noWrap>{m.job.company}{m.job.location ? ` - ${m.job.location}` : ""}</Typography>
                      <Stack direction="row" gap={0.5} flexWrap="wrap" sx={{ mt: 1 }}>
                        <Chip size="small" color={MATCH_LABEL_COLORS[m.label] || "default"} label={m.label} />
                        {m.matched_skills.slice(0, 5).map((s) => <Chip key={s} size="small" variant="outlined" color="success" label={s} />)}
                        {m.missing_skills.slice(0, 3).map((s) => <Chip key={s} size="small" variant="outlined" color="warning" label={`missing: ${s}`} />)}
                      </Stack>
                    </Box>
                  </Stack>
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Stack>
      ) : (
        <Typography color="text.secondary" align="center" sx={{ py: 6 }}>
          No matches yet. Save jobs from AI Job Search, and make sure you have uploaded a resume or completed your profile.
        </Typography>
      )}

      <MatchDialog jobId={openId} onClose={() => setOpenId(null)} onTrack={track} onGenerate={setGenJob} />
      <GenerateDialog
        open={Boolean(genJob)}
        job={genJob}
        onClose={() => setGenJob(null)}
        onCreated={(version) => {
          setGenJob(null);
          setOpenId(null);
          toast.success("Draft created. Review it before you use it.");
          navigate(`/resume?tab=generated&version=${version.id}`);
        }}
      />
    </AnimatedPage>
  );
}
