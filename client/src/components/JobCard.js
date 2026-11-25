import { Button, Card, CardContent, Chip, IconButton, Stack, Tooltip, Typography } from "@mui/material";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import OpenInNew from "@mui/icons-material/OpenInNew";
import AddTaskOutlined from "@mui/icons-material/AddTaskOutlined";
import GppMaybeOutlined from "@mui/icons-material/GppMaybeOutlined";
import { scoreColor } from "../utils/format";
import { SCAM_LEVELS, safeUrl } from "../utils/statuses";

export default function JobCard({ job, onTrack, onDelete, tracking = false }) {
  const match = job.match;
  const scam = SCAM_LEVELS[job.scam_level];
  const showScam = job.scam_level && job.scam_level !== "no_flags_found";
  const url = safeUrl(job.url);

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1.5}>
          <div style={{ minWidth: 0 }}>
            <Typography variant="subtitle1" fontWeight={600}>
              {job.title}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {job.company}
              {job.location ? ` - ${job.location}` : ""}
              {job.salary_text ? ` - ${job.salary_text}` : ""}
            </Typography>
          </div>
          <Stack direction="row" spacing={1} alignItems="flex-start" flexWrap="wrap" useFlexGap>
            {match?.score != null ? (
              <Chip size="small" color={scoreColor(match.score)} label={`${match.score}% ${match.label}`} />
            ) : (
              <Tooltip title="Upload a resume or complete your profile to get a score">
                <Chip size="small" variant="outlined" label="Not scored" />
              </Tooltip>
            )}
            {showScam && (
              <Tooltip title="Rule-based warning signs were found. Check the Scam Detection page for the evidence.">
                <Chip size="small" icon={<GppMaybeOutlined />} color={scam.color} variant="outlined" label={scam.label} />
              </Tooltip>
            )}
          </Stack>
        </Stack>

        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1.5 }}>
          {job.remote && <Chip size="small" variant="outlined" label="Remote" />}
          {job.job_type && <Chip size="small" variant="outlined" label={job.job_type.replace("_", " ")} />}
          {job.source && <Chip size="small" variant="outlined" label={job.source} />}
        </Stack>

        {job.description_preview && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
            {job.description_preview}
            {job.description_preview.length >= 280 ? "..." : ""}
          </Typography>
        )}

        <Stack direction="row" spacing={1} sx={{ mt: 2 }} alignItems="center">
          {onTrack && (
            <Button size="small" variant="contained" startIcon={<AddTaskOutlined />} onClick={() => onTrack(job)} disabled={tracking}>
              Track application
            </Button>
          )}
          {url && (
            <Button size="small" component="a" href={url} target="_blank" rel="noopener noreferrer" endIcon={<OpenInNew fontSize="small" />}>
              View posting
            </Button>
          )}
          <span style={{ flexGrow: 1 }} />
          {onDelete && (
            <Tooltip title="Remove from saved jobs">
              <IconButton size="small" onClick={() => onDelete(job)} aria-label="Delete job">
                <DeleteOutline fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
