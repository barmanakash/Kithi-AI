import { useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  IconButton,
  InputAdornment,
  MenuItem,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import AddOutlined from "@mui/icons-material/AddOutlined";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import EditOutlined from "@mui/icons-material/EditOutlined";
import FactCheckOutlined from "@mui/icons-material/FactCheckOutlined";
import SearchOutlined from "@mui/icons-material/SearchOutlined";
import OpenInNew from "@mui/icons-material/OpenInNew";
import PageHeader from "../components/PageHeader";
import AnimatedPage from "../components/AnimatedPage";
import ConfirmDialog from "../components/ConfirmDialog";
import ApplicationDialog from "../components/ApplicationDialog";
import QualityCheckDialog from "../components/QualityCheckDialog";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { applicationsApi, resumesApi } from "../services/endpoints";
import { errorMessage, formatDateTime } from "../utils/format";
import { APPLICATION_STATUSES, safeUrl, statusColor, statusLabel } from "../utils/statuses";

const todayIso = () => new Date().toISOString().slice(0, 10);

function StatusSelect({ app, onChange, sx }) {
  return (
    <TextField select size="small" value={app.status} onChange={(e) => onChange(app, e.target.value)} sx={sx} aria-label="Application status">
      {APPLICATION_STATUSES.map((s) => <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>)}
    </TextField>
  );
}

function ActionButtons({ app, onEdit, onCheck, onDelete }) {
  const url = safeUrl(app.job_url);
  return (
    <Stack direction="row" spacing={0.25}>
      <Tooltip title="Quality check"><IconButton size="small" onClick={() => onCheck(app)} aria-label="Quality check"><FactCheckOutlined fontSize="small" /></IconButton></Tooltip>
      <Tooltip title="Edit"><IconButton size="small" onClick={() => onEdit(app)} aria-label="Edit"><EditOutlined fontSize="small" /></IconButton></Tooltip>
      {url && <Tooltip title="Open job posting"><IconButton size="small" component="a" href={url} target="_blank" rel="noopener noreferrer" aria-label="Open job posting"><OpenInNew fontSize="small" /></IconButton></Tooltip>}
      <Tooltip title="Delete"><IconButton size="small" onClick={() => onDelete(app)} aria-label="Delete"><DeleteOutline fontSize="small" /></IconButton></Tooltip>
    </Stack>
  );
}

function FollowUpChip({ app }) {
  if (!app.follow_up_date) return null;
  const overdue = app.follow_up_date < todayIso() && !["rejected", "withdrawn", "offer_received"].includes(app.status);
  return <Chip size="small" variant="outlined" color={overdue ? "error" : "default"} label={`${overdue ? "Overdue: " : "Follow up: "}${app.follow_up_date}`} />;
}

function KanbanBoard({ apps, onMove, onEdit, onCheck, onDelete }) {
  const [dragOver, setDragOver] = useState(null);

  const drop = (e, status) => {
    e.preventDefault();
    setDragOver(null);
    const id = e.dataTransfer.getData("text/plain");
    const app = apps.find((a) => a.id === id);
    if (app && app.status !== status) onMove(app, status);
  };

  return (
    <Box sx={{ display: "flex", gap: 2, overflowX: "auto", pb: 2, alignItems: "flex-start" }}>
      {APPLICATION_STATUSES.map((col) => {
        const items = apps.filter((a) => a.status === col.value);
        return (
          <Paper
            key={col.value}
            variant="outlined"
            onDragOver={(e) => { e.preventDefault(); setDragOver(col.value); }}
            onDragLeave={() => setDragOver((c) => (c === col.value ? null : c))}
            onDrop={(e) => drop(e, col.value)}
            sx={{ minWidth: 270, width: 270, flexShrink: 0, p: 1.5, bgcolor: dragOver === col.value ? "action.hover" : "background.paper" }}
          >
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5 }}>
              <Typography variant="subtitle2">{col.label}</Typography>
              <Chip size="small" label={items.length} color={col.color} variant="outlined" />
            </Stack>
            <Stack spacing={1.5} sx={{ minHeight: 40 }}>
              {items.map((app) => (
                <Card key={app.id} variant="outlined" draggable onDragStart={(e) => e.dataTransfer.setData("text/plain", app.id)} sx={{ cursor: "grab" }}>
                  <CardContent sx={{ p: 1.5, "&:last-child": { pb: 1.5 } }}>
                    <Typography variant="body2" fontWeight={600} noWrap>{app.job_title}</Typography>
                    <Typography variant="caption" color="text.secondary" noWrap display="block">{app.company}</Typography>
                    <Stack direction="row" gap={0.5} flexWrap="wrap" sx={{ my: 1 }}>
                      <FollowUpChip app={app} />
                      {app.resume_label && <Chip size="small" variant="outlined" label={app.resume_label} sx={{ maxWidth: 200 }} />}
                    </Stack>
                    <StatusSelect app={app} onChange={onMove} sx={{ width: "100%", mb: 1 }} />
                    <ActionButtons app={app} onEdit={onEdit} onCheck={onCheck} onDelete={onDelete} />
                  </CardContent>
                </Card>
              ))}
            </Stack>
          </Paper>
        );
      })}
    </Box>
  );
}

