import { useState } from "react";
import {
  Alert,
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
  LinearProgress,
  Link,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
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
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import OpenInNew from "@mui/icons-material/OpenInNew";
import RefreshOutlined from "@mui/icons-material/RefreshOutlined";
import PageHeader from "../components/PageHeader";
import AnimatedPage from "../components/AnimatedPage";
import ConfirmDialog from "../components/ConfirmDialog";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { companyResearchApi, jobsApi } from "../services/endpoints";
import { errorMessage, formatDateTime } from "../utils/format";
import { safeUrl } from "../utils/statuses";

const SEEN_IN = {
  both: { label: "Website and your jobs", color: "success" },
  website: { label: "Website", color: "info" },
  "your saved jobs": { label: "Your saved jobs", color: "default" },
};

const normalizeUrl = (value) => {
  const t = value.trim();
  if (!t) return null;
  return /^https?:\/\//i.test(t) ? t : `https://${t}`;
};

function Section({ title, subheader, children }) {
  return (
    <Card>
      <CardHeader title={title} subheader={subheader} titleTypographyProps={{ variant: "h6" }} />
      <CardContent sx={{ pt: 0 }}>{children}</CardContent>
    </Card>
  );
}

function ChipList({ items, color, empty }) {
  if (!items?.length) return <Typography variant="body2" color="text.secondary">{empty}</Typography>;
  return (
    <Stack direction="row" flexWrap="wrap" gap={1}>
      {items.map((item) => <Chip key={item} label={item} color={color} variant="outlined" />)}
    </Stack>
  );
}

function ResearchDetail({ doc, onRefresh, refreshing }) {
  const c = doc.content || {};
  const site = safeUrl(doc.website);
  const basedOn = doc.source_kind === "website" ? "Company website" : doc.source_kind === "saved_jobs" ? "Your saved jobs only" : "No sources";

  return (
    <Stack spacing={2.5}>
      <Card>
        <CardContent>
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={2}>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h5">{doc.company}</Typography>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
                <Chip size="small" label={`Based on: ${basedOn}`} />
                {doc.jobs_used > 0 && <Chip size="small" variant="outlined" label={`${doc.jobs_used} saved job(s) used`} />}
                <Chip size="small" variant="outlined" color={doc.ai_used ? "success" : "default"} label={doc.ai_used ? "Overview written by local AI and fact-checked" : "No AI-written text"} />
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
                Updated {formatDateTime(doc.updated_at)}
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} alignItems="flex-start">
              {site && (
                <Button component="a" href={site} target="_blank" rel="noopener noreferrer" endIcon={<OpenInNew fontSize="small" />}>
                  Website
                </Button>
              )}
              <Button startIcon={<RefreshOutlined />} onClick={onRefresh} disabled={refreshing}>
                {refreshing ? "Refreshing..." : "Refresh"}
              </Button>
            </Stack>
          </Stack>
        </CardContent>
      </Card>

      {doc.injection_flags?.length > 0 && (
        <Alert severity="warning">
          The website text contained wording aimed at AI tools. It was treated as data and ignored.
        </Alert>
      )}
      {doc.warnings?.map((w) => <Alert key={w} severity="info">{w}</Alert>)}

      <Section title="Overview">
        {c.overview ? (
          <Typography variant="body1">{c.overview}</Typography>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No overview could be written from the sources available. Add the company website and refresh to try again.
          </Typography>
        )}
        {c.products_services?.length > 0 && (
          <>
            <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>Products and services named on the website</Typography>
            <ChipList items={c.products_services} empty="" />
          </>
        )}
      </Section>

      <Section title="Technologies" subheader="Skills mentioned on the website or in your saved jobs for this company">
        {c.technologies?.length ? (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Technology</TableCell>
                  <TableCell>Seen in</TableCell>
                  <TableCell align="right">Saved jobs</TableCell>
                  <TableCell>In your profile</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {c.technologies.map((t) => {
                  const seen = SEEN_IN[t.source] || SEEN_IN["your saved jobs"];
                  return (
                    <TableRow key={t.skill}>
                      <TableCell>{t.skill}</TableCell>
                      <TableCell><Chip size="small" variant="outlined" color={seen.color} label={seen.label} /></TableCell>
                      <TableCell align="right">{t.jobs || "-"}</TableCell>
                      <TableCell><Chip size="small" color={t.you_have ? "success" : "warning"} label={t.you_have ? "You have it" : "Gap"} /></TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <Typography variant="body2" color="text.secondary">No technologies were found in the sources available.</Typography>
        )}
      </Section>

      <Grid container spacing={2.5}>
        <Grid item xs={12} md={6}>
          <Section title="Strengths to highlight" subheader="Their technologies that you already have">
            <ChipList items={c.strengths_to_highlight} color="success" empty="No overlap found yet. Add your skills to your profile." />
          </Section>
        </Grid>
        <Grid item xs={12} md={6}>
          <Section title="Gaps to prepare" subheader="Their technologies that are not in your profile">
            <ChipList items={c.gaps_to_prepare} color="warning" empty="No gaps found against the sources available." />
          </Section>
        </Grid>
      </Grid>

      <Section title="Interview preparation" subheader="Topics built from the overlap and gaps above">
        {c.interview_topics?.length ? (
          <List dense disablePadding>
            {c.interview_topics.map((topic) => (
              <ListItem key={topic} disableGutters alignItems="flex-start">
                <ListItemText primary={topic} />
              </ListItem>
            ))}
          </List>
        ) : (
          <Typography variant="body2" color="text.secondary">No topics yet.</Typography>
        )}
      </Section>

      <Section title="Sources">
        {doc.sources?.length ? (
          <Stack spacing={0.5}>
            {doc.sources.map((s) => {
              const href = safeUrl(s.url);
              return href ? (
                <Link key={s.url} href={href} target="_blank" rel="noopener noreferrer" underline="hover" variant="body2" sx={{ wordBreak: "break-all" }}>
                  {s.title || s.url}
                </Link>
              ) : null;
            })}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No web pages were read. Technologies come only from the jobs you saved for this company.
          </Typography>
        )}
      </Section>

      <Alert severity="info" variant="outlined">{doc.limits}</Alert>
    </Stack>
  );
}

export default function CompanyResearch() {
  const toast = useToast();
  const history = useApi(() => companyResearchApi.list());
  const jobs = useApi(() => jobsApi.list({ limit: 100 }));
  const [form, setForm] = useState({ company: "", website: "", jobId: "" });
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState(null);
  const [opening, setOpening] = useState(false);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const savedJobs = jobs.data?.items || [];
  const records = history.data?.items || [];

  const run = async (body) => {
    setRunning(true);
    setError("");
    try {
      const doc = await companyResearchApi.research(body);
      setDetail(doc);
      toast.success(`Research saved for ${doc.company}.`);
      history.reload();
    } catch (err) {
      setError(errorMessage(err, "Research failed"));
    } finally {
      setRunning(false);
    }
  };

  const submit = (e) => {
    e.preventDefault();
    const company = form.company.trim();
    if (!company && !form.jobId) return;
    run({ company: company || null, website: normalizeUrl(form.website), job_id: form.jobId || null });
  };

  const pickJob = (e) => {
    const id = e.target.value;
    const job = savedJobs.find((j) => j.id === id);
    setForm((f) => ({ ...f, jobId: id, company: job ? job.company : f.company }));
  };

  const open = async (id) => {
    setOpening(true);
    setError("");
    try {
      setDetail(await companyResearchApi.get(id));
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setOpening(false);
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await companyResearchApi.remove(toDelete.id);
      toast.success("Research deleted.");
      if (detail?.id === toDelete.id) setDetail(null);
      setToDelete(null);
      history.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  const canRun = (form.company.trim() || form.jobId) && !running;

  return (
    <AnimatedPage>
      <PageHeader
        title="Company Research"
        subtitle="Learn about a company before you apply or interview, using its public website and the jobs you saved for it."
      />

      <Grid container spacing={2.5}>
        <Grid item xs={12} lg={4}>
          <Stack spacing={2.5}>
            <Card>
              <CardHeader title="Research a company" />
              <CardContent sx={{ pt: 0 }}>
                <form onSubmit={submit}>
                  <Stack spacing={2}>
                    {error && <Alert severity="error">{error}</Alert>}
                    <TextField
                      select
                      size="small"
                      label="Start from a saved job (optional)"
                      value={form.jobId}
                      onChange={pickJob}
                      helperText={jobs.loading ? "Loading saved jobs..." : savedJobs.length ? "Fills in the company name" : "No saved jobs yet"}
                    >
                      <MenuItem value="">None</MenuItem>
                      {savedJobs.map((j) => <MenuItem key={j.id} value={j.id}>{j.title} - {j.company}</MenuItem>)}
                    </TextField>
                    <TextField size="small" label="Company name" value={form.company} onChange={(e) => setForm((f) => ({ ...f, company: e.target.value }))} inputProps={{ maxLength: 100 }} />
                    <TextField
                      size="small"
                      label="Company website (optional)"
                      placeholder="example.com"
                      value={form.website}
                      onChange={(e) => setForm((f) => ({ ...f, website: e.target.value }))}
                      helperText="Only public pages are read, and only if the site allows it. Private or local addresses are refused."
                    />
                    <Button type="submit" variant="contained" disabled={!canRun}>
                      {running ? "Researching..." : "Research"}
                    </Button>
                    {running && (
                      <Box>
                        <LinearProgress />
                        <Typography variant="caption" color="text.secondary">
                          Reading the website and checking the facts. This can take a minute.
                        </Typography>
                      </Box>
                    )}
                  </Stack>
                </form>
              </CardContent>
            </Card>

            <Card>
              <CardHeader title="Saved research" subheader={records.length ? `${records.length} compan${records.length === 1 ? "y" : "ies"}` : undefined} />
              <Divider />
              {history.loading && !history.data ? (
                <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress size={24} /></Box>
              ) : history.error ? (
                <Alert severity="error" sx={{ m: 2 }} action={<Button color="inherit" size="small" onClick={history.reload}>Retry</Button>}>{history.error}</Alert>
              ) : records.length === 0 ? (
                <Typography color="text.secondary" variant="body2" sx={{ p: 2 }}>Nothing saved yet. Your research appears here.</Typography>
              ) : (
                <List disablePadding>
                  {records.map((r) => (
                    <ListItem
                      key={r.id}
                      disablePadding
                      divider
                      secondaryAction={
                        <Tooltip title="Delete">
                          <IconButton edge="end" size="small" onClick={() => setToDelete(r)} aria-label={`Delete research for ${r.company}`}><DeleteOutline fontSize="small" /></IconButton>
                        </Tooltip>
                      }
                    >
                      <ListItemButton selected={detail?.id === r.id} onClick={() => open(r.id)}>
                        <ListItemText primary={r.company} secondary={`Updated ${formatDateTime(r.updated_at)}`} primaryTypographyProps={{ noWrap: true }} />
                      </ListItemButton>
                    </ListItem>
                  ))}
                </List>
              )}
            </Card>
          </Stack>
        </Grid>

        <Grid item xs={12} lg={8}>
          {opening ? (
            <Box sx={{ textAlign: "center", py: 8 }}><CircularProgress /></Box>
          ) : detail ? (
            <ResearchDetail
              doc={detail}
              refreshing={running}
              onRefresh={() => run({ company: detail.company, website: detail.website || null, job_id: detail.job_id || null })}
            />
          ) : (
            <Card>
              <CardContent sx={{ py: 8, textAlign: "center" }}>
                <Typography color="text.secondary">
                  Enter a company name and website, or pick a saved job, then press Research. You will see what the company does, the technologies it uses, which ones you already have, and what to prepare for an interview.
                </Typography>
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this research?"
        message={toDelete ? `The saved research for ${toDelete.company} will be permanently removed.` : ""}
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
      />
    </AnimatedPage>
  );
}
