import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Checkbox,
  Collapse,
  FormControlLabel,
  Grid,
  IconButton,
  Skeleton,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import ExpandMore from "@mui/icons-material/ExpandMore";
import PageHeader from "../components/PageHeader";
import ScamReport, { ScamChip } from "../components/jobs/ScamReport";
import ConfirmDialog from "../components/ConfirmDialog";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { scamApi } from "../services/endpoints";
import { errorMessage, formatDateTime } from "../utils/format";

const EMPTY = { text: "", title: "", company: "", url: "", contact_email: "", save: true };
const clean = (v) => {
  const t = v.trim();
  return t || null;
};

function CheckForm({ onDone }) {
  const [form, setForm] = useState(EMPTY);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const valid = form.text.trim().length >= 20;

  const submit = async (event) => {
    event.preventDefault();
    if (!valid) return;
    setLoading(true);
    setError("");
    let url = clean(form.url);
    if (url && !/^https?:\/\//i.test(url)) url = `https://${url}`;
    try {
      const res = await scamApi.assess({
        text: form.text.trim(),
        title: clean(form.title),
        company: clean(form.company),
        url,
        contact_email: clean(form.contact_email),
        save: form.save,
      });
      setReport(res);
      if (form.save) onDone();
    } catch (err) {
      setError(errorMessage(err, "The check failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Grid container spacing={2.5}>
      <Grid item xs={12} lg={6}>
        <Card>
          <CardHeader title="Check a job listing or message" subheader="Paste the text of a posting, recruiter email or chat. Nothing is sent anywhere." />
          <CardContent sx={{ pt: 0 }}>
            <form onSubmit={submit}>
              <Stack spacing={2}>
                {error && <Alert severity="error">{error}</Alert>}
                <TextField
                  size="small"
                  required
                  multiline
                  minRows={8}
                  maxRows={16}
                  label="Listing or message text"
                  value={form.text}
                  onChange={set("text")}
                  inputProps={{ maxLength: 30000 }}
                  helperText="At least 20 characters."
                />
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <TextField size="small" fullWidth label="Job title (optional)" value={form.title} onChange={set("title")} inputProps={{ maxLength: 200 }} />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField size="small" fullWidth label="Company (optional)" value={form.company} onChange={set("company")} inputProps={{ maxLength: 200 }} helperText="Used to compare against email domains" />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField size="small" fullWidth label="Posting URL (optional)" value={form.url} onChange={set("url")} />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField size="small" fullWidth label="Contact email (optional)" type="email" value={form.contact_email} onChange={set("contact_email")} />
                  </Grid>
                </Grid>
                <FormControlLabel control={<Checkbox checked={form.save} onChange={(e) => setForm((f) => ({ ...f, save: e.target.checked }))} />} label="Save this check to my history" />
                <Box>
                  <Button type="submit" variant="contained" disabled={!valid || loading}>
                    {loading ? "Checking..." : "Run check"}
                  </Button>
                </Box>
              </Stack>
            </form>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} lg={6}>
        <Card sx={{ height: "100%" }}>
          <CardHeader title="Result" />
          <CardContent sx={{ pt: 0 }}>
            {report ? (
              <ScamReport report={report} />
            ) : (
              <Typography color="text.secondary">
                The result lists each warning signal with the exact text that triggered it. It reports a concern level, never a verdict.
              </Typography>
            )}
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
}

function History({ refreshKey }) {
  const toast = useToast();
  const { data, loading, error, reload } = useApi(() => scamApi.list({ limit: 50 }), [refreshKey]);
  const [expanded, setExpanded] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const items = data?.items || [];

  const remove = async () => {
    setDeleting(true);
    try {
      await scamApi.remove(toDelete.id);
      toast.success("Check deleted");
      setToDelete(null);
      reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Card sx={{ mt: 3 }}>
      <CardHeader title="History" subheader="Your saved checks, newest first" />
      <CardContent sx={{ pt: 0 }}>
        {error && <Alert severity="error">{error}</Alert>}
        {loading && !data ? (
          <Skeleton variant="rounded" height={60} />
        ) : items.length === 0 && !error ? (
          <Typography color="text.secondary">No saved checks yet.</Typography>
        ) : (
          <Stack spacing={1.5}>
            {items.map((item) => (
              <Box key={item.id} sx={{ border: 1, borderColor: "divider", borderRadius: 2 }}>
                <Stack direction="row" alignItems="center" spacing={1} sx={{ p: 1.5 }}>
                  <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                    <Typography variant="body2" fontWeight={600} noWrap>
                      {item.title || item.company || "Pasted text"}
                      {item.title && item.company ? ` - ${item.company}` : ""}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDateTime(item.created_at)}
                    </Typography>
                  </Box>
                  <ScamChip level={item.result?.risk_level} score={item.result?.concern_score} />
                  <Tooltip title="Details">
                    <IconButton size="small" onClick={() => setExpanded(expanded === item.id ? null : item.id)} aria-label="Toggle details" sx={{ transform: expanded === item.id ? "rotate(180deg)" : "none" }}>
                      <ExpandMore />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton size="small" color="error" onClick={() => setToDelete(item)} aria-label="Delete check">
                      <DeleteOutline fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Stack>
                <Collapse in={expanded === item.id} unmountOnExit>
                  <Box sx={{ p: 2, pt: 0 }}>
                    <ScamReport report={{ ...item.result, injection_flags: item.injection_flags }} />
                  </Box>
                </Collapse>
              </Box>
            ))}
          </Stack>
        )}
      </CardContent>

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this check?"
        message="It will be removed from your history."
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={remove}
        onClose={() => setToDelete(null)}
      />
    </Card>
  );
}

export default function ScamDetection() {
  const [refreshKey, setRefreshKey] = useState(0);
  return (
    <>
      <PageHeader
        title="Scam Detection"
        subtitle="Spot warning signs in job listings and recruiter messages. Evidence and uncertainty are always shown."
      />
      <CheckForm onDone={() => setRefreshKey((k) => k + 1)} />
      <History refreshKey={refreshKey} />
    </>
  );
}
