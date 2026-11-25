import { useState } from "react";
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  Divider,
  Grid,
  IconButton,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import PageHeader from "../components/PageHeader";
import AnimatedPage from "../components/AnimatedPage";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { jobsApi, scamApi } from "../services/endpoints";
import { errorMessage, formatDateTime } from "../utils/format";
import { SCAM_LEVELS } from "../utils/statuses";

function ResultCard({ result }) {
  const meta = SCAM_LEVELS[result.risk_level] || SCAM_LEVELS.low_concern;
  return (
    <Card sx={{ mt: 3 }}>
      <CardContent>
        <Alert severity={meta.severity} sx={{ mb: 2 }}>
          <AlertTitle>
            {meta.label} - concern score {result.concern_score}/100 (confidence: {result.confidence})
          </AlertTitle>
          {result.uncertainty}
        </Alert>

        {result.signals.length > 0 ? (
          <>
            <Typography variant="subtitle2" gutterBottom>Warning signs found ({result.signals.length})</Typography>
            <Stack spacing={1.5} sx={{ mb: 3 }}>
              {result.signals.map((s) => (
                <Box key={s.key} sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 2 }}>
                  <Stack direction="row" justifyContent="space-between" spacing={1}>
                    <Typography variant="body2" fontWeight={600}>{s.description}</Typography>
                    <Chip size="small" variant="outlined" label={`+${s.weight}`} />
                  </Stack>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5, wordBreak: "break-word" }}>
                    Evidence: "{s.evidence}"
                  </Typography>
                </Box>
              ))}
            </Stack>
          </>
        ) : (
          <Typography color="text.secondary" sx={{ mb: 3 }}>
            None of the rule-based checks found a warning sign. That does not prove the listing is genuine.
          </Typography>
        )}

        <Typography variant="subtitle2" gutterBottom>How to verify the employer</Typography>
        <List dense disablePadding>
          {result.verification_steps.map((step) => (
            <ListItem key={step} disableGutters>
              <ListItemText primary={step} />
            </ListItem>
          ))}
        </List>
      </CardContent>
    </Card>
  );
}

export default function ScamDetection() {
  const toast = useToast();
  const jobs = useApi(() => jobsApi.list({ limit: 100 }));
  const history = useApi(() => scamApi.list());
  const [form, setForm] = useState({ job_id: "", text: "", company: "", url: "", contact_email: "" });
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState(null);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const canCheck = form.job_id || form.text.trim().length >= 20;

  const check = async (e) => {
    e.preventDefault();
    setChecking(true);
    try {
      const body = {
        job_id: form.job_id || null,
        text: form.text.trim() || null,
        company: form.company.trim() || null,
        url: form.url.trim() || null,
        contact_email: form.contact_email.trim() || null,
      };
      setResult(await scamApi.assess(body));
      history.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setChecking(false);
    }
  };

  const remove = async (id) => {
    try {
      await scamApi.remove(id);
      history.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <AnimatedPage>
      <PageHeader
        title="Scam Detection"
        subtitle="A transparent, rule-based check. It shows evidence and uncertainty, and never declares a listing fraudulent or safe."
      />

      <Grid container spacing={3}>
        <Grid item xs={12} lg={7}>
          <Card>
            <CardContent component="form" onSubmit={check}>
              <Stack spacing={2}>
                <TextField select label="Check a saved job (optional)" value={form.job_id} onChange={set("job_id")} fullWidth>
                  <MenuItem value="">Paste a listing instead</MenuItem>
                  {(jobs.data?.jobs || []).map((j) => (
                    <MenuItem key={j.id} value={j.id}>{j.title} - {j.company}</MenuItem>
                  ))}
                </TextField>
                {!form.job_id && (
                  <TextField
                    label="Listing text, recruiter message or email"
                    value={form.text}
                    onChange={set("text")}
                    multiline
                    minRows={8}
                    maxRows={18}
                    fullWidth
                    helperText="Paste exactly what you received. It is analysed locally and treated as untrusted text."
                  />
                )}
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={4}>
                    <TextField label="Company name (optional)" value={form.company} onChange={set("company")} fullWidth inputProps={{ maxLength: 200 }} />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField label="Listing URL (optional)" value={form.url} onChange={set("url")} fullWidth placeholder="https://" />
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <TextField label="Contact email (optional)" value={form.contact_email} onChange={set("contact_email")} fullWidth inputProps={{ maxLength: 200 }} />
                  </Grid>
                </Grid>
                <Box>
                  <Button type="submit" variant="contained" disabled={checking || !canCheck}>
                    {checking ? <CircularProgress size={22} color="inherit" /> : "Check for warning signs"}
                  </Button>
                </Box>
              </Stack>
            </CardContent>
          </Card>
          {result && <ResultCard result={result} />}
        </Grid>

        <Grid item xs={12} lg={5}>
          <Card>
            <CardHeader title="Recent checks" />
            <Divider />
            <CardContent sx={{ p: 0 }}>
              {history.error && <Alert severity="error" sx={{ m: 2 }}>{history.error}</Alert>}
              {history.data?.length ? (
                <List disablePadding>
                  {history.data.slice(0, 15).map((h) => {
                    const meta = SCAM_LEVELS[h.risk_level] || SCAM_LEVELS.low_concern;
                    return (
                      <ListItem
                        key={h.id}
                        divider
                        secondaryAction={
                          <Tooltip title="Delete">
                            <IconButton edge="end" size="small" onClick={() => remove(h.id)} aria-label="Delete check"><DeleteOutline fontSize="small" /></IconButton>
                          </Tooltip>
                        }
                      >
                        <ListItemText
                          primary={<Stack direction="row" spacing={1} alignItems="center"><Chip size="small" color={meta.color} label={meta.label} /><Typography variant="body2" noWrap>{h.title || h.company || "Pasted text"}</Typography></Stack>}
                          secondary={`${formatDateTime(h.created_at)} - score ${h.concern_score}`}
                        />
                      </ListItem>
                    );
                  })}
                </List>
              ) : (
                <Typography color="text.secondary" sx={{ p: 3 }} align="center">
                  {history.loading ? "Loading..." : "No checks yet."}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </AnimatedPage>
  );
}
