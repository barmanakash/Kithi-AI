import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Grid,
  MenuItem,
  TextField,
  Typography,
} from "@mui/material";
import useApi from "../hooks/useApi";
import { applicationsApi, generateApi } from "../services/endpoints";
import { errorMessage } from "../utils/format";
import { APPLICATION_STATUSES, statusLabel } from "../utils/statuses";

/** Accept "example.com" as well as "https://example.com"; empty stays empty. */
const withScheme = (value) => {
  const t = (value || "").trim();
  if (!t) return null;
  return /^https?:\/\//i.test(t) ? t : `https://${t}`;
};

const EMPTY = {
  company: "",
  job_title: "",
  job_url: "",
  status: "saved",
  confirmed: false,
  application_date: "",
  follow_up_date: "",
  resume_version_id: "",
  cover_letter_version_id: "",
  rec_name: "",
  rec_email: "",
  rec_phone: "",
  rec_linkedin: "",
  notes: "",
};

function fromApplication(app) {
  const rec = app.recruiter || {};
  return {
    company: app.company || "",
    job_title: app.job_title || "",
    job_url: app.job_url || "",
    status: app.status || "saved",
    confirmed: false,
    application_date: app.application_date || "",
    follow_up_date: app.follow_up_date || "",
    resume_version_id: app.resume_version_id || "",
    cover_letter_version_id: app.cover_letter_version_id || "",
    rec_name: rec.name || "",
    rec_email: rec.email || "",
    rec_phone: rec.phone || "",
    rec_linkedin: rec.linkedin_url || "",
    notes: app.notes || "",
  };
}

/**
 * Create or edit an application. Kithi only records what you enter; it never submits anything.
 * Status is chosen when creating. Afterwards it changes through the board so every change is recorded in the history.
 */
export default function ApplicationDialog({ open, application, onClose, onSaved }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const editing = Boolean(application);
  const versions = useApi(() => (open ? generateApi.list({ limit: 100 }) : Promise.resolve(null)), [open]);

  useEffect(() => {
    if (open) {
      setForm(application ? fromApplication(application) : EMPTY);
      setError("");
    }
  }, [open, application]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const all = versions.data?.versions || [];
  const resumes = all.filter((v) => v.kind === "tailored_resume");
  const letters = all.filter((v) => v.kind === "cover_letter");
  const needsConfirm = !editing && form.status === "applied";

  const submit = async () => {
    setSaving(true);
    setError("");
    const recruiter = {
      name: form.rec_name.trim() || null,
      email: form.rec_email.trim() || null,
      phone: form.rec_phone.trim() || null,
      linkedin_url: withScheme(form.rec_linkedin),
    };
    const shared = {
      company: form.company.trim(),
      job_title: form.job_title.trim(),
      job_url: withScheme(form.job_url),
      application_date: form.application_date || null,
      follow_up_date: form.follow_up_date || null,
      resume_version_id: form.resume_version_id || null,
      cover_letter_version_id: form.cover_letter_version_id || null,
      recruiter: Object.values(recruiter).some(Boolean) ? recruiter : null,
      notes: form.notes,
    };
    try {
      const saved = editing
        ? await applicationsApi.update(application.id, shared)
        : await applicationsApi.create({ ...shared, status: form.status, confirmed_by_user: form.confirmed });
      onSaved(saved, editing);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} maxWidth="md" fullWidth>
      <DialogTitle>{editing ? "Edit application" : "New application"}</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <TextField label="Company" value={form.company} onChange={set("company")} required fullWidth inputProps={{ maxLength: 200 }} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField label="Job title" value={form.job_title} onChange={set("job_title")} required fullWidth inputProps={{ maxLength: 200 }} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField label="Job URL" value={form.job_url} onChange={set("job_url")} fullWidth placeholder="https://" />
          </Grid>
          <Grid item xs={12} sm={6}>
            {editing ? (
              <TextField label="Status" value={statusLabel(form.status)} fullWidth disabled helperText="Change status from the board or table so it is recorded in the history." />
            ) : (
              <TextField select label="Status" value={form.status} onChange={set("status")} fullWidth>
                {APPLICATION_STATUSES.map((s) => <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>)}
              </TextField>
            )}
          </Grid>
          {needsConfirm && (
            <Grid item xs={12}>
              <Alert severity="info">
                <FormControlLabel
                  control={<Checkbox checked={form.confirmed} onChange={(e) => setForm((f) => ({ ...f, confirmed: e.target.checked }))} />}
                  label="I submitted this application myself. Kithi never submits applications for you."
                />
              </Alert>
            </Grid>
          )}
          <Grid item xs={6} sm={3}>
            <TextField type="date" label="Application date" value={form.application_date} onChange={set("application_date")} fullWidth InputLabelProps={{ shrink: true }} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <TextField type="date" label="Follow-up date" value={form.follow_up_date} onChange={set("follow_up_date")} fullWidth InputLabelProps={{ shrink: true }} />
          </Grid>
          <Grid item xs={12} sm={3}>
            <TextField select label="Tailored resume" value={form.resume_version_id} onChange={set("resume_version_id")} fullWidth helperText={resumes.length ? "" : "None generated yet"}>
              <MenuItem value="">None attached</MenuItem>
              {resumes.map((v) => <MenuItem key={v.id} value={v.id}>{v.title}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid item xs={12} sm={3}>
            <TextField select label="Cover letter" value={form.cover_letter_version_id} onChange={set("cover_letter_version_id")} fullWidth helperText={letters.length ? "" : "None generated yet"}>
              <MenuItem value="">None attached</MenuItem>
              {letters.map((v) => <MenuItem key={v.id} value={v.id}>{v.title}</MenuItem>)}
            </TextField>
          </Grid>

          <Grid item xs={12}><Divider><Typography variant="caption" color="text.secondary">Recruiter (optional)</Typography></Divider></Grid>
          <Grid item xs={12} sm={6} md={3}><TextField label="Name" value={form.rec_name} onChange={set("rec_name")} fullWidth inputProps={{ maxLength: 120 }} /></Grid>
          <Grid item xs={12} sm={6} md={3}><TextField label="Email" value={form.rec_email} onChange={set("rec_email")} fullWidth /></Grid>
          <Grid item xs={12} sm={6} md={3}><TextField label="Phone" value={form.rec_phone} onChange={set("rec_phone")} fullWidth inputProps={{ maxLength: 30 }} /></Grid>
          <Grid item xs={12} sm={6} md={3}><TextField label="LinkedIn URL" value={form.rec_linkedin} onChange={set("rec_linkedin")} fullWidth /></Grid>

          <Grid item xs={12}>
            <TextField label="Notes" value={form.notes} onChange={set("notes")} fullWidth multiline minRows={2} maxRows={6} inputProps={{ maxLength: 5000 }} />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button color="inherit" onClick={onClose} disabled={saving}>Cancel</Button>
        <Button variant="contained" onClick={submit} disabled={saving || !form.company.trim() || !form.job_title.trim() || (needsConfirm && !form.confirmed)}>
          {saving ? "Saving..." : editing ? "Save changes" : "Create"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
