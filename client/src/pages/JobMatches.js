import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Skeleton,
  Slider,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import TuneIcon from "@mui/icons-material/Tune";
import RefreshIcon from "@mui/icons-material/Refresh";
import { Link as RouterLink } from "react-router-dom";
import PageHeader from "../components/PageHeader";
import JobCard from "../components/jobs/JobCard";
import JobDetailDialog from "../components/jobs/JobDetailDialog";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { jobsApi, matchesApi } from "../services/endpoints";
import { errorMessage } from "../utils/format";
import { WEIGHT_HELP } from "../utils/jobs";

const PAGE = 25;
const FILTERS = [
  { value: 0, label: "All scores" },
  { value: 35, label: "Partial or better (35+)" },
  { value: 55, label: "Good or better (55+)" },
  { value: 75, label: "Strong only (75+)" },
];

function WeightsDialog({ open, onClose, onSaved }) {
  const toast = useToast();
  const [info, setInfo] = useState(null);
  const [weights, setWeights] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError("");
    matchesApi
      .getWeights()
      .then((res) => {
        setInfo(res);
        setWeights(res.weights);
      })
      .catch((err) => setError(errorMessage(err)));
  }, [open]);

  const total = weights ? Object.values(weights).reduce((a, b) => a + b, 0) : 0;

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await matchesApi.saveWeights(weights);
      const res = await jobsApi.rescoreAll();
      toast.success(`Weights saved. ${res.rescored} job(s) re-scored.`);
      onSaved();
    } catch (err) {
      setError(errorMessage(err, "Could not save the weights"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Scoring weights</DialogTitle>
      <DialogContent dividers>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Decide how much each factor counts. Factors with no usable data are left out and the rest are re-balanced, so missing information never skews a score.
        </Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {!weights && !error && <Skeleton variant="rounded" height={240} />}
        {weights && info && (
          <Stack spacing={2.5}>
            {Object.keys(info.defaults).map((key) => (
              <Box key={key}>
                <Stack direction="row" justifyContent="space-between">
                  <Typography variant="body2" fontWeight={600}>
                    {info.labels[key]}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {weights[key]} {total > 0 ? `(${Math.round((100 * weights[key]) / total)}% of total)` : ""}
                  </Typography>
                </Stack>
                <Slider size="small" min={0} max={100} step={5} value={weights[key]} onChange={(_, v) => setWeights((w) => ({ ...w, [key]: v }))} />
                <Typography variant="caption" color="text.secondary">
                  {WEIGHT_HELP[key]}
                </Typography>
              </Box>
            ))}
          </Stack>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button color="inherit" onClick={() => info && setWeights(info.defaults)} disabled={saving || !info} sx={{ mr: "auto" }}>
          Reset to defaults
        </Button>
        <Button color="inherit" onClick={onClose} disabled={saving}>
          Cancel
        </Button>
        <Button variant="contained" onClick={save} disabled={saving || !weights || total <= 0}>
          {saving ? "Saving..." : "Save and re-score"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default function JobMatches() {
  const toast = useToast();
  const [minScore, setMinScore] = useState(0);
  const [limit, setLimit] = useState(PAGE);
  const [refreshKey, setRefreshKey] = useState(0);
  const [openId, setOpenId] = useState(null);
  const [weightsOpen, setWeightsOpen] = useState(false);
  const [rescoring, setRescoring] = useState(false);

  const { data, loading, error, reload } = useApi(
    () => matchesApi.list({ min_score: minScore, limit }),
    [minScore, limit, refreshKey]
  );
  const items = data?.items || [];

  const rescoreAll = async () => {
    setRescoring(true);
    try {
      const res = await jobsApi.rescoreAll();
      toast.success(`${res.rescored} job(s) re-scored`);
      setRefreshKey((k) => k + 1);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setRescoring(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Job Matches"
        subtitle="Your saved jobs ranked by a transparent score. Open any job to see exactly which skills matched and which are missing."
        actions={
          <>
            <Button startIcon={<TuneIcon />} onClick={() => setWeightsOpen(true)}>
              Weights
            </Button>
            <Button startIcon={<RefreshIcon />} onClick={rescoreAll} disabled={rescoring}>
              {rescoring ? "Re-scoring..." : "Re-score all"}
            </Button>
          </>
        }
      />

      <TextField select size="small" label="Show" value={minScore} onChange={(e) => { setMinScore(Number(e.target.value)); setLimit(PAGE); }} sx={{ minWidth: 240, mb: 3 }}>
        {FILTERS.map((f) => (
          <MenuItem key={f.value} value={f.value}>
            {f.label}
          </MenuItem>
        ))}
      </TextField>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={reload}>Retry</Button>}>
          {error}
        </Alert>
      )}

      {loading && !data ? (
        <Stack spacing={2}>
          <Skeleton variant="rounded" height={130} />
          <Skeleton variant="rounded" height={130} />
        </Stack>
      ) : items.length === 0 && !error ? (
        <Box sx={{ textAlign: "center", py: 6 }}>
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            {minScore > 0 ? "No jobs reach that score. Try a lower filter." : "No scored jobs yet. Find or add some jobs first."}
          </Typography>
          {minScore === 0 && (
            <Button variant="contained" component={RouterLink} to="/job-search">
              Go to AI Job Search
            </Button>
          )}
        </Box>
      ) : (
        <>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
            Showing {items.length} of {data?.total ?? 0}, highest score first
          </Typography>
          <Stack spacing={2}>
            {items.map(({ match, job }) => (
              <JobCard
                key={job.id}
                job={{ ...job, match: { score: match.score, label: match.label } }}
                onOpen={() => setOpenId(job.id)}
                footer={
                  <Typography variant="caption" color="text.secondary">
                    {match.matched_skills?.length ?? 0} skill(s) matched, {match.missing_skills?.length ?? 0} missing
                  </Typography>
                }
              />
            ))}
          </Stack>
          {data && items.length < data.total && (
            <Box sx={{ textAlign: "center", mt: 3 }}>
              <Button onClick={() => setLimit((l) => l + PAGE)} disabled={loading}>
                Show more
              </Button>
            </Box>
          )}
        </>
      )}

      {openId && <JobDetailDialog jobId={openId} onClose={() => setOpenId(null)} onChanged={() => setRefreshKey((k) => k + 1)} />}

      <WeightsDialog
        open={weightsOpen}
        onClose={() => setWeightsOpen(false)}
        onSaved={() => {
          setWeightsOpen(false);
          setRefreshKey((k) => k + 1);
        }}
      />
    </>
  );
}
