import { Box, CircularProgress, Typography } from "@mui/material";
import { scoreColor } from "../utils/format";

export default function ScoreRing({ value = 0, size = 120, label = "/ 100" }) {
  const color = scoreColor(value);
  return (
    <Box sx={{ position: "relative", display: "inline-flex", width: size, height: size }}>
      <CircularProgress
        variant="determinate"
        value={100}
        size={size}
        thickness={4}
        sx={{ color: "action.hover", position: "absolute", inset: 0 }}
      />
      <CircularProgress variant="determinate" value={Math.min(Math.max(value, 0), 100)} size={size} thickness={4} color={color} />
      <Box
        sx={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}
      >
        <Typography variant="h4" component="div" sx={{ lineHeight: 1 }}>
          {Math.round(value)}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
      </Box>
    </Box>
  );
}
