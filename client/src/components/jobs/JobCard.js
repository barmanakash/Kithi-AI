import { Box, Card, CardActionArea, CardContent, Chip, Link, Stack, Typography } from "@mui/material";
import OpenInNew from "@mui/icons-material/OpenInNew";
import { ScamChip } from "./ScamReport";
import { MATCH_LABELS, SOURCE_LABELS, safeHref } from "../../utils/jobs";
import { formatDate } from "../../utils/format";

export function MatchChip({ match }) {
  if (!match) return null;
  const info = MATCH_LABELS[match.label] || MATCH_LABELS.unknown;
  const text = match.score == null ? info.label : `${match.score}% - ${info.label}`;
  return <Chip size="small" color={info.color} label={text} />;
}

export default function JobCard({ job, onOpen, footer }) {
  const href = safeHref(job.url);
  return (
    <Card>
      <CardActionArea onClick={() => onOpen(job)} sx={{ alignItems: "flex-start" }}>
        <CardContent>
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1}>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="subtitle1" fontWeight={600}>
                {job.title}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {job.company}
                {job.location ? ` - ${job.location}` : ""}
                {job.posted_at ? ` - posted ${formatDate(job.posted_at)}` : ""}
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="flex-start">
              <MatchChip match={job.match} />
              {job.scam_level && job.scam_level !== "no_flags_found" && <ScamChip level={job.scam_level} />}
            </Stack>
          </Stack>

          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1.5 }}>
            {job.remote && <Chip size="small" variant="outlined" label="Remote" />}
            {job.job_type && <Chip size="small" variant="outlined" label={job.job_type.replace(/_/g, " ")} />}
            {job.salary_text && <Chip size="small" variant="outlined" label={job.salary_text} />}
            <Chip size="small" variant="outlined" label={SOURCE_LABELS[job.source] || job.source} />
            {job.injection_flags?.length > 0 && <Chip size="small" color="warning" variant="outlined" label="Suspicious wording" />}
          </Stack>

          {job.excerpt && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5, wordBreak: "break-word" }}>
              {job.excerpt}
            </Typography>
          )}
        </CardContent>
      </CardActionArea>
      {(href || footer) && (
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 2, pb: 1.5 }}>
          {href ? (
            <Link href={href} target="_blank" rel="noopener noreferrer" underline="hover" variant="body2" sx={{ display: "inline-flex", alignItems: "center", gap: 0.5 }}>
              Open posting <OpenInNew fontSize="inherit" />
            </Link>
          ) : (
            <span />
          )}
          {footer}
        </Stack>
      )}
    </Card>
  );
}
