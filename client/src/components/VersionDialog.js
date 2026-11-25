import { useEffect, useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ExpandMoreOutlined from "@mui/icons-material/ExpandMoreOutlined";
import ContentCopyOutlined from "@mui/icons-material/ContentCopyOutlined";
import FileDownloadOutlined from "@mui/icons-material/FileDownloadOutlined";
import SaveOutlined from "@mui/icons-material/SaveOutlined";
import AddTaskOutlined from "@mui/icons-material/AddTaskOutlined";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { applicationsApi, generateApi } from "../services/endpoints";
import { errorMessage, formatDateTime } from "../utils/format";

const COVER_NOTE_MAX = 5000; // matches the backend Application.cover_note limit

async function readableError(err, fallback) {
  const body = err?.response?.data;
  if (body instanceof Blob) {
    try {
      const parsed = JSON.parse(await body.text());
      if (typeof parsed.detail === "string") return parsed.detail;
    } catch {
      /* fall through */
    }
    return fallback;
  }
  return errorMessage(err, fallback);
}

/** View, edit and export one saved draft (tailored resume or cover letter). */
export default function VersionDialog({ versionId, onClose, onChanged }) {
  const toast = useToast();
  const detail = useApi(() => (versionId ? generateApi.get(versionId) : Promise.resolve(null)), [versionId]);
  const version = detail.data;
  const isLetter = version?.kind === "cover_letter";

  const [summary, setSummary] = useState("");
  const [letter, setLetter] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    if (!version) return;
    setSummary(version.content?.summary || "");
    setLetter(version.text || "");
  }, [version]);

  const dirty = version && (isLetter ? letter !== version.text : summary !== (version.content?.summary || ""));

  const save = async () => {
    setBusy("save");
    try {
      await generateApi.update(versionId, isLetter ? { text: letter } : { summary });
      toast.success("Changes saved");
      await detail.reload();
      onChanged?.();
      return true;
    } catch (err) {
      toast.error(errorMessage(err));
      return false;
    } finally {
      setBusy("");
    }
  };

  const copy = async () => {
    const text = isLetter ? letter : version.text;
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Could not copy. Select the text and copy it manually.");
    }
  };

  const download = async () => {
    if (dirty && !(await save())) return;
    setBusy("export");
    try {
      const blob = await generateApi.exportDocx(versionId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const slug = (version.title || "document").replace(/[^A-Za-z0-9._-]+/g, "_").slice(0, 60);
      link.href = url;
      link.download = `${isLetter ? "CoverLetter" : "Resume"}_${slug}.docx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(await readableError(err, "Could not export the document"));
    } finally {
      setBusy("");
    }
  };

  const saveAsCoverNote = async () => {
    if (dirty && !(await save())) return;
    const text = (isLetter ? letter : version.text).trim();
    if (text.length > COVER_NOTE_MAX) {
      toast.error(`A cover note can hold ${COVER_NOTE_MAX} characters. Shorten the letter first.`);
      return;
    }
    setBusy("note");
    try {
      const res = await applicationsApi.fromJob(version.job_id);
      await applicationsApi.update(res.application.id, { cover_note: text });
      toast.success(`Saved as the cover note on your ${version.company} application.`);
    } catch (err) {
      toast.error(errorMessage(err, "Could not attach the letter to an application"));
    } finally {
      setBusy("");
    }
  };

  const changes = version?.content?.bullet_changes || [];
  const gaps = version?.content?.keyword_gaps || [];
  const removed = version?.removed_sentences || [];

  return (
    <Dialog open={Boolean(versionId)} onClose={busy ? undefined : onClose} maxWidth="md" fullWidth scroll="paper">
      <DialogTitle>{version ? version.title : "Generated document"}</DialogTitle>
      <DialogContent dividers>
        {detail.loading && !version && <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress /></Box>}
        {detail.error && <Alert severity="error">{detail.error}</Alert>}
        {version && (
          <Stack spacing={2}>
            <Stack direction="row" gap={1} flexWrap="wrap" alignItems="center">
              <Chip size="small" color="primary" label={isLetter ? "Cover letter" : "Tailored resume"} />
              <Chip
                size="small"
                variant="outlined"
                color={version.source === "ai" ? "success" : "default"}
                label={version.source === "ai" ? "Local AI, fact-checked" : "Template from your verified facts"}
              />
              {version.edited && <Chip size="small" variant="outlined" label="Edited by you" />}
              <Typography variant="caption" color="text.secondary">Created {formatDateTime(version.created_at)}</Typography>
            </Stack>

            {(version.warnings || []).map((w) => (
              <Alert key={w} severity="warning">{w}</Alert>
            ))}

            {isLetter ? (
              <TextField
                label="Cover letter"
                value={letter}
                onChange={(e) => setLetter(e.target.value)}
                multiline
                minRows={14}
                fullWidth
                helperText={`${letter.length.toLocaleString()} characters. Review and edit before you use it.`}
              />
            ) : (
              <>
                <TextField
                  label="Professional summary"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  multiline
                  minRows={3}
                  fullWidth
                  helperText="Edit freely. Keep it to claims that are true for you."
                />
                <Box>
                  <Typography variant="subtitle2" gutterBottom>Resume preview</Typography>
                  <Box
                    component="pre"
                    sx={{ m: 0, p: 2, border: 1, borderColor: "divider", borderRadius: 1, whiteSpace: "pre-wrap", wordBreak: "break-word", fontFamily: "ui-monospace, Consolas, monospace", fontSize: 13, maxHeight: 360, overflow: "auto" }}
                  >
                    {version.text}
                  </Box>
                </Box>
              </>
            )}

            {gaps.length > 0 && (
              <Alert severity="info">
                The job asks for skills that are not in your profile or resume, so they were <strong>not</strong> added: {gaps.join(", ")}.
                Add them to your profile only if you genuinely have them.
              </Alert>
            )}

            {changes.length > 0 && (
              <Accordion variant="outlined" disableGutters>
                <AccordionSummary expandIcon={<ExpandMoreOutlined />}>
                  <Typography variant="body2">{changes.length} bullet(s) reworded. Compare with your original wording.</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Stack spacing={2}>
                    {changes.map((c, i) => (
                      <Box key={i}>
                        <Typography variant="caption" color="text.secondary">{c.role}</Typography>
                        <Typography variant="body2" color="text.secondary">Before: {c.original}</Typography>
                        <Typography variant="body2">After: {c.improved}</Typography>
                      </Box>
                    ))}
                  </Stack>
                </AccordionDetails>
              </Accordion>
            )}

            {removed.length > 0 && (
              <Accordion variant="outlined" disableGutters>
                <AccordionSummary expandIcon={<ExpandMoreOutlined />}>
                  <Typography variant="body2">{removed.length} AI-written sentence(s) removed by the fact check</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Stack spacing={1.5}>
                    {removed.map((r, i) => (
                      <Box key={i}>
                        <Typography variant="body2" color="text.secondary">"{r.sentence}"</Typography>
                        <Typography variant="caption" color="warning.main">{r.reasons.join("; ")}</Typography>
                      </Box>
                    ))}
                  </Stack>
                </AccordionDetails>
              </Accordion>
            )}

            <Typography variant="caption" color="text.secondary">
              This is a draft for you to review. Kithi never sends or submits anything for you.
            </Typography>
          </Stack>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2, flexWrap: "wrap", gap: 1 }}>
        <Button onClick={copy} disabled={!version || Boolean(busy)} startIcon={<ContentCopyOutlined />}>Copy</Button>
        <Button onClick={download} disabled={!version || Boolean(busy)} startIcon={busy === "export" ? <CircularProgress size={16} /> : <FileDownloadOutlined />}>
          Download .docx
        </Button>
        {isLetter && (
          <Button onClick={saveAsCoverNote} disabled={!version || Boolean(busy)} startIcon={busy === "note" ? <CircularProgress size={16} /> : <AddTaskOutlined />}>
            Save as application cover note
          </Button>
        )}
        <span style={{ flexGrow: 1 }} />
        <Button onClick={save} disabled={!dirty || Boolean(busy)} variant="outlined" startIcon={busy === "save" ? <CircularProgress size={16} /> : <SaveOutlined />}>
          Save changes
        </Button>
        <Button onClick={onClose} disabled={Boolean(busy)} variant="contained">Close</Button>
      </DialogActions>
    </Dialog>
  );
}
