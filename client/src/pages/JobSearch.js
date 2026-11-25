import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  InputAdornment,
  LinearProgress,
  MenuItem,
  Skeleton,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import SearchIcon from "@mui/icons-material/Search";
import PageHeader from "../components/PageHeader";
import JobCard from "../components/jobs/JobCard";
import JobDetailDialog from "../components/jobs/JobDetailDialog";
import AddJobDialog from "../components/jobs/AddJobDialog";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { jobsApi } from "../services/endpoints";
import { errorMessage } from "../utils/format";
import { SOURCE_LABELS } from "../utils/jobs";

const SOURCES = ["remotive", "arbeitnow"];
const PAGE = 25;

function DiscoverTab({ onOpen, results, setResults }) {
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [limit, setLimit] = useState(15);
  const [sources, setSources] = useState(SOURCES);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const toggle = (name) =>
    setSources((s) => (s.includes(name) ? s.filter((x) => x !== name) : [...s, name]));

  const search = async (event) => {
    event.preventDefault();
    if (query.trim().length < 2 || !sources.length) return;
    setError("");
    setLoading(true);
    try {
      const res = await jobsApi.discover({
        query: query.trim(),
        location: location.trim() || null,
        limit,
        sources,
      });
      setResults(res);
      if (!res.found) toast.info("No jobs matched that search.");
    } catch (err) {
      setError(errorMessage(err, "Job search failed"));
    } finally {
      setLoading(false);
    }
  };

  const errorEntries = Object.entries(results?.errors || {});

  return (
    <Box>
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <form onSubmit={search}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "flex-start" }}>
              <TextField
                size="small"
                label="Job title or keywords"
                placeholder="e.g. python developer"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                sx={{ flex: 2 }}
                inputProps={{ maxLength: 100 }}
                InputProps={{ startAdornment: (<InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>) }}
              />
              <TextField size="small" label="Location (optional)" value={location} onChange={(e) => setLocation(e.target.value)} sx={{ flex: 1 }} inputProps={{ maxLength: 100 }} />
              <TextField select size="small" label="Per source" value={limit} onChange={(e) => setLimit(Number(e.target.value))} sx={{ minWidth: 110 }}>
                {[10, 15, 20, 30].map((n) => (
                  <MenuItem key={n} value={n}>
                    {n} jobs
                  </MenuItem>
                ))}
              </TextField>
              <Button type="submit" variant="contained" disabled={loading || query.trim().length < 2 || !sources.length} sx={{ minWidth: 120, height: 40 }}>
                {loading ? "Searching..." : "Search"}
              </Button>
            </Stack>
            <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" sx={{ mt: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Permitted sources:
              </Typography>
              {SOURCES.map((name) => (
                <FormControlLabel
                  key={name}
                  control={<Checkbox size="small" checked={sources.includes(name)} onChange={() => toggle(name)} />}
                  label={<Typography variant="body2">{SOURCE_LABELS[name]}</Typography>}
                />
              ))}
            </Stack>
            {loading && <LinearProgress sx={{ mt: 1 }} />}
          </form>
        </CardContent>
      </Card>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {results && (
        <>
          <Alert severity={results.found ? "success" : "info"} sx={{ mb: 2 }}>
            Found {results.found} job(s): {results.saved} new, {results.duplicates} already saved.
            {!results.scored && " Add a resume or fill in your profile to see match scores."}
            {results.at_capacity && " Your saved-jobs limit was reached, so some results were not saved."}
          </Alert>
          {errorEntries.map(([name, message]) => (
            <Alert key={name} severity="warning" sx={{ mb: 2 }}>
              {SOURCE_LABELS[name] || name} could not be reached ({message}). Results from the other source are shown.
            </Alert>
          ))}
          <Stack spacing={2}>
            {results.items.map((job) => (
              <JobCard key={job.id} job={job} onOpen={onOpen} />
            ))}
          </Stack>
        </>
      )}

      {!results && !loading && (
        <Typography color="text.secondary" align="center" sx={{ py: 6 }}>
          Search public job boards. Results are saved to your account, scored against your profile, and checked for scam signals.
        </Typography>
      )}
    </Box>
  );
}

