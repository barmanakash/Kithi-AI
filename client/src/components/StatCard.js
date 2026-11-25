import { Avatar, Box, Card, CardContent, Chip, Skeleton, Stack, Typography } from "@mui/material";
import { alpha } from "@mui/material/styles";

export default function StatCard({ icon: Icon, label, value, caption, color = "primary", loading = false, chip }) {
  return (
    <Card sx={{ height: "100%" }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body2" color="text.secondary" noWrap>
              {label}
            </Typography>
            {loading ? (
              <Skeleton width={90} height={46} />
            ) : (
              <Typography variant="h4" sx={{ mt: 0.5 }}>
                {value}
              </Typography>
            )}
          </Box>
          <Avatar sx={{ bgcolor: (t) => alpha(t.palette[color].main, 0.15), color: `${color}.main` }}>
            <Icon />
          </Avatar>
        </Stack>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1, minHeight: 24 }}>
          {chip && <Chip size="small" label={chip} variant="outlined" />}
          {caption && (
            <Typography variant="caption" color="text.secondary">
              {caption}
            </Typography>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
