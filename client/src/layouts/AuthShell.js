import { Box, Card, CardContent, Stack, Typography } from "@mui/material";
import AutoAwesome from "@mui/icons-material/AutoAwesome";

export default function AuthShell({ title, subtitle, children }) {
  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        p: 2,
        background: (t) =>
          t.palette.mode === "dark"
            ? "radial-gradient(900px 500px at 15% 10%, rgba(139,124,246,0.18), transparent), radial-gradient(800px 500px at 90% 90%, rgba(45,212,191,0.12), transparent)"
            : "radial-gradient(900px 500px at 15% 10%, rgba(91,75,214,0.12), transparent)",
      }}
    >
      <Box sx={{ width: "100%", maxWidth: 440 }}>
        <Stack alignItems="center" spacing={1} sx={{ mb: 3 }}>
          <Box
            sx={{
              width: 52,
              height: 52,
              borderRadius: 3,
              display: "grid",
              placeItems: "center",
              color: "#fff",
              background: (t) => `linear-gradient(135deg, ${t.palette.primary.main}, ${t.palette.secondary.main})`,
            }}
          >
            <AutoAwesome />
          </Box>
          <Typography variant="h5">Kithi AI</Typography>
          <Typography variant="body2" color="text.secondary" align="center">
            Find the right opportunity. Become the right candidate. Apply with confidence.
          </Typography>
        </Stack>
        <Card>
          <CardContent sx={{ p: 4 }}>
            <Typography variant="h5">{title}</Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {subtitle}
            </Typography>
            {children}
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
