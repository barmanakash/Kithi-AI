import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  IconButton,
  Skeleton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import AutoAwesomeOutlined from "@mui/icons-material/AutoAwesomeOutlined";
import ArticleOutlined from "@mui/icons-material/ArticleOutlined";
import MailOutline from "@mui/icons-material/MailOutline";
import VisibilityOutlined from "@mui/icons-material/VisibilityOutlined";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import ConfirmDialog from "../../components/ConfirmDialog";
import GenerateDialog from "../../components/GenerateDialog";
import VersionDialog from "../../components/VersionDialog";
import useApi from "../../hooks/useApi";
import { useToast } from "../../context/ToastContext";
import { generateApi } from "../../services/endpoints";
import { errorMessage, formatDate } from "../../utils/format";

export default function GeneratedTab({ initialOpenId = null }) {
  const toast = useToast();
  const { data, loading, error, reload } = useApi(() => generateApi.list({ limit: 100 }));
  const [generating, setGenerating] = useState(false);
  const [openId, setOpenId] = useState(initialOpenId);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const versions = data?.versions || [];

  const confirmDelete = async () => {
    setDeleting(true);
    try {
      await generateApi.remove(toDelete.id);
      toast.success("Draft deleted");
      setToDelete(null);
      reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Box>
      <Card sx={{ mb: 3, borderStyle: "dashed" }}>
        <CardContent>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }} justifyContent="space-between">
            <Box>
              <Typography variant="subtitle1" fontWeight={600}>Tailored resumes and cover letters</Typography>
              <Typography variant="body2" color="text.secondary">
                Generated from your verified profile and resume for a specific saved job. Nothing is invented, and nothing is sent for you.
              </Typography>
            </Box>
            <Button variant="contained" startIcon={<AutoAwesomeOutlined />} onClick={() => setGenerating(true)}>
              Generate
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={reload}>Retry</Button>}>
          {error}
        </Alert>
      )}

      {loading && !data ? (
        <Stack spacing={2}>
          <Skeleton variant="rounded" height={84} />
          <Skeleton variant="rounded" height={84} />
        </Stack>
      ) : versions.length === 0 && !error ? (
        <Typography color="text.secondary" align="center" sx={{ py: 6 }}>
          No generated documents yet. Save a job, then generate a tailored resume or cover letter for it.
        </Typography>
      ) : (
        <Stack spacing={2}>
          {versions.map((v) => (
            <Card key={v.id}>
              <CardContent>
                <Stack direction="row" spacing={2} alignItems="center">
                  {v.kind === "cover_letter" ? <MailOutline color="primary" sx={{ fontSize: 32 }} /> : <ArticleOutlined color="primary" sx={{ fontSize: 32 }} />}
                  <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                    <Typography variant="subtitle1" fontWeight={600} noWrap>{v.title}</Typography>
                    <Stack direction="row" gap={0.5} flexWrap="wrap" alignItems="center" sx={{ mt: 0.5 }}>
                      <Chip size="small" label={v.kind === "cover_letter" ? "Cover letter" : "Tailored resume"} />
                      <Chip size="small" variant="outlined" color={v.source === "ai" ? "success" : "default"} label={v.source === "ai" ? "AI, fact-checked" : "Template"} />
                      {v.edited && <Chip size="small" variant="outlined" label="Edited" />}
                      {v.warnings?.length > 0 && <Chip size="small" variant="outlined" color="warning" label={`${v.warnings.length} note(s)`} />}
                      <Typography variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>{formatDate(v.created_at)}</Typography>
                    </Stack>
                  </Box>
                  <Stack direction="row" spacing={0.5}>
                    <Tooltip title="Open, edit or export">
                      <IconButton onClick={() => setOpenId(v.id)} aria-label="Open draft"><VisibilityOutlined /></IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton color="error" onClick={() => setToDelete(v)} aria-label="Delete draft"><DeleteOutline /></IconButton>
                    </Tooltip>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          ))}
        </Stack>
      )}

      <GenerateDialog
        open={generating}
        onClose={() => setGenerating(false)}
        onCreated={(version) => {
          setGenerating(false);
          toast.success("Draft created. Review it before you use it.");
          reload();
          setOpenId(version.id);
        }}
      />
      <VersionDialog versionId={openId} onClose={() => setOpenId(null)} onChanged={reload} />
      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this draft?"
        message={`"${toDelete?.title}" will be permanently removed.`}
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
      />
    </Box>
  );
}
