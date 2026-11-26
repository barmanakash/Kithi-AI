import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControlLabel,
  Stack,
  Step,
  StepLabel,
  Stepper,
  TextField,
  Typography,
} from "@mui/material";
import ContentCopyOutlined from "@mui/icons-material/ContentCopyOutlined";
import MailOutline from "@mui/icons-material/MailOutline";
import ConfirmDialog from "../ConfirmDialog";
import useApi from "../../hooks/useApi";
import { useToast } from "../../context/ToastContext";
import { recruiterMessagesApi } from "../../services/endpoints";
import { errorMessage, formatDateTime } from "../../utils/format";
import { KIND_LABELS } from "./GenerateMessageDialog";

const STEPS = ["draft", "approved", "sent"];
const STEP_LABELS = { draft: "Draft", approved: "Approved by you", sent: "Sent by you" };

/**
 * Review, edit, approve and send a message.
 * Kithi never sends anything: after approval it can open YOUR email app with the text filled in,
 * and "I sent it" only records that you did.
 */
export default function MessageDialog({ messageId, onClose, onChanged }) {
  const toast = useToast();
  const detail = useApi(() => (messageId ? recruiterMessagesApi.get(messageId) : Promise.resolve(null)), [messageId]);
  const [msg, setMsg] = useState(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState("");
  const [showRemoved, setShowRemoved] = useState(false);
  const [confirmSent, setConfirmSent] = useState(false);

  const load = (m) => {
    setMsg(m);
    setSubject(m.subject || "");
    setBody(m.body || "");
    setAgree(false);
  };

  useEffect(() => {
    if (detail.data) load(detail.data);
    else if (!messageId) setMsg(null);
  }, [detail.data, messageId]);

  const dirty = msg && (subject !== (msg.subject || "") || body !== (msg.body || ""));
  const frozen = msg?.status === "sent";

  const run = async (name, fn, success) => {
    setBusy(name);
    try {
      const res = await fn();
      if (res && res.id) {
        load(res);
        onChanged();
      }
      if (success) toast.success(success);
      return res;
    } catch (err) {
      toast.error(errorMessage(err));
      return null;
    } finally {
      setBusy("");
    }
  };

  const save = () =>
    run("save", () => recruiterMessagesApi.edit(msg.id, { subject, body }), msg.status === "approved" ? "Saved. Your approval was cleared, so approve it again." : "Saved.");
  const approve = () => run("approve", () => recruiterMessagesApi.approve(msg.id), "Approved. You can now open it in your email app.");
  const markSent = async () => {
    setConfirmSent(false);
    await run("sent", () => recruiterMessagesApi.markSent(msg.id), "Recorded as sent.");
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(msg.channel === "email" && subject ? `Subject: ${subject}\n\n${body}` : body);
      toast.success("Copied to clipboard.");
    } catch {
      toast.error("Could not copy. Select the text and copy it manually.");
    }
  };

  const openEmail = async () => {
    setBusy("mailto");
    try {
      const res = await recruiterMessagesApi.mailto(msg.id);
      if (res.too_long) toast.info(res.note);
      window.location.href = res.url; // opens your own email app; you press send there
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy("");
    }
  };

  const open = Boolean(messageId);
  const removed = msg?.removed_sentences || [];

  return (
    <>
      <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="md" fullWidth>
        <DialogTitle>
          {msg ? KIND_LABELS[msg.kind] || "Message" : "Message"}
          {msg && (
            <Stack direction="row" spacing={1} sx={{ mt: 1 }} flexWrap="wrap" useFlexGap>
              <Chip size="small" label={msg.channel === "email" ? "Email" : "LinkedIn"} variant="outlined" />
              <Chip size="small" color={msg.source === "ai" ? "primary" : "default"} variant="outlined" label={msg.source === "ai" ? "AI draft, fact-checked" : "Template from your verified facts"} />
              {msg.recruiter_name && <Chip size="small" variant="outlined" label={`To: ${msg.recruiter_name}`} />}
            </Stack>
          )}
        </DialogTitle>
        <DialogContent dividers>
          {detail.loading && !msg && <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress /></Box>}
          {detail.error && <Alert severity="error">{detail.error}</Alert>}
          {msg && (
            <Stack spacing={2.5}>
              <Stepper activeStep={STEPS.indexOf(msg.status) + (msg.status === "sent" ? 1 : 0)} alternativeLabel>
                {STEPS.map((s) => <Step key={s}><StepLabel>{STEP_LABELS[s]}</StepLabel></Step>)}
              </Stepper>

              {(msg.warnings || []).map((w) => <Alert key={w} severity="warning" variant="outlined">{w}</Alert>)}

              {removed.length > 0 && (
                <Box>
                  <Button size="small" onClick={() => setShowRemoved((v) => !v)}>{showRemoved ? "Hide" : "Show"} {removed.length} sentence(s) removed by the fact-check</Button>
                  <Collapse in={showRemoved}>
                    <Stack spacing={1} sx={{ mt: 1 }}>
                      {removed.map((r, i) => (
                        <Box key={i} sx={{ p: 1.5, border: 1, borderColor: "divider", borderRadius: 2 }}>
                          <Typography variant="body2">"{r.sentence}"</Typography>
                          <Typography variant="caption" color="text.secondary">Removed: {r.reasons.join("; ")}</Typography>
                        </Box>
                      ))}
                    </Stack>
                  </Collapse>
                </Box>
              )}

              {msg.channel === "email" && (
                <TextField label="Subject" value={subject} onChange={(e) => setSubject(e.target.value)} fullWidth disabled={frozen} inputProps={{ maxLength: 200 }} />
              )}
              <TextField label="Message" value={body} onChange={(e) => setBody(e.target.value)} fullWidth multiline minRows={10} maxRows={22} disabled={frozen} inputProps={{ maxLength: 8000 }} />

              {dirty && !frozen && (
                <Alert severity={msg.status === "approved" ? "warning" : "info"}>
                  {msg.status === "approved" ? "Saving your changes will clear the approval, so you can approve the new text." : "You have unsaved changes."}
                </Alert>
              )}

              <Divider />

              {msg.status === "draft" && (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>Approve this exact text</Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    Approval unlocks opening the message in your email app. It applies only to the text above, so any later edit clears it.
                  </Typography>
                  <FormControlLabel control={<Checkbox checked={agree} onChange={(e) => setAgree(e.target.checked)} disabled={dirty} />} label="I have read this message and approve it" />
                  {dirty && <Typography variant="caption" color="text.secondary" display="block">Save your edits before approving.</Typography>}
                </Box>
              )}

              {msg.status === "approved" && (
                <Alert severity="success">
                  Approved{msg.approved_at ? ` on ${formatDateTime(msg.approved_at)}` : ""}. Kithi does not send messages. Open it in your email app, or copy it, and send it yourself. Then record it as sent.
                </Alert>
              )}
              {msg.status === "sent" && <Alert severity="info">Recorded as sent{msg.sent_at ? ` on ${formatDateTime(msg.sent_at)}` : ""}. Sent messages cannot be edited.</Alert>}
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2, flexWrap: "wrap", gap: 1 }}>
          <Button startIcon={<ContentCopyOutlined />} onClick={copy} disabled={!msg}>Copy text</Button>
          {msg?.status === "approved" && msg.channel === "email" && (
            <Button startIcon={busy === "mailto" ? <CircularProgress size={16} /> : <MailOutline />} onClick={openEmail} disabled={Boolean(busy) || dirty}>Open in my email app</Button>
          )}
          <span style={{ flexGrow: 1 }} />
          {dirty && !frozen && <Button variant="outlined" onClick={save} disabled={Boolean(busy) || (msg.channel === "email" && !subject.trim()) || !body.trim()}>{busy === "save" ? "Saving..." : "Save changes"}</Button>}
          {msg?.status === "draft" && <Button variant="contained" onClick={approve} disabled={!agree || dirty || Boolean(busy)}>{busy === "approve" ? "Approving..." : "Approve"}</Button>}
          {msg?.status === "approved" && !dirty && <Button variant="contained" color="success" onClick={() => setConfirmSent(true)} disabled={Boolean(busy)}>I sent it</Button>}
          <Button color="inherit" onClick={onClose} disabled={Boolean(busy)}>Close</Button>
        </DialogActions>
      </Dialog>

      <ConfirmDialog
        open={confirmSent}
        title="Record this message as sent?"
        message="This only records that you sent it yourself. Kithi has not sent anything. The message will be locked and can no longer be edited."
        confirmLabel="Yes, I sent it"
        loading={busy === "sent"}
        onConfirm={markSent}
        onClose={() => setConfirmSent(false)}
      />
    </>
  );
}
