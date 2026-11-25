import { createTheme } from "@mui/material/styles";

const FONT = '"Inter", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

export function buildTheme(mode) {
  const dark = mode === "dark";
  return createTheme({
    palette: {
      mode,
      primary: { main: dark ? "#8b7cf6" : "#5b4bd6" },
      secondary: { main: dark ? "#2dd4bf" : "#0f9d8a" },
      success: { main: "#34d399" },
      warning: { main: "#fbbf24" },
      error: { main: "#f87171" },
      info: { main: "#60a5fa" },
      background: dark
        ? { default: "#0b0d14", paper: "#12151f" }
        : { default: "#f5f6fa", paper: "#ffffff" },
      divider: dark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.1)",
    },
    shape: { borderRadius: 12 },
    typography: {
      fontFamily: FONT,
      h4: { fontWeight: 700, letterSpacing: "-0.01em" },
      h5: { fontWeight: 700 },
      h6: { fontWeight: 600 },
      button: { textTransform: "none", fontWeight: 600 },
    },
    components: {
      MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
      MuiCard: { defaultProps: { variant: "outlined" } },
      MuiButton: { defaultProps: { disableElevation: true } },
      MuiChip: { styleOverrides: { root: { fontWeight: 500 } } },
      MuiTooltip: { defaultProps: { arrow: true } },
    },
  });
}
