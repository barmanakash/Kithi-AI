import { useState } from "react";
import { Alert, Box, Button, Card, CardContent, CardHeader, Chip, Grid, Link, LinearProgress, Stack, TextField, Typography } from "@mui/material";
import { careerApi } from "../../services/endpoints";
import { errorMessage, formatDate } from "../../utils/format";

function List({ title, items, color }) {
  if (!items?.length) return null;
  return (
    <Box>
      <Typography variant="subtitle2" color={color}>{title}</Typography>
      {items.map((s) => <Typography key={s} variant="body2">• {s}</Typography>)}
    </Box>
  );
}

export default function GithubTab() {
  const [username, setUsername] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const analyze = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await careerApi.github(username.trim()));
    } catch (err) {
      setResult(null);
      setError(errorMessage(err, "The analysis failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Card>
        <CardHeader title="GitHub portfolio analyzer" subheader="Reads only your public repositories. Leave the username empty to use the GitHub link in your profile." />
        <CardContent sx={{ pt: 0 }}>
          <form onSubmit={analyze}>
            <Stack direction="row" spacing={1.5} alignItems="flex-start">
              <TextField size="small" label="GitHub username (optional)" value={username} onChange={(e) => setUsername(e.target.value)} inputProps={{ maxLength: 39 }} />
              <Button type="submit" variant="contained" disabled={busy}>{busy ? "Analyzing..." : "Analyze"}</Button>
            </Stack>
            {busy && <LinearProgress sx={{ mt: 2 }} />}
          </form>
          {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
        </CardContent>
      </Card>

      {result && (
        <Grid container spacing={2.5}>
          <Grid item xs={12} md={6}>
            <Card sx={{ height: "100%" }}>
              <CardHeader
                title={result.profile.name || result.profile.username}
                subheader={`${result.profile.public_repos} public repos · ${result.profile.followers} followers · joined ${formatDate(result.profile.account_created)}`}
              />
              <CardContent sx={{ pt: 0 }}>
                <Stack spacing={1.5}>
                  <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1 }}>
                    <Chip size="small" label={`${result.metrics.original_repos} original repos`} />
                    <Chip size="small" label={`${result.metrics.recently_active_repos} active in 6 months`} />
                    <Chip size="small" label={`${result.metrics.total_stars} stars`} />
                  </Stack>
                  <List title="Strengths" items={result.strengths} color="success.main" />
                  <List title="Improve" items={result.improvements} color="warning.main" />
                  {result.languages.length > 0 && (
                    <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap", rowGap: 1 }}>
                      {result.languages.map((l) => <Chip key={l.language} size="small" variant="outlined" label={`${l.language} · ${l.repos}`} />)}
                    </Stack>
                  )}
                </Stack>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card sx={{ height: "100%" }}>
              <CardHeader title="Skills your projects demonstrate" />
              <CardContent sx={{ pt: 0 }}>
                {Object.keys(result.target_skill_evidence).length === 0 ? (
                  <Typography color="text.secondary">None of your target skills were found in repository languages, topics or descriptions.</Typography>
                ) : (
                  Object.entries(result.target_skill_evidence).map(([skill, repos]) => (
                    <Typography key={skill} variant="body2" sx={{ mb: 0.5 }}><b>{skill}</b>: {repos.join(", ")}</Typography>
                  ))
                )}
                {result.target_skills_without_projects.length > 0 && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                    No project evidence for: {result.target_skills_without_projects.slice(0, 12).join(", ")}
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12}>
            <Card>
              <CardHeader title="Top repositories" />
              <CardContent sx={{ pt: 0 }}>
                <Stack spacing={1.5}>
                  {result.top_repos.map((r) => (
                    <Box key={r.name}>
                      <Link href={r.url} target="_blank" rel="noopener noreferrer" underline="hover" fontWeight={600}>{r.name}</Link>
                      <Typography variant="caption" color="text.secondary"> · {r.language || "no language"} · {r.stars} stars</Typography>
                      {r.description && <Typography variant="body2" color="text.secondary">{r.description}</Typography>}
                    </Box>
                  ))}
                </Stack>
                <Alert severity="info" sx={{ mt: 2 }}>
                  {result.limitations.map((l) => <Typography key={l} variant="caption" display="block">{l}</Typography>)}
                </Alert>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Stack>
  );
}
