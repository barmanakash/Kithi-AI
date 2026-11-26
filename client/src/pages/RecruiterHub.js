import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
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
import AutoAwesomeOutlined from "@mui/icons-material/AutoAwesomeOutlined";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import EditOutlined from "@mui/icons-material/EditOutlined";
import ForumOutlined from "@mui/icons-material/ForumOutlined";
import SearchOutlined from "@mui/icons-material/SearchOutlined";
import PageHeader from "../components/PageHeader";
import AnimatedPage from "../components/AnimatedPage";
import ConfirmDialog from "../components/ConfirmDialog";
import RecruiterDialog from "../components/recruiter/RecruiterDialog";
import GenerateMessageDialog, { KIND_LABELS } from "../components/recruiter/GenerateMessageDialog";
import MessageDialog from "../components/recruiter/MessageDialog";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { recruiterMessagesApi, recruitersApi } from "../services/endpoints";
import { errorMessage, formatDateTime } from "../utils/format";

const STATUS_COLOR = { draft: "default", approved: "info", sent: "success" };
const STATUS_LABEL = { draft: "Draft", approved: "Approved", sent: "Sent" };

function MessagesTab({ onNew, refreshKey, onChanged }) {
  const toast = useToast();
  const [status, setStatus] = useState("");
  const messages = useApi(() => recruiterMessagesApi.list({ status: status || undefined, limit: 200 }), [status, refreshKey]);
  const [openId, setOpenId] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const items = messages.data?.items || [];

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await recruiterMessagesApi.remove(toDelete.id);
      toast.success("Message deleted.");
      setToDelete(null);
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <TextField select size="small" label="Status" value={status} onChange={(e) => setStatus(e.target.value)} sx={{ minWidth: 160 }}>
          <MenuItem value="">All</MenuItem>
          {Object.entries(STATUS_LABEL).map(([v, l]) => <MenuItem key={v} value={v}>{l}</MenuItem>)}
        </TextField>
        <Typography variant="body2" color="text.secondary">{messages.data?.total ?? 0} message(s)</Typography>
        <span style={{ flexGrow: 1 }} />
        <Button variant="contained" startIcon={<AutoAwesomeOutlined />} onClick={() => onNew()}>Draft a message</Button>
      </Stack>

      {messages.error && <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={messages.reload}>Retry</Button>}>{messages.error}</Alert>}

      {messages.loading && !messages.data ? (
        <Box sx={{ textAlign: "center", py: 6 }}><CircularProgress /></Box>
      ) : items.length ? (
        <Stack spacing={2}>
          {items.map((m) => (
            <Card key={m.id} variant="outlined">
              <Stack direction="row" alignItems="stretch">
                <CardActionArea onClick={() => setOpenId(m.id)} sx={{ flexGrow: 1 }}>
                  <CardContent>
                    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 0.5 }}>
                      <Chip size="small" color={STATUS_COLOR[m.status]} label={STATUS_LABEL[m.status]} />
                      <Chip size="small" variant="outlined" label={m.channel === "email" ? "Email" : "LinkedIn"} />
                      <Chip size="small" variant="outlined" label={m.source === "ai" ? "AI draft" : "Template"} />
                    </Stack>
                    <Typography variant="subtitle2">{KIND_LABELS[m.kind] || m.kind}{m.recruiter_name ? ` - ${m.recruiter_name}` : ""}{m.company ? ` (${m.company})` : ""}</Typography>
                    <Typography variant="body2" color="text.secondary" noWrap>{m.subject || (m.body || "").split("\n").find((l) => l.trim() && !/^(hello|hi)\b/i.test(l)) || ""}</Typography>
                    <Typography variant="caption" color="text.secondary">Updated {formatDateTime(m.updated_at)}</Typography>
                  </CardContent>
                </CardActionArea>
                <Box sx={{ p: 1 }}>
                  <Tooltip title="Delete"><IconButton size="small" onClick={() => setToDelete(m)} aria-label="Delete message"><DeleteOutline fontSize="small" /></IconButton></Tooltip>
                </Box>
              </Stack>
            </Card>
          ))}
        </Stack>
      ) : (
        <Typography color="text.secondary" align="center" sx={{ py: 6 }}>
          No messages yet. Draft one, review it, and approve it before you send it yourself.
        </Typography>
      )}

      <MessageDialog messageId={openId} onClose={() => setOpenId(null)} onChanged={onChanged} />
      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this message?"
        message="The message and its history will be permanently deleted."
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
      />
    </>
  );
}