function ApplicationsTable({ apps, onMove, onEdit, onCheck, onDelete }) {
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Company</TableCell>
            <TableCell>Job title</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Applied</TableCell>
            <TableCell>Follow-up</TableCell>
            <TableCell>Resume</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {apps.map((app) => (
            <TableRow key={app.id} hover>
              <TableCell>{app.company}</TableCell>
              <TableCell>{app.job_title}</TableCell>
              <TableCell><StatusSelect app={app} onChange={onMove} sx={{ minWidth: 190 }} /></TableCell>
              <TableCell>{app.application_date || "-"}</TableCell>
              <TableCell>{app.follow_up_date ? <FollowUpChip app={app} /> : "-"}</TableCell>
              <TableCell>{app.resume_label || "-"}</TableCell>
              <TableCell align="right"><ActionButtons app={app} onEdit={onEdit} onCheck={onCheck} onDelete={onDelete} /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function Timeline({ refreshKey }) {
  const events = useApi(() => applicationsApi.timeline(), [refreshKey]);
  if (events.loading && !events.data) return <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress /></Box>;
  if (events.error) return <Alert severity="error">{events.error}</Alert>;
  if (!events.data?.length) return <Typography color="text.secondary" align="center" sx={{ py: 6 }}>No activity yet.</Typography>;
  return (
    <Stack spacing={0} sx={{ borderLeft: 2, borderColor: "divider", ml: 1.5 }}>
      {events.data.map((e, i) => (
        <Box key={`${e.application_id}-${i}`} sx={{ pl: 3, pb: 2.5, position: "relative" }}>
          <Box sx={{ position: "absolute", left: -7, top: 4, width: 12, height: 12, borderRadius: "50%", bgcolor: statusColor(e.status) === "default" ? "text.disabled" : `${statusColor(e.status)}.main`, border: 2, borderColor: "background.default" }} />
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            <Chip size="small" color={statusColor(e.status)} label={statusLabel(e.status)} />
            <Typography variant="body2" fontWeight={600}>{e.job_title} at {e.company}</Typography>
          </Stack>
          <Typography variant="caption" color="text.secondary">
            {formatDateTime(e.at)}{e.note ? ` - ${e.note}` : ""}
          </Typography>
        </Box>
      ))}
    </Stack>
  );
}

export default function Applications() {
  const toast = useToast();
  const apps = useApi(() => applicationsApi.list({ limit: 1000 }));
  const resumes = useApi(() => resumesApi.list());
  const [tab, setTab] = useState("kanban");
  const [search, setSearch] = useState("");
  const [dialog, setDialog] = useState({ open: false, app: null });
  const [checkApp, setCheckApp] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [version, setVersion] = useState(0);

  const all = apps.data?.applications || [];
  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return q ? all.filter((a) => `${a.company} ${a.job_title}`.toLowerCase().includes(q)) : all;
  }, [all, search]);

  const refresh = () => {
    apps.reload();
    setVersion((v) => v + 1);
  };

  const move = async (app, status) => {
    if (app.status === status) return;
    try {
      await applicationsApi.changeStatus(app.id, status);
      toast.success(`Moved to ${statusLabel(status)}.`);
      refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await applicationsApi.remove(toDelete.id);
      toast.success("Application deleted.");
      setToDelete(null);
      refresh();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  const handlers = { onMove: move, onEdit: (app) => setDialog({ open: true, app }), onCheck: setCheckApp, onDelete: setToDelete };

  return (
    <AnimatedPage>
      <PageHeader
        title="Applications"
        subtitle="Track every application from Saved to Offer. Kithi records your progress; it never submits an application for you."
        actions={<Button variant="contained" startIcon={<AddOutlined />} onClick={() => setDialog({ open: true, app: null })}>New application</Button>}
      />

      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={2} sx={{ mb: 2 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab value="kanban" label="Kanban" />
          <Tab value="table" label="Table" />
          <Tab value="timeline" label="Timeline" />
        </Tabs>
        {tab !== "timeline" && (
          <TextField size="small" placeholder="Search company or title" value={search} onChange={(e) => setSearch(e.target.value)} InputProps={{ startAdornment: <InputAdornment position="start"><SearchOutlined fontSize="small" /></InputAdornment> }} />
        )}
      </Stack>

      {apps.error && <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={apps.reload}>Retry</Button>}>{apps.error}</Alert>}

      {apps.loading && !apps.data ? (
        <Box sx={{ textAlign: "center", py: 8 }}><CircularProgress /></Box>
      ) : tab === "timeline" ? (
        <Timeline refreshKey={version} />
      ) : all.length === 0 ? (
        <Typography color="text.secondary" align="center" sx={{ py: 8 }}>
          No applications yet. Create one, or use "Track application" on a job from AI Job Search.
        </Typography>
      ) : tab === "kanban" ? (
        <KanbanBoard apps={visible} {...handlers} />
      ) : (
        <ApplicationsTable apps={visible} {...handlers} />
      )}

      <ApplicationDialog
        open={dialog.open}
        application={dialog.app}
        resumes={resumes.data || []}
        onClose={() => setDialog({ open: false, app: null })}
        onSaved={(_, editing) => {
          setDialog({ open: false, app: null });
          toast.success(editing ? "Application updated." : "Application created.");
          refresh();
        }}
      />
      <QualityCheckDialog application={checkApp} onClose={() => setCheckApp(null)} />
      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this application?"
        message={toDelete ? `${toDelete.job_title} at ${toDelete.company} and its history will be permanently deleted.` : ""}
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
      />
    </AnimatedPage>
  );
}
