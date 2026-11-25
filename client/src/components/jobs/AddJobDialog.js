import { useState } from "react";
import {
  Alert,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Grid,
  MenuItem,
  TextField,
} from "@mui/material";
import { jobsApi } from "../../services/endpoints";
import { errorMessage } from "../../utils/format";

const EMPTY = { title: "", company: "", location: "", remote: false, job_type: "", url: "", salary_text: "", description: "" };

const clean = (v) => {
  const t = v.trim();
  return t || null;
};

export default function AddJobDialog({ open, onClose, onCreated }) {
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const valid = form.title.trim() && form.company.trim() && form.description.trim().length >= 20;

  const close = () => {
    if (saving) return;
    setForm(EMPTY);
    setError("");
    onClose();
  };

  const submit = async () => {
    setError("");
    let url = clean(form.url);
    if (url && !/^https?:\/\//i.test(url)) url = `https://${url}`;
    setSaving(true);
    try {
      const res = await jobsApi.create({
        title: form.title.trim(),
        company: form.company.trim(),
        location: clean(form.location),
        remote: form.remote,
        job_type: clean(form.job_type),
        url,
        salary_text: clean(form.salary_text),
        description: form.description.trim(),
      });
      setForm(EMPTY);
      onCreated(res);
    } catch (err) {
      setError(errorMessage(err, "Could not save the job"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={close} maxWidth="md" fullWidth>
      <DialogTitle>Add a job manually</DialogTitle>
      <DialogContent dividers>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <Grid container spacing={2} sx={{ mt: 0 }}>
          <Grid item xs={12} md={6}>
            <TextField size="small" fullWidth required label="Job title" value={form.title} onChange={set("title")} inputProps={{ maxLength: 200 }} />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField size="small" fullWidth required label="Company" value={form.company} onChange={set("company")} inputProps={{ maxLength: 200 }} />
          </Grid>
          <Grid item xs={12} md={5}>
            <TextField size="small" fullWidth label="Location" value={form.location} onChange={set("location")} inputProps={{ maxLength: 200 }} />
          </Grid>
          <Grid item xs={6} md={3}>
            <TextField select size="small" fullWidth label="Job type" value={form.job_type} onChange={set("job_type")}>
              <MenuItem value="">Not specified</MenuItem>
              <MenuItem value="full_time">Full-time</MenuItem>
              <MenuItem value="part_time">Part-time</MenuItem>
              <MenuItem value="contract">Contract</MenuItem>
              <MenuItem value="internship">Internship</MenuItem>
            </TextField>
          </Grid>
          <Grid item xs={6} md={4}>
            <FormControlLabel control={<Checkbox checked={form.remote} onChange={(e) => setForm((f) => ({ ...f, remote: e.target.checked }))} />} label="Remote role" />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField size="small" fullWidth label="Posting URL" value={form.url} onChange={set("url")} />
          </Grid>
          <Grid item xs={12} md={6}>
            <TextField size="small" fullWidth label="Salary (as written)" value={form.salary_text} onChange={set("salary_text")} inputProps={{ maxLength: 100 }} />
          </Grid>
          <Grid item xs={12}>
            <TextField
              size="small"
              fullWidth
              required
              multiline
              minRows={8}
              maxRows={16}
              label="Job description"
              value={form.description}
              onChange={set("description")}
              inputProps={{ maxLength: 30000 }}
              helperText="Paste the full posting text. At least 20 characters. The more detail, the better the match."
            />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={close} color="inherit" disabled={saving}>
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={!valid || saving}>
          {saving ? "Saving..." : "Save and score"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
