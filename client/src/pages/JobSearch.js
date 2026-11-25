import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Checkbox,
  CircularProgress,
  FormControlLabel,
  FormGroup,
  Grid,
  InputAdornment,
  MenuItem,
  Pagination,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import SearchOutlined from "@mui/icons-material/SearchOutlined";
import AddOutlined from "@mui/icons-material/AddOutlined";
import PageHeader from "../components/PageHeader";
import AnimatedPage from "../components/AnimatedPage";
import ConfirmDialog from "../components/ConfirmDialog";
import JobCard from "../components/JobCard";
import ManualJobDialog from "../components/ManualJobDialog";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { applicationsApi, jobsApi } from "../services/endpoints";
import { errorMessage } from "../utils/format";

const PAGE_SIZE = 20;

export default function JobSearch() {
  const toast = useToast();
  const sources = useApi(() => jobsApi.sources());
  const [form, setForm] = useState({ query: "", location: "", limit: 20, sources: null });
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState(null);
  const [filterInput, setFilterInput] = useState("");
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [manualOpen, setManualOpen] = useState(false);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [trackingId, setTrackingId] = useState(null);

  const saved = useApi(() => jobsApi.list({ q: filter || undefined, skip: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE }), [filter, page]);

  const allSources = sources.data?.sources || [];
  const selected = form.sources ?? allSources;

  const toggleSource = (name) => {
    const next = selected.includes(name) ? selected.filter((s) => s !== name) : [...selected, name];
    setForm((f) => ({ ...f, sources: next }));
  };

  const search = async (e) => {
    e.preventDefault();
    if (form.query.trim().length < 2) return toast.warning("Enter a job title or keyword (at least 2 characters).");
    if (!selected.length) return toast.warning("Select at least one job source.");
    setSearching(true);
    setResult(null);
    try {
      const res = await jobsApi.discover({
        query: form.query.trim(),
        location: form.location.trim() || null,
        limit: Number(form.limit),
        sources: selected,
      });
      setResult(res);
      setPage(1);
      saved.reload();
      if (res.saved_new > 0) toast.success(`${res.saved_new} new job(s) saved.`);
      else if (res.found === 0) toast.info("No jobs found for that search.");
      else toast.info("Everything found was already saved.");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSearching(false);
    }
  };

  const track = async (job) => {
    setTrackingId(job.id);
    try {
      const res = await applicationsApi.fromJob(job.id);
      toast[res.created ? "success" : "info"](res.created ? "Added to Applications as Saved." : "Already in your Applications.");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setTrackingId(null);
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await jobsApi.remove(toDelete.id);
      toast.success("Job removed.");
      setResult((r) => (r ? { ...r, jobs: r.jobs.filter((j) => j.id !== toDelete.id) } : r));
      setToDelete(null);
      saved.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  const total = saved.data?.total || 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const sourceErrors = result ? Object.entries(result.source_errors || {}) : [];

  return (
    <AnimatedPage>
      <PageHeader
        title="AI Job Search"
        subtitle="Search permitted public job boards. Results are de-duplicated, safety-checked and scored against your profile."
        actions={
          <Button variant="outlined" startIcon={<AddOutlined />} onClick={() => setManualOpen(true)}>
            Add job manually
          </Button>
        }
      />

      <Card sx={{ mb: 3 }}>
        <CardContent component="form" onSubmit={search}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={5}>
              <TextField
                label="Job title or keywords"
                value={form.query}
                onChange={(e) => setForm((f) => ({ ...f, query: e.target.value }))}
                fullWidth
                placeholder="e.g. python developer"
                inputProps={{ maxLength: 100 }}
                InputProps={{ startAdornment: <InputAdornment position="start"><SearchOutlined /></InputAdornment> }}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <TextField label="Location (optional)" value={form.location} onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))} fullWidth inputProps={{ maxLength: 100 }} />
            </Grid>
            <Grid item xs={6} md={2}>
              <TextField select label="Per source" value={form.limit} onChange={(e) => setForm((f) => ({ ...f, limit: e.target.value }))} fullWidth>
                {[10, 20, 30, 50].map((n) => (
                  <MenuItem key={n} value={n}>
                    {n}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={6} md={2}>
              <Button type="submit" variant="contained" fullWidth size="large" disabled={searching || sources.loading}>
                {searching ? <CircularProgress size={22} color="inherit" /> : "Search"}
              </Button>
            </Grid>
            <Grid item xs={12}>
              <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
                <Typography variant="body2" color="text.secondary">
                  Sources:
                </Typography>
                <FormGroup row>
                  {allSources.map((name) => (
                    <FormControlLabel key={name} control={<Checkbox size="small" checked={selected.includes(name)} onChange={() => toggleSource(name)} />} label={name} />
                  ))}
                </FormGroup>
              </Stack>
              {sources.error && <Alert severity="error" sx={{ mt: 1 }}>{sources.error}</Alert>}
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {result && (
        <Box sx={{ mb: 4 }}>
          <Alert severity={result.saved_new > 0 ? "success" : "info"} sx={{ mb: 2 }}>
            Found {result.found} listing(s): {result.saved_new} new, {result.duplicates_skipped} already saved
            {result.scored > 0 ? `, ${result.scored} scored.` : "."}
            {result.scoring_note ? ` ${result.scoring_note}` : ""}
          </Alert>
          {sourceErrors.map(([name, msg]) => (
            <Alert severity="warning" key={name} sx={{ mb: 1 }}>
              Source "{name}" failed: {msg}. The other sources were still searched.
            </Alert>
          ))}
          <Stack spacing={2} sx={{ mt: 2 }}>
            {result.jobs.map((job) => (
              <JobCard key={job.id} job={job} onTrack={track} onDelete={setToDelete} tracking={trackingId === job.id} />
            ))}
          </Stack>
        </Box>
      )}

      <Card>
        <CardHeader
          title="Saved jobs"
          subheader={`${total} job(s) in your pipeline`}
          action={
            <Stack direction="row" spacing={1} component="form" onSubmit={(e) => { e.preventDefault(); setFilter(filterInput.trim()); setPage(1); }}>
              <TextField size="small" placeholder="Filter by title, company, location" value={filterInput} onChange={(e) => setFilterInput(e.target.value)} sx={{ minWidth: 260 }} />
              <Button type="submit" size="small">Filter</Button>
            </Stack>
          }
        />
        <CardContent>
          {saved.error && <Alert severity="error" sx={{ mb: 2 }}>{saved.error}</Alert>}
          {saved.loading && !saved.data ? (
            <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress /></Box>
          ) : saved.data?.jobs?.length ? (
            <Stack spacing={2}>
              {saved.data.jobs.map((job) => (
                <JobCard key={job.id} job={job} onTrack={track} onDelete={setToDelete} tracking={trackingId === job.id} />
              ))}
              {pages > 1 && <Pagination count={pages} page={page} onChange={(_, p) => setPage(p)} sx={{ alignSelf: "center" }} />}
            </Stack>
          ) : (
            <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
              {filter ? "No saved jobs match that filter." : "No saved jobs yet. Run a search above or add a job manually."}
            </Typography>
          )}
        </CardContent>
      </Card>

      <ManualJobDialog
        open={manualOpen}
        onClose={() => setManualOpen(false)}
        onSaved={(res) => {
          setManualOpen(false);
          toast[res.created ? "success" : "info"](res.created ? "Job saved." : "That job was already saved.");
          saved.reload();
        }}
      />
      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Remove this job?"
        message={toDelete ? `"${toDelete.title}" at ${toDelete.company} and its match score will be deleted. Tracked applications are kept.` : ""}
        confirmLabel="Remove"
        loading={deleting}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
      />
    </AnimatedPage>
  );
}
