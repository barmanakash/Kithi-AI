import { useEffect, useState } from "react";
import { Alert, Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Grid, MenuItem, TextField, Typography } from "@mui/material";
import useApi from "../../hooks/useApi";
import { applicationsApi, jobsApi, recruiterMessagesApi, recruitersApi } from "../../services/endpoints";
import { errorMessage } from "../../utils/format";

export const KIND_LABELS = {
  outreach: "Introduce myself / express interest",
  referral: "Ask for a referral",
  follow_up: "Follow up on an application",
  thank_you: "Thank you after an interview",
  reply: "Reply to a message I received",
};

const BASE = { kind: "outreach", channel: "email", tone: "professional", recruiter_id: "", job_id: "", application_id: "", incoming_message: "", note: "" };

function missingContext(f) {
  if (f.kind === "reply" && f.incoming_message.trim().length < 1) return "Paste the message you received.";
  if (f.kind === "follow_up" && !f.application_id && !f.job_id) return "Choose the application or job you are following up on.";
  if ((f.kind === "referral" || f.kind === "thank_you") && !f.application_id && !f.job_id) return "Choose the job or application this message is about.";
  return "";
}

/** Draft a message with the local model. The result is always a draft: nothing is approved or sent. */
export default function GenerateMessageDialog({ open, initial, onClose, onCreated }) {
  const [form, setForm] = useState(BASE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const recruiters = useApi(() => (open ? recruitersApi.list({ limit: 200 }) : Promise.resolve(null)), [open]);
  const jobs = useApi(() => (open ? jobsApi.list({ limit: 100 }) : Promise.resolve(null)), [open]);
  const applications = useApi(() => (open ? applicationsApi.list({ limit: 200 }) : Promise.resolve(null)), [open]);

  useEffect(() => {
    if (open) {
      setForm({ ...BASE, ...(initial || {}) });
      setError("");
    }
  }, [open, initial]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const hint = missingContext(form);

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const body = {
        kind: form.kind,
        channel: form.channel,
        tone: form.tone,
        recruiter_id: form.recruiter_id || null,
        job_id: form.job_id || null,
        application_id: form.application_id || null,
        incoming_message: form.kind === "reply" ? form.incoming_message.trim() || null : null,
        note: form.note.trim() || null,
      };
      const res = await recruiterMessagesApi.generate(body);
      onCreated(res.message);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="md" fullWidth>
      <DialogTitle>Draft a message</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Alert severity="info" sx={{ mb: 2 }}>
          The draft uses only your verified profile. You review and edit it, and nothing is sent unless you approve it and send it yourself.
        </Alert>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <TextField select label="Purpose" value={form.kind} onChange={set("kind")} fullWidth>
              {Object.entries(KIND_LABELS).map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid item xs={6} sm={3}>
            <TextField select label="Channel" value={form.channel} onChange={set("channel")} fullWidth>
              <MenuItem value="email">Email</MenuItem>
              <MenuItem value="linkedin">LinkedIn</MenuItem>
            </TextField>
          </Grid>
          <Grid item xs={6} sm={3}>
            <TextField select label="Tone" value={form.tone} onChange={set("tone")} fullWidth>
              <MenuItem value="professional">Professional</MenuItem>
              <MenuItem value="warm">Warm</MenuItem>
              <MenuItem value="concise">Concise</MenuItem>
            </TextField>
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField select label="To (recruiter)" value={form.recruiter_id} onChange={set("recruiter_id")} fullWidth helperText={recruiters.data?.items?.length ? "" : "Add contacts in the Contacts tab"}>
              <MenuItem value="">No one selected</MenuItem>
              {(recruiters.data?.items || []).map((r) => <MenuItem key={r.id} value={r.id}>{r.name}{r.company ? ` (${r.company})` : ""}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField select label="About a job" value={form.job_id} onChange={set("job_id")} fullWidth>
              <MenuItem value="">None</MenuItem>
              {(jobs.data?.items || []).map((j) => <MenuItem key={j.id} value={j.id}>{j.title} - {j.company}</MenuItem>)}
            </TextField>
          </Grid>
          <Grid item xs={12} sm={4}>
            <TextField select label="Or an application" value={form.application_id} onChange={set("application_id")} fullWidth>
              <MenuItem value="">None</MenuItem>
              {(applications.data?.items || []).map((a) => <MenuItem key={a.id} value={a.id}>{a.job_title} - {a.company}</MenuItem>)}
            </TextField>
          </Grid>
          {form.kind === "reply" && (
            <Grid item xs={12}>
              <TextField
                label="Message you received"
                value={form.incoming_message}
                onChange={set("incoming_message")}
                fullWidth
                multiline
                minRows={4}
                maxRows={10}
                inputProps={{ maxLength: 4000 }}
                helperText="Treated as untrusted text. Kithi will not follow instructions in it or repeat times or numbers from it."
              />
            </Grid>
          )}
          <Grid item xs={12}>
            <TextField label="Anything specific to include (optional)" value={form.note} onChange={set("note")} fullWidth multiline minRows={2} maxRows={4} inputProps={{ maxLength: 500 }} helperText="Your own facts only, for example 'I am available for calls on weekday mornings'." />
          </Grid>
        </Grid>
        {busy && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mt: 2 }}>
            <CircularProgress size={20} />
            <Typography variant="body2" color="text.secondary">The local model is writing. On modest hardware this can take a minute.</Typography>
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        {hint && <Typography variant="caption" color="text.secondary" sx={{ mr: "auto" }}>{hint}</Typography>}
        <Button color="inherit" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button variant="contained" onClick={submit} disabled={busy || Boolean(hint)}>{busy ? "Drafting..." : "Draft message"}</Button>
      </DialogActions>
    </Dialog>
  );
}