function SavedTab({ onOpen, refreshKey }) {
  const [input, setInput] = useState("");
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(PAGE);
  const { data, loading, error, reload } = useApi(() => jobsApi.list({ q: q || undefined, limit }), [q, limit, refreshKey]);
  const items = data?.items || [];

  return (
    <Box>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setLimit(PAGE);
          setQ(input.trim());
        }}
      >
        <Stack direction="row" spacing={2} sx={{ mb: 3 }}>
          <TextField size="small" fullWidth placeholder="Filter saved jobs by title or company" value={input} onChange={(e) => setInput(e.target.value)} inputProps={{ maxLength: 100 }} />
          <Button type="submit" variant="outlined">
            Filter
          </Button>
        </Stack>
      </form>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={reload}>Retry</Button>}>
          {error}
        </Alert>
      )}

      {loading && !data ? (
        <Stack spacing={2}>
          <Skeleton variant="rounded" height={120} />
          <Skeleton variant="rounded" height={120} />
        </Stack>
      ) : items.length === 0 && !error ? (
        <Typography color="text.secondary" align="center" sx={{ py: 6 }}>
          {q ? "No saved jobs match that filter." : "No saved jobs yet. Search for jobs or add one manually."}
        </Typography>
      ) : (
        <>
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
            Showing {items.length} of {data?.total ?? 0}
          </Typography>
          <Stack spacing={2}>
            {items.map((job) => (
              <JobCard key={job.id} job={job} onOpen={onOpen} />
            ))}
          </Stack>
          {data && items.length < data.total && (
            <Box sx={{ textAlign: "center", mt: 3 }}>
              <Button onClick={() => setLimit((l) => l + PAGE)} disabled={loading}>
                Show more
              </Button>
            </Box>
          )}
        </>
      )}
    </Box>
  );
}

export default function JobSearch() {
  const toast = useToast();
  const [tab, setTab] = useState(0);
  const [results, setResults] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // After the detail dialog changes a job (re-score or delete), refresh what is on screen.
  const handleChanged = async () => {
    setRefreshKey((k) => k + 1);
    if (!results || !openId) return;
    const id = openId;
    try {
      const res = await jobsApi.get(id);
      const match = res.match ? { score: res.match.score, label: res.match.label } : null;
      setResults((r) => ({ ...r, items: r.items.map((j) => (j.id === id ? { ...j, match } : j)) }));
    } catch (err) {
      if (err.response?.status === 404) setResults((r) => ({ ...r, items: r.items.filter((j) => j.id !== id) }));
    }
  };

  return (
    <>
      <PageHeader
        title="AI Job Search"
        subtitle="Discover jobs from permitted public sources. Every result is saved, scored with evidence, and screened for scam signals."
        actions={
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setAddOpen(true)}>
            Add job
          </Button>
        }
      />
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3, borderBottom: 1, borderColor: "divider" }}>
        <Tab label="Discover" />
        <Tab label="Saved jobs" />
      </Tabs>

      {tab === 0 ? (
        <DiscoverTab onOpen={(job) => setOpenId(job.id)} results={results} setResults={setResults} />
      ) : (
        <SavedTab onOpen={(job) => setOpenId(job.id)} refreshKey={refreshKey} />
      )}

      {openId && <JobDetailDialog jobId={openId} onClose={() => setOpenId(null)} onChanged={handleChanged} />}

      <AddJobDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onCreated={(res) => {
          setAddOpen(false);
          setRefreshKey((k) => k + 1);
          toast.success(res.created ? "Job saved and scored" : "That job was already saved");
          setTab(1);
          setOpenId(res.job.id);
        }}
      />
    </>
  );
}
