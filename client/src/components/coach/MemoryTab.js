import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Grid,
  IconButton,
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
import { careerApi, memoryApi } from "../../services/endpoints";
import { errorMessage, formatDate } from "../../utils/format";

function Row({ primary, secondary, chip, onDelete }) {
  return (
    <Stack direction="row" alignItems="center" spacing={1} sx={{ py: 0.75, borderBottom: 1, borderColor: "divider" }}>
      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Typography variant="body2" fontWeight={600} noWrap>{primary}</Typography>
        {secondary && <Typography variant="caption" color="text.secondary">{secondary}</Typography>}
      </Box>
      {chip}
      {onDelete && (
        <Tooltip title="Delete">
          <IconButton size="small" color="error" aria-label="Delete" onClick={onDelete}><DeleteOutline fontSize="small" /></IconButton>
        </Tooltip>
      )}
    </Stack>
  );
}

function Section({ title, subheader, empty, children, count }) {
  return (
    <Card sx={{ height: "100%" }}>
      <CardHeader title={title} subheader={subheader} />
      <CardContent sx={{ pt: 0 }}>{count === 0 ? <Typography color="text.secondary">{empty}</Typography> : children}</CardContent>
    </Card>
  );
}

function AddGoal({ onAdded }) {
  const toast = useToast();
  const [form, setForm] = useState({ kind: "goal", text: "" });
  const add = async (event) => {
    event.preventDefault();
    try {
      await careerApi.createGoal({ kind: form.kind, text: form.text.trim() });
      setForm({ ...form, text: "" });
      onAdded();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };
  return (
    <form onSubmit={add}>
      <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
        <TextField select size="small" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} sx={{ minWidth: 150 }}>
          <MenuItem value="goal">Career goal</MenuItem>
          <MenuItem value="preferred_company">Preferred company</MenuItem>
        </TextField>
        <TextField size="small" fullWidth placeholder="e.g. Become a backend lead / Acme Corp" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} inputProps={{ maxLength: 300 }} />
        <Button type="submit" variant="outlined" disabled={!form.text.trim()}>Add</Button>
      </Stack>
    </form>
  );
}

function AddSkill({ onAdded }) {
  const toast = useToast();
  const [form, setForm] = useState({ skill: "", level: 3, kind: "learning" });
  const add = async (event) => {
    event.preventDefault();
    try {
      await careerApi.saveSkill({ skill: form.skill.trim(), level: Number(form.level), kind: form.kind });
      setForm({ ...form, skill: "" });
      onAdded();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };
  return (
    <form onSubmit={add}>
      <Stack direction="row" spacing={1} sx={{ mb: 1.5 }}>
        <TextField size="small" fullWidth placeholder="Skill, e.g. Docker" value={form.skill} onChange={(e) => setForm({ ...form, skill: e.target.value })} inputProps={{ maxLength: 60 }} />
        <TextField select size="small" value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })} sx={{ minWidth: 90 }} label="Level">
          {[1, 2, 3, 4, 5].map((n) => <MenuItem key={n} value={n}>{n}/5</MenuItem>)}
        </TextField>
        <TextField select size="small" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} sx={{ minWidth: 120 }}>
          <MenuItem value="strength">Strength</MenuItem>
          <MenuItem value="gap">Gap</MenuItem>
          <MenuItem value="learning">Learning</MenuItem>
        </TextField>
        <Button type="submit" variant="outlined" disabled={!form.skill.trim()}>Save</Button>
      </Stack>
    </form>
  );
}