function ContactsTab({ onDraft, refreshKey, onChanged }) {
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const contacts = useApi(() => recruitersApi.list({ q: q || undefined, limit: 200 }), [q, refreshKey]);
  const [dialog, setDialog] = useState({ open: false, recruiter: null });
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const items = contacts.data?.items || [];

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await recruitersApi.remove(toDelete.id);
      toast.success("Contact deleted. Existing messages were kept.");
      setToDelete(null);
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 2 }} component="form" onSubmit={(e) => { e.preventDefault(); setQ(search.trim()); }}>
        <TextField size="small" placeholder="Search name, company or email" value={search} onChange={(e) => setSearch(e.target.value)} InputProps={{ startAdornment: <InputAdornment position="start"><SearchOutlined fontSize="small" /></InputAdornment> }} sx={{ minWidth: 280 }} />
        <Button type="submit" size="small">Search</Button>
        <span style={{ flexGrow: 1 }} />
        <Button variant="contained" startIcon={<AddOutlined />} onClick={() => setDialog({ open: true, recruiter: null })}>New contact</Button>
      </Stack>

      {contacts.error && <Alert severity="error" sx={{ mb: 2 }}>{contacts.error}</Alert>}

      {contacts.loading && !contacts.data ? (
        <Box sx={{ textAlign: "center", py: 6 }}><CircularProgress /></Box>
      ) : items.length ? (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Company</TableCell>
                <TableCell>Email</TableCell>
                <TableCell align="right">Messages</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((r) => (
                <TableRow key={r.id} hover>
                  <TableCell>{r.name}{r.title ? <Typography variant="caption" color="text.secondary" display="block">{r.title}</Typography> : null}</TableCell>
                  <TableCell>{r.company || "-"}</TableCell>
                  <TableCell>{r.email || "-"}</TableCell>
                  <TableCell align="right">{r.message_count}</TableCell>
                  <TableCell align="right">
                    <Tooltip title="Draft a message to this contact"><IconButton size="small" onClick={() => onDraft(r)} aria-label="Draft a message"><ForumOutlined fontSize="small" /></IconButton></Tooltip>
                    <Tooltip title="Edit"><IconButton size="small" onClick={() => setDialog({ open: true, recruiter: r })} aria-label="Edit contact"><EditOutlined fontSize="small" /></IconButton></Tooltip>
                    <Tooltip title="Delete"><IconButton size="small" onClick={() => setToDelete(r)} aria-label="Delete contact"><DeleteOutline fontSize="small" /></IconButton></Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : (
        <Typography color="text.secondary" align="center" sx={{ py: 6 }}>
          {q ? "No contacts match that search." : "No contacts yet. Add the recruiters and hiring contacts you want to write to."}
        </Typography>
      )}

      <RecruiterDialog
        open={dialog.open}
        recruiter={dialog.recruiter}
        onClose={() => setDialog({ open: false, recruiter: null })}
        onSaved={(_, editing) => {
          setDialog({ open: false, recruiter: null });
          toast.success(editing ? "Contact updated." : "Contact added.");
          onChanged();
        }}
      />
      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this contact?"
        message={toDelete ? `${toDelete.name} will be removed. Messages you already drafted to them are kept.` : ""}
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
      />
    </>
  );
}

export default function RecruiterHub() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState("messages");
  const [version, setVersion] = useState(0);
  const [gen, setGen] = useState({ open: false, initial: null });
  const [openNew, setOpenNew] = useState(null);
  const bump = () => setVersion((v) => v + 1);

  // Coming from Applications ("Draft a message"): open the drafting dialog for that application.
  useEffect(() => {
    const application = params.get("application");
    if (application) {
      setGen({ open: true, initial: { application_id: application, kind: "follow_up" } });
      setParams({}, { replace: true });
    }
  }, [params, setParams]);

  return (
    <AnimatedPage>
      <PageHeader
        title="Recruiter Hub"
        subtitle="Draft recruiter messages, referral requests and follow-ups from your verified profile. Nothing leaves Kithi: you approve each message, then send it yourself."
      />

      <Alert severity="info" sx={{ mb: 3 }}>
        Kithi never sends messages for you. After you approve a message you can open it in your own email app, or copy it into LinkedIn, and send it there.
      </Alert>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab value="messages" label="Messages" />
        <Tab value="contacts" label="Contacts" />
      </Tabs>

      {tab === "messages" ? (
        <MessagesTab onNew={() => setGen({ open: true, initial: null })} refreshKey={version} onChanged={bump} />
      ) : (
        <ContactsTab onDraft={(r) => setGen({ open: true, initial: { recruiter_id: r.id } })} refreshKey={version} onChanged={bump} />
      )}

      <GenerateMessageDialog
        open={gen.open}
        initial={gen.initial}
        onClose={() => setGen({ open: false, initial: null })}
        onCreated={(message) => {
          setGen({ open: false, initial: null });
          setTab("messages");
          bump();
          setOpenNew(message.id);
          toast.success(message.source === "ai" ? "Draft ready. Review it before approving." : "Draft ready from a template. Review it before approving.");
        }}
      />
      <MessageDialog messageId={openNew} onClose={() => setOpenNew(null)} onChanged={bump} />
    </AnimatedPage>
  );
}
