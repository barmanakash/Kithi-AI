import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  LinearProgress,
  MenuItem,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import AutoAwesomeOutlined from "@mui/icons-material/AutoAwesomeOutlined";
import useApi from "../hooks/useApi";
import { generateApi, jobsApi } from "../services/endpoints";
import { errorMessage } from "../utils/format";

/**
 * Generate a tailored resume or a cover letter for one saved job.
 * `job` ({ id, title, company }) preselects the job; without it the user picks from their saved jobs.
 * Drafts are private and are never sent or attached anywhere automatically.
 */
export default function GenerateDialog({ open, job, onClose, onCreated }) {
  const [kind, setKind] = useState("tailored_resume");
  const [jobId, setJobId] = useState("");
  const [improve, setImprove] = useState(false);
  const [tone, setTone] = useState("professional");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const jobs = useApi(() => (open && !job ? jobsApi.list({ limit: 100 }) : Promise.resolve(null)), [open, job?.id]);

  useEffect(() => {
    if (open) {
      setJobId(job?.id || "");
      setError("");
    }
  }, [open, job?.id]);

  const jobList = jobs.data?.jobs || [];
  const selectedId = job?.id || jobId;

  const generate = async () => {
    setBusy(true);
    setError("");
    try {
      const res =
        kind === "tailored_resume"
          ? await generateApi.tailorResume({ job_id: selectedId, improve_bullets: improve })
          : await generateApi.coverLetter({ job_id: selectedId, tone });
      onCreated(res.version);
    } catch (err) {
      setError(errorMessage(err, "Could not generate the document"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Generate a document</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2.5}>
          <Alert severity="info">
            Only facts from your profile and resume are used. Anything the local AI writes is fact-checked, and sentences
            that add skills, numbers or claims you do not have are removed. Nothing is sent or submitted.
          </Alert>

          {job ? (
            <Typography variant="body2">
              For: <strong>{job.title}</strong> at {job.company}
            </Typography>
          ) : (
            <TextField
              select
              size="small"
              label="Saved job"
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              disabled={busy}
              helperText={jobs.error || (jobs.loading && !jobs.data ? "Loading your jobs..." : jobList.length ? "" : "Save a job in AI Job Search first.")}
              error={Boolean(jobs.error)}
            >
              {jobList.map((j) => (
                <MenuItem key={j.id} value={j.id}>
                  {j.title} - {j.company}
                </MenuItem>
              ))}
            </TextField>
          )}

          <ToggleButtonGroup exclusive fullWidth size="small" color="primary" value={kind} onChange={(_, v) => v && setKind(v)} disabled={busy}>
            <ToggleButton value="tailored_resume">Tailored resume</ToggleButton>
            <ToggleButton value="cover_letter">Cover letter</ToggleButton>
          </ToggleButtonGroup>

          {kind === "tailored_resume" ? (
            <Stack spacing={0.5}>
              <Typography variant="body2" color="text.secondary">
                Your skills, bullets and projects are reordered to match the job. The summary is written by the local AI and fact-checked.
              </Typography>
              <FormControlLabel
                control={<Checkbox checked={improve} onChange={(e) => setImprove(e.target.checked)} disabled={busy} />}
                label="Also reword my top bullets (slower; rewrites that add facts are rejected)"
              />
            </Stack>
          ) : (
            <TextField select size="small" label="Tone" value={tone} onChange={(e) => setTone(e.target.value)} disabled={busy}>
              <MenuItem value="professional">Professional</MenuItem>
              <MenuItem value="warm">Warm</MenuItem>
              <MenuItem value="concise">Concise</MenuItem>
            </TextField>
          )}

          {busy && (
            <Stack spacing={1}>
              <LinearProgress />
              <Typography variant="caption" color="text.secondary">
                The local model is writing. This can take a minute or two on modest hardware.
              </Typography>
            </Stack>
          )}
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} disabled={busy} color="inherit">
          Cancel
        </Button>
        <Button variant="contained" onClick={generate} disabled={busy || !selectedId} startIcon={<AutoAwesomeOutlined />}>
          {busy ? "Generating..." : "Generate draft"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
