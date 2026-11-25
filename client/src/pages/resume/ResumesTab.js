import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  LinearProgress,
  Skeleton,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import UploadFileOutlined from "@mui/icons-material/UploadFileOutlined";
import Star from "@mui/icons-material/Star";
import StarBorder from "@mui/icons-material/StarBorder";
import PsychologyOutlined from "@mui/icons-material/PsychologyOutlined";
import VisibilityOutlined from "@mui/icons-material/VisibilityOutlined";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import InsertDriveFileOutlined from "@mui/icons-material/InsertDriveFileOutlined";
import ConfirmDialog from "../../components/ConfirmDialog";
import useApi from "../../hooks/useApi";
import { useToast } from "../../context/ToastContext";
import { resumesApi } from "../../services/endpoints";
import { errorMessage, formatBytes, formatDate, scoreColor } from "../../utils/format";

const MAX_MB = 5; // matches the backend default MAX_UPLOAD_MB
const MAX_RESUMES = 20;

export default function ResumesTab() {
  const navigate = useNavigate();
  const toast = useToast();
  const fileRef = useRef(null);
  const { data, loading, error, reload } = useApi(() => resumesApi.list());
  const [progress, setProgress] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [preview, setPreview] = useState(null); // { resume, text, loading, error }

  const resumes = data || [];

  const handleFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const ext = file.name.toLowerCase().split(".").pop();
    if (!["pdf", "docx"].includes(ext)) {
      toast.error("Only PDF and DOCX files are allowed.");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      toast.error(`File is larger than ${MAX_MB} MB.`);
      return;
    }
    setProgress(0);
    try {
      const created = await resumesApi.upload(file, setProgress);
      toast.success(created.warnings?.length ? "Resume uploaded with parsing warnings" : "Resume uploaded and parsed");
      reload();
    } catch (err) {
      toast.error(errorMessage(err, "Upload failed"));
    } finally {
      setProgress(null);
    }
  };

  const makePrimary = async (resume) => {
    setBusyId(resume.id);
    try {
      await resumesApi.setPrimary(resume.id);
      toast.success("Primary resume updated");
      reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    setBusyId(toDelete.id);
    try {
      await resumesApi.remove(toDelete.id);
      toast.success("Resume deleted");
      setToDelete(null);
      reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const openPreview = async (resume) => {
    setPreview({ resume, text: "", loading: true, error: "" });
    try {
      const full = await resumesApi.get(resume.id);
      setPreview({ resume, text: full.text || "", loading: false, error: "" });
    } catch (err) {
      setPreview({ resume, text: "", loading: false, error: errorMessage(err) });
    }
  };

  const uploading = progress !== null;

  return (
    <Box>
      <Card sx={{ mb: 3, borderStyle: "dashed" }}>
        <CardContent>
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }} justifyContent="space-between">
            <Box>
              <Typography variant="subtitle1" fontWeight={600}>
                Upload a resume
              </Typography>
              <Typography variant="body2" color="text.secondary">
                PDF or DOCX, up to {MAX_MB} MB. Text is extracted locally. You can keep up to {MAX_RESUMES} versions.
              </Typography>
            </Box>
            <Button
              variant="contained"
              startIcon={<UploadFileOutlined />}
              disabled={uploading || resumes.length >= MAX_RESUMES}
              onClick={() => fileRef.current?.click()}
            >
              {uploading ? "Uploading..." : "Choose file"}
            </Button>
            <input ref={fileRef} type="file" hidden accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={handleFile} />
          </Stack>
          {uploading && (
            <Box sx={{ mt: 2 }}>
              <LinearProgress variant={progress < 100 ? "determinate" : "indeterminate"} value={progress} />
              <Typography variant="caption" color="text.secondary">
                {progress < 100 ? `Uploading ${progress}%` : "Parsing document..."}
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" size="small" onClick={reload}>Retry</Button>}>
          {error}
        </Alert>
      )}

      {loading && !data ? (
        <Stack spacing={2}>
          <Skeleton variant="rounded" height={92} />
          <Skeleton variant="rounded" height={92} />
        </Stack>
      ) : resumes.length === 0 && !error ? (
        <Typography color="text.secondary" align="center" sx={{ py: 6 }}>
          No resumes yet. Upload one to get started.
        </Typography>
      ) : (
        <Stack spacing={2}>
          {resumes.map((resume) => {
            const score = resume.analysis?.health_score;
            return (
              <Card key={resume.id}>
                <CardContent>
                  <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems={{ md: "center" }}>
                    <InsertDriveFileOutlined color="primary" sx={{ fontSize: 36, display: { xs: "none", md: "block" } }} />
                    <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
                        <Typography variant="subtitle1" fontWeight={600} noWrap sx={{ maxWidth: "100%" }}>
                          {resume.original_filename}
                        </Typography>
                        {resume.is_primary && <Chip size="small" color="primary" label="Primary" />}
                        {score != null && <Chip size="small" color={scoreColor(score)} variant="outlined" label={`Health ${score}/100`} />}
                      </Stack>
                      <Typography variant="body2" color="text.secondary">
                        {resume.file_type?.toUpperCase()} - {formatBytes(resume.size_bytes)} - {resume.page_count} page(s) - {resume.text_length?.toLocaleString()} characters - uploaded {formatDate(resume.created_at)}
                      </Typography>
                      {resume.warnings?.length > 0 && (
                        <Alert severity="warning" sx={{ mt: 1, py: 0 }}>
                          {resume.warnings.join(" ")}
                        </Alert>
                      )}
                    </Box>
                    <Stack direction="row" spacing={0.5} alignItems="center">
                      {busyId === resume.id && <CircularProgress size={20} />}
                      <Tooltip title={resume.is_primary ? "Primary resume" : "Make primary"}>
                        <span>
                          <IconButton disabled={resume.is_primary || busyId === resume.id} onClick={() => makePrimary(resume)} aria-label="Make primary">
                            {resume.is_primary ? <Star color="warning" /> : <StarBorder />}
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Preview extracted text">
                        <IconButton onClick={() => openPreview(resume)} aria-label="Preview extracted text">
                          <VisibilityOutlined />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Analyze with Resume Intelligence">
                        <IconButton onClick={() => navigate(`/resume-intelligence?resume=${resume.id}`)} aria-label="Analyze resume">
                          <PsychologyOutlined />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton color="error" disabled={busyId === resume.id} onClick={() => setToDelete(resume)} aria-label="Delete resume">
                          <DeleteOutline />
                        </IconButton>
                      </Tooltip>
                    </Stack>
                  </Stack>
                </CardContent>
              </Card>
            );
          })}
        </Stack>
      )}

      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this resume?"
        message={`"${toDelete?.original_filename}" and its stored file will be permanently removed.`}
        confirmLabel="Delete"
        loading={busyId === toDelete?.id}
        onConfirm={confirmDelete}
        onClose={() => setToDelete(null)}
      />

      <Dialog open={Boolean(preview)} onClose={() => setPreview(null)} maxWidth="md" fullWidth scroll="paper">
        <DialogTitle>Extracted text{preview ? `: ${preview.resume.original_filename}` : ""}</DialogTitle>
        <DialogContent dividers>
          {preview?.loading && <CircularProgress size={24} />}
          {preview?.error && <Alert severity="error">{preview.error}</Alert>}
          {preview && !preview.loading && !preview.error && (
            <Box component="pre" sx={{ m: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", fontFamily: "ui-monospace, Consolas, monospace", fontSize: 13 }}>
              {preview.text || "(No text could be extracted.)"}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPreview(null)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
