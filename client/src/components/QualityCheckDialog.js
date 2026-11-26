import { useEffect, useState } from "react";
import { Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, LinearProgress, Stack, Typography } from "@mui/material";
import CheckCircleOutline from "@mui/icons-material/CheckCircleOutline";
import WarningAmberOutlined from "@mui/icons-material/WarningAmberOutlined";
import ErrorOutline from "@mui/icons-material/ErrorOutline";
import InfoOutlined from "@mui/icons-material/InfoOutlined";
import { applicationsApi } from "../services/endpoints";
import { errorMessage } from "../utils/format";

const ICONS = {
  pass: <CheckCircleOutline color="success" />,
  warn: <WarningAmberOutlined color="warning" />,
  fail: <ErrorOutline color="error" />,
  info: <InfoOutlined color="info" />,
};

/** Application Quality Checker: a read-only checklist to review before you apply. It changes nothing. */
export default function QualityCheckDialog({ application, onClose }) {
  const [state, setState] = useState({ loading: false, data: null, error: "" });

  useEffect(() => {
    if (!application) return undefined;
    let active = true;
    setState({ loading: true, data: null, error: "" });
    applicationsApi
      .qualityCheck(application.id)
      .then((data) => active && setState({ loading: false, data, error: "" }))
      .catch((err) => active && setState({ loading: false, data: null, error: errorMessage(err) }));
    return () => {
      active = false;
    };
  }, [application]);

  const { loading, data, error } = state;
  const summary = data
    ? data.blocking > 0
      ? `${data.blocking} blocking issue(s) to fix before you apply.`
      : data.warnings > 0
      ? `No blockers. ${data.warnings} suggestion(s) to review.`
      : "Everything looks ready."
    : "";

  return (
    <Dialog open={Boolean(application)} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Quality check{application ? `: ${application.job_title} at ${application.company}` : ""}</DialogTitle>
      <DialogContent dividers>
        {loading && <Box sx={{ textAlign: "center", py: 4 }}><CircularProgress /></Box>}
        {error && <Alert severity="error">{error}</Alert>}
        {data && (
          <Stack spacing={2}>
            <Alert severity={data.ready ? (data.warnings ? "info" : "success") : "error"}>{summary}</Alert>
            <Box>
              <Stack direction="row" justifyContent="space-between">
                <Typography variant="caption" color="text.secondary">Readiness score</Typography>
                <Chip size="small" label={`${data.score}/100`} />
              </Stack>
              <LinearProgress variant="determinate" value={data.score} sx={{ height: 8, borderRadius: 4, mt: 0.5 }} />
            </Box>
            {data.checks.map((c) => (
              <Stack key={c.key} direction="row" spacing={1.5} alignItems="flex-start">
                {ICONS[c.status]}
                <Box>
                  <Typography variant="body2" fontWeight={600}>{c.label}</Typography>
                  <Typography variant="body2" color="text.secondary">{c.message}</Typography>
                </Box>
              </Stack>
            ))}
            <Typography variant="caption" color="text.secondary">{data.note}</Typography>
          </Stack>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={onClose} variant="contained">Close</Button>
      </DialogActions>
    </Dialog>
  );
}
