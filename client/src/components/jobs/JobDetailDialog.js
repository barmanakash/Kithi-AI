import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  LinearProgress,
  Link,
  Stack,
  Typography,
} from "@mui/material";
import OpenInNew from "@mui/icons-material/OpenInNew";
import ConfirmDialog from "../ConfirmDialog";
import ScamReport, { InjectionAlert, ScamChip } from "./ScamReport";
import { MatchChip } from "./JobCard";
import { useToast } from "../../context/ToastContext";
import { jobsApi, scamApi } from "../../services/endpoints";
import { errorMessage, formatDateTime } from "../../utils/format";
import { SOURCE_LABELS, safeHref } from "../../utils/jobs";

function Section({ title, children }) {
  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>
        {title}
      </Typography>
      {children}
    </Box>
  );
}

export default function JobDetailDialog({ jobId, onClose, onChanged }) {
  const toast = useToast();
  const [state, setState] = useState({ loading: true, error: "", job: null, match: null });
  const [busy, setBusy] = useState("");
  const [scam, setScam] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: "" }));
    try {
      const res = await jobsApi.get(jobId);
      setState({ loading: false, error: "", job: res.job, match: res.match });
    } catch (err) {
      setState({ loading: false, error: errorMessage(err), job: null, match: null });
    }
  }, [jobId]);

  useEffect(() => {
    setScam(null);
    load();
  }, [load]);

  const { job, match } = state;
  const href = safeHref(job?.url);

  const run = async (name, fn) => {
    setBusy(name);
    try {
      await fn();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy("");
    }
  };

  const rescore = () =>
    run("rescore", async () => {
      await jobsApi.rescore(jobId);
      await load();
      onChanged?.();
      toast.success("Match score updated");
    });

  const explain = () =>
    run("explain", async () => {
      const res = await jobsApi.explain(jobId);
      if (res.explanation) {
        setState((s) => ({ ...s, match: { ...s.match, explanation: res.explanation } }));
      } else {
        toast.warning(`The local AI could not write an explanation: ${res.ai_error || "unknown error"}`);
      }
    });

  const checkScam = () =>
    run("scam", async () => {
      setScam(await scamApi.assessJob(jobId));
    });

  const remove = () =>
    run("delete", async () => {
      await jobsApi.remove(jobId);
      toast.success("Job deleted");
      setConfirmDelete(false);
      onChanged?.();
      onClose();
    });

  return (
    <Dialog open onClose={onClose} maxWidth="md" fullWidth scroll="paper">
      <DialogTitle>
        {state.loading && !job ? "Loading..." : job ? job.title : "Job"}
        {job && (
          <Typography variant="body2" color="text.secondary">
            {job.company}
            {job.location ? ` - ${job.location}` : ""}
          </Typography>
        )}
      </DialogTitle>
      <DialogContent dividers>
        {state.loading && !job && (
          <Box sx={{ display: "grid", placeItems: "center", py: 6 }}>
            <CircularProgress />
          </Box>
        )}
        {state.error && <Alert severity="error">{state.error}</Alert>}

        {job && (
          <>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
              <MatchChip match={match ? { score: match.score, label: match.label } : null} />
              {job.scam_level && <ScamChip level={job.scam_level} score={job.scam_score} />}
              {job.remote && <Chip size="small" variant="outlined" label="Remote" />}
              {job.job_type && <Chip size="small" variant="outlined" label={job.job_type.replace(/_/g, " ")} />}
              {job.salary_text && <Chip size="small" variant="outlined" label={job.salary_text} />}
              <Chip size="small" variant="outlined" label={SOURCE_LABELS[job.source] || job.source} />
            </Stack>

            <InjectionAlert flags={job.injection_flags} />

            {match ? (
              <>
                <Section title="Why this score">
                  {match.score == null ? (
                    <Alert severity="info">{match.notes?.[0] || "Not enough data to calculate a score."}</Alert>
                  ) : (
                    <Stack spacing={2}>
                      {match.components.map((c) => (
                        <Box key={c.key}>
                          <Stack direction="row" justifyContent="space-between">
                            <Typography variant="body2" fontWeight={600}>
                              {c.label} <Typography component="span" variant="caption" color="text.secondary">(weight {c.weight})</Typography>
                            </Typography>
                            <Typography variant="body2">{c.score_percent == null ? "Not scored" : `${c.score_percent}%`}</Typography>
                          </Stack>
                          <LinearProgress
                            variant="determinate"
                            value={c.score_percent ?? 0}
                            color={c.score_percent == null ? "inherit" : c.score_percent >= 70 ? "success" : c.score_percent >= 40 ? "warning" : "error"}
                            sx={{ height: 6, borderRadius: 3, my: 0.5, opacity: c.score_percent == null ? 0.3 : 1 }}
                          />
                          <Typography variant="caption" color="text.secondary">
                            {c.detail}
                          </Typography>
                        </Box>
                      ))}
                      {match.notes?.map((n) => (
                        <Typography key={n} variant="caption" color="text.secondary">
                          {n}
                        </Typography>
                      ))}
                    </Stack>
                  )}
                </Section>

                {(match.matched_skills?.length > 0 || match.missing_skills?.length > 0) && (
                  <Section title="Skills">
                    {match.matched_skills?.length > 0 && (
                      <>
                        <Typography variant="caption" color="text.secondary">
                          You have
                        </Typography>
                        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 1.5, mt: 0.5 }}>
                          {match.matched_skills.map((s) => (
                            <Chip key={s.skill} size="small" color="success" variant="outlined" label={s.optional ? `${s.skill} (nice to have)` : s.skill} title={`Job: ${s.job_evidence}\nYours: from ${s.candidate_source}`} />
                          ))}
                        </Stack>
                      </>
                    )}
                    {match.missing_skills?.length > 0 && (
                      <>
                        <Typography variant="caption" color="text.secondary">
                          Not found in your profile or resume
                        </Typography>
                        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mt: 0.5 }}>
                          {match.missing_skills.map((s) => (
                            <Chip key={s.skill} size="small" color="warning" variant="outlined" label={s.optional ? `${s.skill} (nice to have)` : s.skill} title={`Job: ${s.job_evidence}`} />
                          ))}
                        </Stack>
                        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                          Only list a skill on your profile if you genuinely have it.
                        </Typography>
                      </>
                    )}
                  </Section>
                )}

                <Section title="AI explanation">
                  {match.explanation ? (
                    <Typography variant="body2">{match.explanation}</Typography>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Optional. The local model writes a short summary using only the facts above.
                    </Typography>
                  )}
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
                    Scored {formatDateTime(match.computed_at)}
                  </Typography>
                </Section>
                <Divider sx={{ mb: 3 }} />
              </>
            ) : (
              <Alert severity="info" sx={{ mb: 3 }}>
                This job has not been scored yet.
              </Alert>
            )}

            {scam && (
              <Section title="Scam check">
                <ScamReport report={scam} />
              </Section>
            )}

            <Section title="Job description">
              <Box sx={{ whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 14, color: "text.secondary", maxHeight: 360, overflow: "auto" }}>
                {job.description}
              </Box>
            </Section>
          </>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2, flexWrap: "wrap", gap: 1 }}>
        <Button color="error" onClick={() => setConfirmDelete(true)} disabled={!job || Boolean(busy)} sx={{ mr: "auto" }}>
          Delete
        </Button>
        {href && (
          <Button component={Link} href={href} target="_blank" rel="noopener noreferrer" endIcon={<OpenInNew fontSize="small" />} underline="none">
            Open posting
          </Button>
        )}
        <Button onClick={checkScam} disabled={!job || Boolean(busy)}>
          {busy === "scam" ? "Checking..." : "Scam check"}
        </Button>
        <Button onClick={rescore} disabled={!job || Boolean(busy)}>
          {busy === "rescore" ? "Scoring..." : "Re-score"}
        </Button>
        <Button onClick={explain} disabled={!job || !match || match.score == null || Boolean(busy)}>
          {busy === "explain" ? "Writing..." : "Explain with AI"}
        </Button>
        <Button variant="contained" onClick={onClose}>
          Close
        </Button>
      </DialogActions>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this job?"
        message="The job, its match score and any scam assessments for it will be removed."
        confirmLabel="Delete"
        loading={busy === "delete"}
        onConfirm={remove}
        onClose={() => setConfirmDelete(false)}
      />
    </Dialog>
  );
}
