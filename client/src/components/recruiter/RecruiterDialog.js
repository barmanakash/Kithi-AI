import { useEffect, useState } from "react";
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Grid, TextField } from "@mui/material";
import { recruitersApi } from "../../services/endpoints";
import { errorMessage } from "../../utils/format";

const EMPTY = { name: "", email: "", phone: "", company: "", title: "", linkedin_url: "", notes: "" };

/** Create or edit a recruiter contact. */
export default function RecruiterDialog({ open, recruiter, onClose, onSaved }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const editing = Boolean(recruiter);

  useEffect(() => {
    if (!open) return;
    setError("");
    setForm(
      recruiter
        ? {
            name: recruiter.name || "",
            email: recruiter.email || "",
            phone: recruiter.phone || "",
            company: recruiter.company || "",
            title: recruiter.title || "",
            linkedin_url: recruiter.linkedin_url || "",
            notes: recruiter.notes || "",
          }
        : EMPTY
    );
  }, [open, recruiter]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async () => {
    setSaving(true);
    setError("");
    const body = {
      name: form.name.trim(),
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      company: form.company.trim() || null,
      title: form.title.trim() || null,
      linkedin_url: form.linkedin_url.trim() || null,
      notes: form.notes,
    };
    try {
      const saved = editing ? await recruitersApi.update(recruiter.id, body) : await recruitersApi.create(body);
      onSaved(saved, editing);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{editing ? "Edit contact" : "New recruiter contact"}</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Grid container spacing={2}>
          <Grid item xs={12}><TextField label="Name" value={form.name} onChange={set("name")} required fullWidth inputProps={{ maxLength: 120 }} /></Grid>
          <Grid item xs={12} sm={6}><TextField label="Company" value={form.company} onChange={set("company")} fullWidth inputProps={{ maxLength: 200 }} /></Grid>
          <Grid item xs={12} sm={6}><TextField label="Job title" value={form.title} onChange={set("title")} fullWidth inputProps={{ maxLength: 150 }} /></Grid>
          <Grid item xs={12} sm={6}><TextField label="Email" value={form.email} onChange={set("email")} fullWidth /></Grid>
          <Grid item xs={12} sm={6}><TextField label="Phone" value={form.phone} onChange={set("phone")} fullWidth inputProps={{ maxLength: 30 }} /></Grid>
          <Grid item xs={12}><TextField label="LinkedIn URL" value={form.linkedin_url} onChange={set("linkedin_url")} fullWidth placeholder="https://" /></Grid>
          <Grid item xs={12}><TextField label="Notes" value={form.notes} onChange={set("notes")} fullWidth multiline minRows={2} maxRows={6} inputProps={{ maxLength: 2000 }} /></Grid>
        </Grid>
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button color="inherit" onClick={onClose} disabled={saving}>Cancel</Button>
        <Button variant="contained" onClick={submit} disabled={saving || !form.name.trim()}>{saving ? "Saving..." : editing ? "Save changes" : "Add contact"}</Button>
      </DialogActions>
    </Dialog>
  );
}
