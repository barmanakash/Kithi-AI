import { useRef, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
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
  LinearProgress,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import OpenInBrowserOutlined from "@mui/icons-material/OpenInBrowserOutlined";
import RefreshOutlined from "@mui/icons-material/RefreshOutlined";
import CloseOutlined from "@mui/icons-material/CloseOutlined";
import PageHeader from "../components/PageHeader";
import AnimatedPage from "../components/AnimatedPage";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { applicationsApi, formAssistApi, generateApi } from "../services/endpoints";
import { errorMessage } from "../utils/format";
import { safeUrl, statusLabel } from "../utils/statuses";

const SAFETY_NOTICE =
  "Kithi fills only the fields you approve, using verified data from your profile. It never presses submit, never answers open-ended or sensitive questions, and never touches passwords, uploads or agreements. Review the form in the browser window and submit it yourself.";

const BROWSER_GONE = [404, 410, 504];

const withScheme = (value) => {
  const t = value.trim();
  if (!t) return "";
  return /^https?:\/\//i.test(t) ? t : `https://${t}`;
};

const initialRows = (plan) =>
  Object.fromEntries(plan.map((f) => [f.id, { checked: f.action === "fill" && f.proposed != null, value: f.proposed ?? "" }]));

const ACTION_CHIP = {
  fill: { label: "Proposed", color: "success" },
  manual: { label: "Yours to answer", color: "warning" },
  skip: { label: "Never filled", color: "default" },
};

function SetupAlert({ status, onRecheck }) {
  if (!status) return null;
  return (
    <>
      {!status.local && (
        <Alert severity="error" sx={{ mb: 2 }}>
          The browser assistant only works when Kithi runs on your own computer. This request did not come from this machine.
        </Alert>
      )}
      {!status.playwright_installed && (
        <Alert severity="warning" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={onRecheck}>Re-check</Button>}>
          <Typography variant="body2" sx={{ mb: 1 }}>
            The browser tool is not installed yet. In a terminal, from the <code>server</code> folder, run these once, then restart the backend:
          </Typography>
          <Box component="pre" sx={{ m: 0, fontSize: 13, whiteSpace: "pre-wrap" }}>
            {status.setup.join("\n")}
          </Box>
        </Alert>
      )}
    </>
  );
}

function FieldValue({ field, row, onChange }) {
  if (field.action === "skip") return <Typography variant="body2" color="text.disabled">-</Typography>;
  if (field.tag === "select") {
    return (
      <TextField select size="small" fullWidth value={row.value} onChange={(e) => onChange({ value: e.target.value, checked: Boolean(e.target.value) })}>
        <MenuItem value="">Not selected</MenuItem>
        {field.options.map((o) => <MenuItem key={o} value={o}>{o}</MenuItem>)}
      </TextField>
    );
  }
  return (
    <TextField
      size="small"
      fullWidth
      multiline={field.tag === "textarea"}
      minRows={field.tag === "textarea" ? 2 : undefined}
      maxRows={6}
      value={row.value}
      placeholder={field.action === "manual" ? "Type your own answer (optional)" : ""}
      onChange={(e) => onChange({ value: e.target.value, checked: Boolean(e.target.value.trim()) })}
      inputProps={{ maxLength: 2000 }}
    />
  );
}

