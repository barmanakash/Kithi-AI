import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  Grid,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import DownloadOutlined from "@mui/icons-material/DownloadOutlined";
import PageHeader from "../components/PageHeader";
import ConfirmDialog from "../components/ConfirmDialog";
import useApi from "../hooks/useApi";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { accountApi, aiApi, authApi, healthApi } from "../services/endpoints";
import { errorMessage, formatDate } from "../utils/format";
import { passwordProblem } from "./Register";

function AiSection() {
  const toast = useToast();
  const { data, loading, error, reload } = useApi(() => aiApi.status());
  const [pinging, setPinging] = useState(false);
  const [pingResult, setPingResult] = useState(null);

  const ping = async () => {
    setPinging(true);
    setPingResult(null);
    try {
      const result = await aiApi.ping();
      setPingResult({ ok: Boolean(result.ok), message: result.message || "" });
    } catch (err) {
      setPingResult({ ok: false, message: errorMessage(err, "AI test failed") });
    } finally {
      setPinging(false);
    }
  };

  const ready = data?.reachable && data?.model_available;

  return (
    <Card>
      <CardHeader
        title="Local AI (Ollama)"
        subheader="All inference runs on this machine. No external AI services are used."
        action={
          <Button size="small" startIcon={<RefreshIcon />} onClick={reload} disabled={loading}>
            Refresh
          </Button>
        }
      />
      <CardContent sx={{ pt: 0 }}>
        {loading && !data ? (
          <Skeleton variant="rounded" height={80} />
        ) : error ? (
          <Alert severity="error">{error}</Alert>
        ) : (
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip size="small" color={data.reachable ? "success" : "error"} label={data.reachable ? "Ollama reachable" : "Ollama offline"} />
              <Chip size="small" color={data.model_available ? "success" : "warning"} label={data.model_available ? "Model installed" : "Model missing"} />
            </Stack>
            <Typography variant="body2" color="text.secondary">
              Endpoint: {data.endpoint} - Model: {data.model}
            </Typography>
            {!ready && <Alert severity="warning">{data.message}</Alert>}
            {data.installed_models?.length > 0 && (
              <Typography variant="caption" color="text.secondary">
                Installed models: {data.installed_models.join(", ")}
              </Typography>
            )}
            <Box>
              <Button variant="outlined" onClick={ping} disabled={!ready || pinging}>
                {pinging ? "Testing..." : "Test AI pipeline"}
              </Button>
              {pingResult && (
                <Alert severity={pingResult.ok ? "success" : "warning"} sx={{ mt: 2 }}>
                  {pingResult.ok ? "The local model responded with valid structured output." : "The model responded, but the test did not pass."}
                  {pingResult.message ? ` ${pingResult.message}` : ""}
                </Alert>
              )}
            </Box>
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}

function BackendSection() {
  const { data, loading, error } = useApi(() => healthApi.get());
  return (
    <Card>
      <CardHeader title="Backend" />
      <CardContent sx={{ pt: 0 }}>
        {loading && !data ? (
          <Skeleton variant="rounded" height={48} />
        ) : error ? (
          <Alert severity="error">{error}</Alert>
        ) : (
          <Stack spacing={1}>
            <Stack direction="row" spacing={1}>
              <Chip size="small" color={data.status === "ok" ? "success" : "warning"} label={data.status === "ok" ? "Healthy" : "Degraded"} />
              <Chip size="small" color={data.database?.connected ? "success" : "error"} label={data.database?.connected ? "MongoDB connected" : "MongoDB unavailable"} />
            </Stack>
            <Typography variant="body2" color="text.secondary">
              {data.app} v{data.version} - {data.environment} - database "{data.database?.name}"
            </Typography>
          </Stack>
        )}
      </CardContent>
    </Card>
  );
}

function PasswordSection() {
  const toast = useToast();
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const nextProblem = form.next ? passwordProblem(form.next) : "";
  const mismatch = form.confirm && form.confirm !== form.next;
  const valid = form.current && form.next && !nextProblem && form.confirm === form.next;

  const submit = async (event) => {
    event.preventDefault();
    if (!valid) return;
    setError("");
    setSaving(true);
    try {
      await authApi.changePassword({ current_password: form.current, new_password: form.next });
      setForm({ current: "", next: "", confirm: "" });
      toast.success("Password changed");
    } catch (err) {
      setError(errorMessage(err, "Could not change the password"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader title="Change password" />
      <CardContent sx={{ pt: 0 }}>
        <form onSubmit={submit} noValidate>
          <Stack spacing={2} sx={{ maxWidth: 420 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField size="small" type="password" label="Current password" autoComplete="current-password" value={form.current} onChange={set("current")} />
            <TextField
              size="small"
              type="password"
              label="New password"
              autoComplete="new-password"
              value={form.next}
              onChange={set("next")}
              error={Boolean(nextProblem)}
              helperText={nextProblem || "At least 8 characters, with letters and numbers."}
            />
            <TextField
              size="small"
              type="password"
              label="Confirm new password"
              autoComplete="new-password"
              value={form.confirm}
              onChange={set("confirm")}
              error={Boolean(mismatch)}
              helperText={mismatch ? "Passwords do not match." : " "}
            />
            <Box>
              <Button type="submit" variant="contained" disabled={!valid || saving}>
                {saving ? "Saving..." : "Update password"}
              </Button>
            </Box>
          </Stack>
        </form>
      </CardContent>
    </Card>
  );
}

function DataSection() {
  const toast = useToast();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [exporting, setExporting] = useState(false);
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const exportData = async () => {
    setExporting(true);
    try {
      const payload = await accountApi.exportData();
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `kithi-data-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success("Your data export has been downloaded");
    } catch (err) {
      toast.error(errorMessage(err, "Export failed"));
    } finally {
      setExporting(false);
    }
  };

  const close = () => {
    if (deleting) return;
    setOpen(false);
    setPassword("");
    setConfirmText("");
    setDeleteError("");
  };

  const deleteAccount = async () => {
    setDeleting(true);
    setDeleteError("");
    try {
      await accountApi.remove({ password, confirm: confirmText });
      logout();
      navigate("/login", { replace: true });
    } catch (err) {
      setDeleteError(errorMessage(err, "Could not delete the account"));
      setDeleting(false);
    }
  };

  return (
    <Card>
      <CardHeader title="Your data" subheader="Your data belongs to you. Export it or erase it at any time." />
      <CardContent sx={{ pt: 0 }}>
        <Stack spacing={2}>
          <Box>
            <Button variant="outlined" startIcon={<DownloadOutlined />} onClick={exportData} disabled={exporting}>
              {exporting ? "Preparing export..." : "Download all my data (JSON)"}
            </Button>
          </Box>
          <Divider />
          <Box>
            <Typography variant="subtitle2" color="error" sx={{ mb: 0.5 }}>
              Danger zone
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
              Permanently deletes your account, profile, resumes, stored files and all related records. This cannot be undone.
            </Typography>
            <Button color="error" variant="outlined" onClick={() => setOpen(true)}>
              Delete my account
            </Button>
          </Box>
        </Stack>
      </CardContent>

      <ConfirmDialog
        open={open}
        title="Delete your account permanently?"
        message='Enter your password and type DELETE to confirm.'
        confirmLabel="Delete everything"
        loading={deleting}
        onConfirm={deleteAccount}
        onClose={close}
      >
        <Stack spacing={2} sx={{ mt: 2 }}>
          {deleteError && <Alert severity="error">{deleteError}</Alert>}
          <TextField size="small" type="password" label="Password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} fullWidth />
          <TextField size="small" label='Type "DELETE"' value={confirmText} onChange={(e) => setConfirmText(e.target.value)} fullWidth />
        </Stack>
      </ConfirmDialog>
    </Card>
  );
}

export default function Settings() {
  const { user } = useAuth();
  return (
    <>
      <PageHeader title="Settings" subtitle="Account, local AI and privacy controls." />
      <Grid container spacing={2.5}>
        <Grid item xs={12}>
          <Card>
            <CardHeader title="Account" />
            <CardContent sx={{ pt: 0 }}>
              <Typography variant="body1">{user?.full_name}</Typography>
              <Typography variant="body2" color="text.secondary">
                {user?.email} - member since {formatDate(user?.created_at)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} lg={6}>
          <AiSection />
        </Grid>
        <Grid item xs={12} lg={6}>
          <Stack spacing={2.5}>
            <BackendSection />
            <PasswordSection />
          </Stack>
        </Grid>
        <Grid item xs={12}>
          <DataSection />
        </Grid>
      </Grid>
    </>
  );
}
