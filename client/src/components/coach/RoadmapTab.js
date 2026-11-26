import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Checkbox,
  Chip,
  FormControlLabel,
  IconButton,
  LinearProgress,
  MenuItem,
  Skeleton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import ConfirmDialog from "../ConfirmDialog";
import useApi from "../../hooks/useApi";
import { useToast } from "../../context/ToastContext";
import { careerApi } from "../../services/endpoints";
import { errorMessage } from "../../utils/format";

function Gaps({ gaps }) {
  return (
    <Card>
      <CardHeader title="Skills your saved jobs ask for that you lack" subheader="Counted from your scored jobs, so every number traces to real listings." />
      <CardContent sx={{ pt: 0 }}>
        {gaps.error && <Alert severity="error">{gaps.error}</Alert>}
        {gaps.loading && !gaps.data ? (
          <Skeleton variant="rounded" height={60} />
        ) : gaps.data?.gaps?.length ? (
          <>
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1 }}>
              {gaps.data.gaps.map((g) => (
                <Chip key={g.skill} color="warning" variant="outlined" label={`${g.skill} · ${g.jobs_requiring} of ${gaps.data.jobs_analyzed} jobs${g.mostly_optional ? " (nice to have)" : ""}`} />
              ))}
            </Stack>
            {gaps.data.strengths?.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" color="success.main" sx={{ mb: 1 }}>Your strengths seen in those jobs</Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1 }}>
                  {gaps.data.strengths.slice(0, 10).map((s) => (
                    <Chip key={s.skill} size="small" color="success" variant="outlined" label={`${s.skill} · ${s.jobs_matching}`} />
                  ))}
                </Stack>
              </Box>
            )}
          </>
        ) : (
          <Typography color="text.secondary">{gaps.data?.note || "No skill gaps found across your saved jobs."}</Typography>
        )}
      </CardContent>
    </Card>
  );
}

function RoadmapForm({ gaps, onCreated }) {
  const toast = useToast();
  const [form, setForm] = useState({ target_role: "", weeks: 8, focus: "" });
  const [busy, setBusy] = useState(false);
  const noGaps = !gaps.data?.gaps?.length;

  const create = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const body = { weeks: Number(form.weeks) };
      if (form.target_role.trim()) body.target_role = form.target_role.trim();
      const focus = form.focus.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 10);
      if (focus.length) body.focus_skills = focus;
      await careerApi.createRoadmap(body);
      toast.success("Roadmap created");
      onCreated();
    } catch (err) {
      toast.error(errorMessage(err, "Could not create the roadmap"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader title="Build a learning roadmap" subheader="Your local model turns skill gaps into a week-by-week plan with portfolio project ideas." />
      <CardContent sx={{ pt: 0 }}>
        <form onSubmit={create}>
          <Stack spacing={2}>
            <TextField size="small" label="Target role (optional)" value={form.target_role} onChange={(e) => setForm({ ...form, target_role: e.target.value })} inputProps={{ maxLength: 100 }} />
            <Stack direction="row" spacing={2}>
              <TextField select size="small" label="Weeks" value={form.weeks} onChange={(e) => setForm({ ...form, weeks: e.target.value })} sx={{ minWidth: 110 }}>
                {[4, 6, 8, 12, 16].map((w) => <MenuItem key={w} value={w}>{w}</MenuItem>)}
              </TextField>
              <TextField size="small" fullWidth label="Focus skills (optional, comma separated)" value={form.focus} onChange={(e) => setForm({ ...form, focus: e.target.value })} helperText={noGaps ? "No gaps found yet, so type the skills you want to learn." : "Leave empty to use your top gaps."} />
            </Stack>
            {busy && (
              <Box>
                <LinearProgress />
                <Typography variant="caption" color="text.secondary">Writing your roadmap locally. This can take a minute or two.</Typography>
              </Box>
            )}
            <Box>
              <Button type="submit" variant="contained" disabled={busy || (noGaps && !form.focus.trim())}>
                {busy ? "Building..." : "Create roadmap"}
              </Button>
            </Box>
          </Stack>
        </form>
      </CardContent>
    </Card>
  );
}

function Plan({ plan, onChanged, onDelete }) {
  const toast = useToast();
  const toggle = async (index, done) => {
    try {
      await careerApi.updatePlanItem(plan.id, index, done);
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };
  const pct = plan.progress.total ? Math.round((100 * plan.progress.done) / plan.progress.total) : 0;

  return (
    <Card variant="outlined">
      <CardHeader
        title={plan.title}
        subheader={`${plan.progress.done} of ${plan.progress.total} milestones done`}
        action={
          <Tooltip title="Delete plan">
            <IconButton color="error" aria-label="Delete plan" onClick={() => onDelete(plan)}><DeleteOutline /></IconButton>
          </Tooltip>
        }
      />
      <CardContent sx={{ pt: 0 }}>
        <LinearProgress variant="determinate" value={pct} sx={{ mb: 2, height: 8, borderRadius: 4 }} />
        <Stack spacing={1.5}>
          {plan.items.map((item, index) => (
            <Box key={index}>
              <FormControlLabel
                control={<Checkbox checked={Boolean(item.done)} onChange={(e) => toggle(index, e.target.checked)} />}
                label={
                  <Typography variant="body2" fontWeight={600} sx={{ textDecoration: item.done ? "line-through" : "none" }}>
                    Week {item.week}: {item.title}
                  </Typography>
                }
              />
              <Box sx={{ pl: 4 }}>
                {item.tasks.map((t) => <Typography key={t} variant="body2" color="text.secondary">• {t}</Typography>)}
              </Box>
            </Box>
          ))}
        </Stack>
        {plan.portfolio_projects?.length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>Portfolio project ideas</Typography>
            {plan.portfolio_projects.map((p) => (
              <Typography key={p.name} variant="body2" sx={{ mb: 0.5 }}>
                <b>{p.name}</b>: {p.description} {p.skills?.length ? `(${p.skills.join(", ")})` : ""}
              </Typography>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

export default function RoadmapTab() {
  const toast = useToast();
  const gaps = useApi(() => careerApi.skillGaps(), []);
  const plans = useApi(() => careerApi.plans(), []);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const remove = async () => {
    setDeleting(true);
    try {
      await careerApi.removePlan(toDelete.id);
      toast.success("Plan deleted");
      setToDelete(null);
      plans.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Gaps gaps={gaps} />
      <RoadmapForm gaps={gaps} onCreated={plans.reload} />
      {plans.error && <Alert severity="error">{plans.error}</Alert>}
      {(plans.data?.plans || []).map((plan) => (
        <Plan key={plan.id} plan={plan} onChanged={plans.reload} onDelete={setToDelete} />
      ))}
      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this learning plan?"
        message="The plan and its progress will be removed."
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={remove}
        onClose={() => setToDelete(null)}
      />
    </Stack>
  );
}