export default function ApplicationAssistant() {
  const toast = useToast();
  const status = useApi(() => formAssistApi.status());
  const apps = useApi(() => applicationsApi.list({ limit: 200 }));
  const versions = useApi(() => generateApi.list({ limit: 100 }));

  const [form, setForm] = useState({ applicationId: "", url: "", letterId: "" });
  const [session, setSession] = useState(null);
  const [rows, setRows] = useState({});
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const sessionId = useRef(null);

  const applications = apps.data?.items || [];
  const letters = (versions.data?.versions || []).filter((v) => v.kind === "cover_letter");
  const chosenApp = applications.find((a) => a.id === form.applicationId);

  const receive = (res) => {
    sessionId.current = res.session_id;
    setSession(res);
    setRows(initialRows(res.plan));
    setApproved(false);
    setResult(null);
  };

  const reset = () => {
    sessionId.current = null;
    setSession(null);
    setRows({});
    setApproved(false);
    setResult(null);
  };

  const fail = (err, fallback) => {
    setError(errorMessage(err, fallback));
    if (BROWSER_GONE.includes(err.response?.status)) reset();
  };

  const pickApplication = (e) => {
    const app = applications.find((a) => a.id === e.target.value);
    setForm((f) => ({ ...f, applicationId: e.target.value, url: app?.job_url || f.url }));
  };

  const open = async (e) => {
    e.preventDefault();
    setError("");
    setBusy("open");
    try {
      const res = await formAssistApi.open({
        url: form.url.trim() ? withScheme(form.url) : null,
        application_id: form.applicationId || null,
        cover_letter_id: form.letterId || null,
      });
      receive(res);
      toast.success("The form is open in a browser window. Review the plan below.");
    } catch (err) {
      fail(err, "Could not open the form");
    } finally {
      setBusy("");
    }
  };

  const rescan = async () => {
    setError("");
    setBusy("scan");
    try {
      receive(await formAssistApi.scan(session.session_id));
    } catch (err) {
      fail(err, "Could not read the page");
    } finally {
      setBusy("");
    }
  };

  const closeBrowser = async () => {
    const id = session?.session_id;
    reset();
    if (!id) return;
    try {
      await formAssistApi.close(id);
    } catch {
      /* already closed */
    }
  };

  const setRow = (id, patch) => {
    setRows((r) => ({ ...r, [id]: { ...r[id], ...patch } }));
    setApproved(false); // any change needs a fresh approval
  };

  const items = session
    ? session.plan
        .filter((f) => f.action !== "skip" && rows[f.id]?.checked && rows[f.id].value.trim())
        .map((f) => ({ id: f.id, value: rows[f.id].value.trim() }))
    : [];

  const fill = async () => {
    setError("");
    setBusy("fill");
    try {
      const res = await formAssistApi.fill(session.session_id, { items, plan_hash: session.plan_hash, confirmed_by_user: true });
      setResult(res);
      setApproved(false);
      toast.success(`${res.filled.length} field(s) filled. Now review and submit the form yourself.`);
    } catch (err) {
      fail(err, "Could not fill the form");
    } finally {
      setBusy("");
    }
  };

  const opening = busy === "open";

  return (
    <AnimatedPage>
      <PageHeader
        title="Application Assistant"
        subtitle="Open an application form in a browser window and let Kithi type your verified details into the fields you approve. You always submit the form yourself."
      />

      <SetupAlert status={status.data} onRecheck={status.reload} />
      <Alert severity="info" variant="outlined" sx={{ mb: 3 }}>{status.data?.notice || SAFETY_NOTICE}</Alert>
      {error && <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError("")}>{error}</Alert>}

      <Card sx={{ mb: 3 }}>
        <CardHeader title="1. Open the form" subheader="Pick a tracked application or paste the address of the application form." />
        <CardContent sx={{ pt: 0 }}>
          <form onSubmit={open}>
            <Stack spacing={2}>
              <TextField select size="small" label="Tracked application (optional)" value={form.applicationId} onChange={pickApplication}
                helperText={chosenApp ? `Status: ${statusLabel(chosenApp.status)}. Its attached cover letter is used automatically.` : "Fills in the posting link"}>
                <MenuItem value="">None</MenuItem>
                {applications.map((a) => (
                  <MenuItem key={a.id} value={a.id} disabled={!a.job_url && !form.url.trim()}>
                    {a.job_title} - {a.company}{a.job_url ? "" : " (no link saved)"}
                  </MenuItem>
                ))}
              </TextField>
              <TextField size="small" label="Application form address" placeholder="https://jobs.example.com/apply/123" value={form.url} onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
                helperText="Only public websites are opened. Local and private network addresses are refused." />
              <TextField select size="small" label="Cover letter (optional)" value={form.letterId} onChange={(e) => setForm((f) => ({ ...f, letterId: e.target.value }))}
                helperText="Only offered for a field that asks for a cover letter. Longer than 2000 characters? Paste it yourself.">
                <MenuItem value="">{chosenApp?.cover_letter_version_id ? "Use the one attached to the application" : "None"}</MenuItem>
                {letters.map((l) => <MenuItem key={l.id} value={l.id}>{l.title || "Cover letter"}</MenuItem>)}
              </TextField>
              <Box>
                <Button type="submit" variant="contained" startIcon={<OpenInBrowserOutlined />}
                  disabled={opening || (!form.url.trim() && !chosenApp?.job_url) || status.data?.playwright_installed === false || status.data?.local === false}>
                  {opening ? "Opening the browser..." : session ? "Open again" : "Open form in browser"}
                </Button>
              </Box>
              {opening && (
                <Box>
                  <LinearProgress />
                  <Typography variant="caption" color="text.secondary">Starting a browser window and reading the form. This can take up to a minute.</Typography>
                </Box>
              )}
            </Stack>
          </form>
        </CardContent>
      </Card>

      {session && (
        <Card>
          <CardHeader
            title="2. Review and approve"
            subheader={
              <>
                {session.title || "Untitled page"}
                {safeUrl(session.url) && <Typography component="span" variant="caption" color="text.secondary" sx={{ display: "block", wordBreak: "break-all" }}>{session.url}</Typography>}
              </>
            }
            action={
              <Stack direction="row" spacing={1}>
                <Button size="small" startIcon={<RefreshOutlined />} onClick={rescan} disabled={Boolean(busy)}>{busy === "scan" ? "Reading..." : "Rescan page"}</Button>
                <Button size="small" color="inherit" startIcon={<CloseOutlined />} onClick={closeBrowser}>Close browser</Button>
              </Stack>
            }
          />
          <CardContent sx={{ pt: 0 }}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
              <Chip size="small" color="success" label={`${session.summary.fillable} proposed`} />
              <Chip size="small" color="warning" label={`${session.summary.manual} yours to answer`} />
              <Chip size="small" label={`${session.summary.skipped} never filled`} />
            </Stack>
            {session.notes.map((n) => <Alert key={n} severity="info" sx={{ mb: 2 }}>{n}</Alert>)}
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Moving to the next step of a multi-step form? Go to it in the browser window, then press Rescan page. You can edit any value below, or type your own answer into a field Kithi left for you.
            </Typography>

            {session.plan.length > 0 && (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell padding="checkbox">Fill</TableCell>
                      <TableCell>Field</TableCell>
                      <TableCell sx={{ minWidth: 260 }}>Value to type</TableCell>
                      <TableCell>Why</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {session.plan.map((f) => {
                      const row = rows[f.id] || { checked: false, value: "" };
                      const chip = ACTION_CHIP[f.action];
                      const skip = f.action === "skip";
                      return (
                        <TableRow key={f.id} sx={{ opacity: skip ? 0.6 : 1 }}>
                          <TableCell padding="checkbox">
                            <Checkbox checked={!skip && row.checked} disabled={skip || !row.value.trim()} onChange={(e) => setRow(f.id, { checked: e.target.checked })} inputProps={{ "aria-label": `Fill ${f.label}` }} />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" fontWeight={600}>{f.label}{f.required ? " *" : ""}</Typography>
                            <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }}>
                              <Chip size="small" color={chip.color} variant="outlined" label={chip.label} />
                              <Chip size="small" variant="outlined" label={f.kind.replace(/_/g, " ")} />
                            </Stack>
                          </TableCell>
                          <TableCell><FieldValue field={f} row={row} onChange={(patch) => setRow(f.id, patch)} /></TableCell>
                          <TableCell>
                            <Typography variant="caption" color="text.secondary">
                              {f.reason || (f.proposed != null ? "From your verified profile" : "")}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}

            {session.plan.length > 0 && (
              <Box sx={{ mt: 3, p: 2, border: 1, borderColor: "divider", borderRadius: 2 }}>
                <FormControlLabel
                  control={<Checkbox checked={approved} onChange={(e) => setApproved(e.target.checked)} />}
                  label="I have reviewed these fields and approve typing the ticked values into the form. I will check the form and submit it myself."
                />
                <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 1 }}>
                  <Tooltip title={!items.length ? "Tick at least one field that has a value" : !approved ? "Tick the approval box first" : ""}>
                    <span>
                      <Button variant="contained" onClick={fill} disabled={!approved || !items.length || Boolean(busy)}>
                        {busy === "fill" ? "Filling..." : `Fill ${items.length} field${items.length === 1 ? "" : "s"}`}
                      </Button>
                    </span>
                  </Tooltip>
                  <Typography variant="caption" color="text.secondary">Kithi will not press submit.</Typography>
                </Stack>
              </Box>
            )}

            {result && (
              <Alert severity={result.failed.length ? "warning" : "success"} sx={{ mt: 3 }}>
                <Typography variant="body2" fontWeight={600}>
                  Filled {result.filled.length} field{result.filled.length === 1 ? "" : "s"}{result.failed.length ? `, ${result.failed.length} could not be filled` : ""}.
                </Typography>
                {result.failed.map((f) => <Typography key={f.id} variant="body2">{f.label}: {f.error}</Typography>)}
                <Typography variant="body2" sx={{ mt: 1 }}>{result.message}</Typography>
                <Button component={RouterLink} to="/applications" size="small" sx={{ mt: 1 }}>
                  After you submit, record it in Applications
                </Button>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}
    </AnimatedPage>
  );
}