export default function MemoryTab() {
  const toast = useToast();
  const { data, loading, error, reload } = useApi(() => memoryApi.overview(), []);
  const [target, setTarget] = useState(null); // { section, id, label }
  const [deleting, setDeleting] = useState(false);

  const remove = async () => {
    setDeleting(true);
    try {
      await memoryApi.remove(target.section, target.id);
      toast.success("Deleted");
      setTarget(null);
      reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  };
  const ask = (section, id, label) => () => setTarget({ section, id, label });

  if (error) return <Alert severity="error">{error}</Alert>;
  if (loading && !data) return <Skeleton variant="rounded" height={200} />;

  const m = data;
  const skills = [...m.technical_strengths.self_assessed, ...m.skill_gaps.self_assessed, ...m.learning_progress.skills_being_learned];
  const apps = m.previous_applications;

  return (
    <>
      <Alert severity="info" sx={{ mb: 2.5 }}>
        This is everything Kithi remembers about your career. It stays on this computer. You can delete any item here.
        Your resume files and profile are managed in My Resume.
      </Alert>
      <Grid container spacing={2.5}>
        <Grid item xs={12} md={6}>
          <Section title="Career goals" subheader="Used by your coach and roadmaps" count={-1}>
            <AddGoal onAdded={reload} />
            {m.career_goals.length === 0 && <Typography color="text.secondary">No goals yet.</Typography>}
            {m.career_goals.map((g) => (
              <Row key={g.id} primary={g.text} secondary={`${g.status}${g.target_date ? ` · target ${g.target_date}` : ""}`} onDelete={ask("career_goals", g.id, g.text)} />
            ))}
            <Typography variant="subtitle2" sx={{ mt: 2 }}>Preferred companies</Typography>
            {m.preferred_companies.length === 0 && <Typography color="text.secondary" variant="body2">None yet. Add one above.</Typography>}
            {m.preferred_companies.map((g) => (
              <Row key={g.id} primary={g.text} onDelete={ask("career_goals", g.id, g.text)} />
            ))}
          </Section>
        </Grid>
        <Grid item xs={12} md={6}>
          <Section title="Skills you rated" subheader="Your own honest ratings, plus ones from interview practice" count={-1}>
            <AddSkill onAdded={reload} />
            {skills.length === 0 && <Typography color="text.secondary">No skills rated yet.</Typography>}
            {skills.map((s) => (
              <Row key={s.id} primary={s.skill} secondary={`${s.level}/5 · ${s.source === "interview" ? "from interview practice" : "your rating"}`} chip={<Chip size="small" variant="outlined" label={s.kind} />} onDelete={ask("skill_assessments", s.id, s.skill)} />
            ))}
          </Section>
        </Grid>
        <Grid item xs={12} md={6}>
          <Section title="Learning plans" empty="No learning plans yet." count={m.learning_progress.plans.length}>
            {m.learning_progress.plans.map((p) => (
              <Row key={p.id} primary={p.title} secondary={`${p.done}/${p.total} milestones`} onDelete={ask("learning_plans", p.id, p.title)} />
            ))}
          </Section>
        </Grid>
        <Grid item xs={12} md={6}>
          <Section title="Interview feedback" empty="No completed interview sessions yet." count={m.interview_feedback.length}>
            {m.interview_feedback.map((f) => (
              <Row key={f.id} primary={f.title || "Interview"} secondary={formatDate(f.created_at)} chip={<Chip size="small" label={`${f.overall_score}/10`} />} onDelete={ask("interview_feedback", f.id, f.title || "this feedback")} />
            ))}
          </Section>
        </Grid>
        <Grid item xs={12} md={6}>
          <Section title="Generated resumes and letters" empty="Nothing generated yet." count={m.resume_versions.length}>
            {m.resume_versions.map((v) => (
              <Row key={v.id} primary={v.title || v.job_title || v.kind || "Version"} secondary={`${v.company || ""} ${formatDate(v.created_at)}`.trim()} onDelete={ask("resume_versions", v.id, v.title || "this version")} />
            ))}
          </Section>
        </Grid>
        <Grid item xs={12} md={6}>
          <Section title="Applications" subheader="Manage these in the Applications page" empty="No applications yet." count={apps.total}>
            <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1, mb: 1 }}>
              {Object.entries(apps.by_status).map(([status, n]) => <Chip key={status} size="small" label={`${status.replace(/_/g, " ")}: ${n}`} />)}
            </Stack>
            {apps.recent.slice(0, 5).map((a) => <Row key={a.id} primary={`${a.job_title} - ${a.company}`} secondary={a.status.replace(/_/g, " ")} />)}
          </Section>
        </Grid>
      </Grid>

      <ConfirmDialog
        open={Boolean(target)}
        title="Delete this item?"
        message={target ? `"${target.label}" will be permanently removed from your career memory.` : ""}
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={remove}
        onClose={() => setTarget(null)}
      />
    </>
  );
}
