import { Alert, Box, Card, CardContent, Chip, List, ListItem, ListItemIcon, ListItemText, Stack, Typography } from "@mui/material";
import { alpha } from "@mui/material/styles";
import LockClockOutlined from "@mui/icons-material/LockClockOutlined";
import CheckCircleOutline from "@mui/icons-material/CheckCircleOutline";
import PageHeader from "./PageHeader";

/** Honest placeholder for modules whose backend API does not exist yet. Shows no fake data. */
export default function ComingSoon({ item }) {
  const Icon = item.icon;
  return (
    <>
      <PageHeader title={item.label} subtitle={item.description} />
      <Card>
        <CardContent sx={{ p: { xs: 2, md: 4 } }}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={4} alignItems={{ md: "flex-start" }}>
            <Box
              sx={{
                width: 88,
                height: 88,
                flexShrink: 0,
                borderRadius: 3,
                display: "grid",
                placeItems: "center",
                color: "primary.main",
                bgcolor: (t) => alpha(t.palette.primary.main, 0.12),
              }}
            >
              <Icon sx={{ fontSize: 44 }} />
            </Box>
            <Box sx={{ flexGrow: 1 }}>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                <Typography variant="h6">Backend module pending</Typography>
                <Chip size="small" icon={<LockClockOutlined />} label={item.phase} color="primary" variant="outlined" />
              </Stack>
              <Typography color="text.secondary" sx={{ mb: 2 }}>
                This page will be connected to real data once its API exists. Nothing on this screen is simulated.
              </Typography>
              <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
                <strong>Needs:</strong> {item.needs}
              </Alert>
              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                Planned capabilities
              </Typography>
              <List dense disablePadding>
                {item.features.map((feature) => (
                  <ListItem key={feature} disableGutters>
                    <ListItemIcon sx={{ minWidth: 32 }}>
                      <CheckCircleOutline fontSize="small" color="secondary" />
                    </ListItemIcon>
                    <ListItemText primary={feature} />
                  </ListItem>
                ))}
              </List>
            </Box>
          </Stack>
        </CardContent>
      </Card>
    </>
  );
}
