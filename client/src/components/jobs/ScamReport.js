import { Alert, Box, Chip, List, ListItem, ListItemText, Stack, Typography } from "@mui/material";
import { INJECTION_LABELS, SCAM_LEVELS } from "../../utils/jobs";

export function ScamChip({ level, score }) {
  const info = SCAM_LEVELS[level];
  if (!info) return null;
  return <Chip size="small" variant="outlined" color={info.color} label={score != null ? `${info.label} (${score})` : info.label} />;
}

export function InjectionAlert({ flags }) {
  if (!flags?.length) return null;
  const reasons = [...new Set(flags.map((f) => INJECTION_LABELS[f] || f))];
  return (
    <Alert severity="warning" sx={{ mb: 2 }}>
      This text contains wording that {reasons.join("; ")}. It is treated as untrusted content and can never trigger an action on your behalf.
    </Alert>
  );
}

/** Evidence-first display of a scam assessment. Never states that a listing is or is not a scam. */
export default function ScamReport({ report }) {
  if (!report) return null;
  const info = SCAM_LEVELS[report.risk_level] || SCAM_LEVELS.no_flags_found;
  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
        <Chip color={info.color} label={info.label} />
        <Typography variant="body2" color="text.secondary">
          Concern score {report.concern_score}/100 - confidence: {report.confidence}
        </Typography>
      </Stack>

      <InjectionAlert flags={report.injection_flags} />

      {report.signals?.length ? (
        <List dense disablePadding sx={{ mb: 2 }}>
          {report.signals.map((signal) => (
            <ListItem key={signal.key} disableGutters alignItems="flex-start">
              <ListItemText
                primary={`${signal.description} (+${signal.weight})`}
                secondary={
                  <Typography component="span" variant="caption" color="text.secondary" sx={{ wordBreak: "break-word" }}>
                    Evidence: {signal.evidence}
                  </Typography>
                }
              />
            </ListItem>
          ))}
        </List>
      ) : (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          None of the known warning signals were found in this text.
        </Typography>
      )}

      <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
        {report.uncertainty}
      </Alert>

      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
        How to verify the employer
      </Typography>
      <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
        {report.verification_steps?.map((step) => (
          <Typography component="li" variant="body2" color="text.secondary" key={step}>
            {step}
          </Typography>
        ))}
      </Box>
    </Box>
  );
}
