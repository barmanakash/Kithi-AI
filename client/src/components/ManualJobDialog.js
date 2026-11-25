import { useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Grid,
  MenuItem,
  Switch,
  TextField,
} from "@mui/material";
import { jobsApi } from "../services/endpoints";
import { errorMessage } from "../utils/format";
import { JOB_TYPES } from "../utils/statuses";

const EMPTY = { title: "", company: "", location: "", remote: false, job_type: "", url: "", salary_text: "", description: "" };

/** Add a job by pasting its description. Useful for sites that are not permitted discovery sources. */
export default function ManualJobDialog({ open, onClose, onSaved }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const close = () => {
    if (saving) return;
    setForm(EMPTY);
    setError("");
    onClose();
  };

  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      const body = {
        title: form.title,
        company: form.company,
        description: form.description,
        remote: form.remote,
        location: form.location || null,
        job_type: form.job_type || null,
        url: form.url || null,
        salary_text: form.salary_text || null,
      };
      const result = await jobsApi.add(body);
      setForm(EMPTY);
      onSaved(result);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={close} maxWidth="md" fullWidth>
      <DialogTitle>Add a job manually</DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <Grid container spacing={2} sx={{ mt: 0 }}>
          <Grid item xs={12} sm={6}>
            <TextField label="Job title" value={form.title} onChange={set("title")} required fullWidth inputProps={{ maxLength: 200 }} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField label="Company" value={form.company} onChange={set("company")} required fullWidth inputProps={{ maxLength: 200 }} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField label="Location" value={form.location} onChange={set("location")} fullWidth inputProps={{ maxLength: 200 }} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField select label="Job type" value={form.job_type} onChange={set("job_type")} fullWidth>
              <MenuItem value="">Not specified</MenuItem>
              {JOB_TYPES.map((t) => (
                <MenuItem key={t.value} value={t.value}>
                  {t.label}
                </MenuItem>
              ))}
            </TextField>
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField label="Posting URL (optional)" value={form.url} onChange={set("url")} fullWidth placeholder="https://" />
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField label="Salary (optional)" value={form.salary_text} onChange={set("salary_text")} fullWidth inputProps={{ maxLength: 100 }} />
          </Grid>
          <Grid item xs={12} sm={2}>
            <FormControlLabel control={<Switch checked={form.remote} onChange={(e) => setForm((f) => ({ ...f, remote: e.target.checked }))} />} label="Remote" />
          </Grid>
          <Grid item xs={12}>
            <TextField
              label="Job description"
              value={form.description}
              onChange={set("description")}
              required
              fullWidth
              multiline
              minRows={8}
              maxRows={16}
              helperText="Paste the full description. It is treated as untrusted text and checked for scam and injection signals."
            />
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={close} color="inherit" disabled={saving}>
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={saving || !form.title.trim() || !form.company.trim() || form.description.trim().length < 20}>
          {saving ? "Saving..." : "Save job"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
