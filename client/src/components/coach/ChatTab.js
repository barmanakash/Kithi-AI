import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Box, Button, Card, CardContent, Chip, LinearProgress, Stack, TextField, Typography } from "@mui/material";
import SendOutlined from "@mui/icons-material/SendOutlined";
import { coachApi } from "../../services/endpoints";
import { errorMessage } from "../../utils/format";

const SUGGESTIONS = [
  "What skills should I learn next?",
  "How am I doing overall?",
  "How is my resume?",
  "What would 12 LPA be in hand?",
  "How should I prepare for interviews?",
];

const WELCOME = {
  role: "assistant",
  agent: "Career Coach",
  content:
    "Hi! I can look at your saved data and answer questions about skill gaps, progress, your resume, salary maths and interviews. " +
    "Paste a job post and ask if it looks like a scam. I only read your data and never send or change anything.",
};

export default function ChatTab({ onTab }) {
  const navigate = useNavigate();
  const [messages, setMessages] = useState([WELCOME]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  const send = async (text) => {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    setError("");
    setInput("");
    const history = messages
      .filter((m) => m !== WELCOME)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content.slice(0, 1000) }));
    setMessages((m) => [...m, { role: "user", content: message }]);
    setBusy(true);
    try {
      const res = await coachApi.chat({ message, history });
      setMessages((m) => [...m, { role: "assistant", content: res.reply, agent: res.agent, action: res.action }]);
    } catch (err) {
      setError(errorMessage(err, "The coach could not answer"));
    } finally {
      setBusy(false);
    }
  };

  const runAction = (action) => {
    if (action.path) navigate(action.path);
    else if (action.tab) onTab(action.tab);
  };

  return (
    <Card>
      <CardContent>
        <Stack spacing={1.5} sx={{ minHeight: 320, maxHeight: 520, overflowY: "auto", pr: 1 }}>
          {messages.map((m, i) => (
            <Box key={i} sx={{ alignSelf: m.role === "user" ? "flex-end" : "flex-start", maxWidth: "85%" }}>
              {m.role === "assistant" && m.agent && (
                <Chip size="small" variant="outlined" label={m.agent} sx={{ mb: 0.5 }} />
              )}
              <Box
                sx={{
                  px: 1.75,
                  py: 1.25,
                  borderRadius: 2,
                  bgcolor: m.role === "user" ? "primary.main" : "action.hover",
                  color: m.role === "user" ? "primary.contrastText" : "text.primary",
                }}
              >
                <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>{m.content}</Typography>
              </Box>
              {m.action && (
                <Button size="small" sx={{ mt: 0.5 }} onClick={() => runAction(m.action)}>{m.action.label}</Button>
              )}
            </Box>
          ))}
          {busy && (
            <Box sx={{ maxWidth: 260 }}>
              <LinearProgress />
              <Typography variant="caption" color="text.secondary">Thinking locally. This can take a minute.</Typography>
            </Box>
          )}
          <div ref={endRef} />
        </Stack>

        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

        <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: "wrap", rowGap: 1 }}>
          {SUGGESTIONS.map((s) => (
            <Chip key={s} size="small" label={s} onClick={() => send(s)} disabled={busy} />
          ))}
        </Stack>

        <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
          <TextField
            fullWidth
            size="small"
            multiline
            maxRows={5}
            placeholder="Ask your career coach..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            inputProps={{ maxLength: 2000 }}
          />
          <Button variant="contained" endIcon={<SendOutlined />} onClick={() => send()} disabled={busy || !input.trim()}>
            Send
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );
}
