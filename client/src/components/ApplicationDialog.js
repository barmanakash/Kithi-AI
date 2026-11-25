import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  MenuItem,
  TextField,
  Typography,
} from "@mui/material";
import { applicationsApi } from "../services/endpoints";
import { errorMessage } from "../utils/format";
import { APPLICATION_STATUSES } from "../utils/statuses";

const EMPTY = {
  company: "",
  job_title: "",
  job_url: "",
  status: "saved",
  resume_id: "",
  application_date: "",
  follow_up_date: "",
  rec_name: "",
  rec_email: "",
  rec_phone: "",
  rec_linkedin: "",
  cover_note: "",
  notes: "",
};

function fromApplication(app) {
  const rec = app.recruiter || {};
  return {
    company: app.company || "",
    job_title: app.job_title || "",
    job_url: app.job_url || "",
    status: app.status || "saved",
    resume_id: app.resume_id || "",
    application_date: app.application_date || "",
    follow_up_date: app.follow_up_date || "",
    rec_name: rec.name || "",
    rec_email: rec.email || "",
    rec_phone: rec.phone || "",
    rec_linkedin: rec.linkedin_url || "",
    cover_note: app.cover_note || "",
    notes: app.notes || "",
  };
}

/** Create or edit an application. Kithi only records what you enter; it never submits anything. */
export default function ApplicationDialog({ open, application, resumes = [], onClose, onSaved }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const editing = Boolean(application);

  useEffect(() => {
    if (open) {
      setForm(application ? fromApplication(application) : EMPTY);
      setError("");
    }
  }, [open, application]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async () => {
    setSaving(true);
    setError("");
    const recruiter = {
      name: form.rec_name.trim() || null,
      email: form.rec_email.trim() || null,
      phone: form.rec_phone.trim() || null,
      linkedin_url: form.rec_linkedin.trim() || null,
    };
    const body = {
      company: form.company.trim(),
      job_title: form.job_title.trim(),
      job_url: form.job_url.trim() || null,
      status: form.status,
      resume_id: form.resume_id || null,
      application_date: form.application_date || null,
      follow_up_date: form.follow_up_date || null,
      recruiter: Object.values(recruiter).some(Boolean) ? recruiter : null,
      cover_note: form.cover_note,
      notes: form.notes,
    };
    try {
      const saved = editing ? await applicationsApi.update(application.id, body) : await applicationsApi.create(body);
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
            <TextField select label="Status" value={form.status} onChange={set("status")} fullWidth>
              {APPLICATION_STATUSES.map((s) => <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField select label="Resume version" value={form.resume_id} onChange={set("resume_id")} fullWidth>
              <MenuItem value="">None selected</MenuItem>
              {resumes.map((r) => <MenuItem key={r.id} value={r.id}>{r.original_filename}{r.is_primary ? " (primary)" : ""}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid item xs={6} sm={4}>
            <TextField type="date" label="Application date" value={form.application_date} onChange={set("application_date")} fullWidth InputLabelProps={{ shrink: true }} />
          </Grid>
          <Grid item xs={6} sm={4}>
            <TextField type="date" label="Follow-up date" value={form.follow_up_date} onChange={set("follow_up_date")} fullWidth InputLabelProps={{ shrink: true }} />
          </Grid>

          <Grid item xs={12}><Divider><Typography variant="caption" color="text.secondary">Recruiter (optional)</Typography></Divider></Grid>
          <Grid item xs={12} sm={6} md={3}><TextField label="Name" value={form.rec_name} onChange={set("rec_name")} fullWidth inputProps={{ maxLength: 150 }} /></Grid>
          <Grid item xs={12} sm={6} md={3}><TextField label="Email" value={form.rec_email} onChange={set("rec_email")} fullWidth /></Grid>
          <Grid item xs={12} sm={6} md={3}><TextField label="Phone" value={form.rec_phone} onChange={set("rec_phone")} fullWidth inputProps={{ maxLength: 30 }} /></Grid>
          <Grid item xs={12} sm={6} md={3}><TextField label="LinkedIn URL" value={form.rec_linkedin} onChange={set("rec_linkedin")} fullWidth /></Grid>

          <Grid item xs={12}>
            <TextField label="Cover note or application answers" value={form.cover_note} onChange={set("cover_note")} fullWidth multiline minRows={3} maxRows={8} inputProps={{ maxLength: 5000 }} />
          </Grid>
          <Grid item xs={12}>
            <TextField label="Notes" value={form.notes} onChange={set("notes")} fullWidth multiline minRows={2} maxRows={6} inputProps={{ maxLength: 5000 }} />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button color="inherit" onClick={onClose} disabled={saving}>Cancel</Button>
        <Button variant="contained" onClick={submit} disabled={saving || !form.company.trim() || !form.job_title.trim()}>
          {saving ? "Saving..." : editing ? "Save changes" : "Create"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
