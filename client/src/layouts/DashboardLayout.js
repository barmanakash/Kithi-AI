import { useState } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  AppBar,
  Avatar,
  Box,
  Chip,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  Toolbar,
  Tooltip,
  Typography,
  useMediaQuery,
} from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import MenuIcon from "@mui/icons-material/Menu";
import DarkModeOutlined from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlined from "@mui/icons-material/LightModeOutlined";
import LogoutOutlined from "@mui/icons-material/LogoutOutlined";
import SettingsOutlined from "@mui/icons-material/SettingsOutlined";
import AutoAwesome from "@mui/icons-material/AutoAwesome";
import { NAV_ITEMS } from "../config/navigation";
import { useAuth } from "../context/AuthContext";
import { useColorMode } from "../context/ColorModeContext";
import AnimatedPage from "../components/AnimatedPage";
import { initials } from "../utils/format";

const DRAWER_WIDTH = 268;

function Brand() {
  return (
    <Stack direction="row" spacing={1.5} alignItems="center" sx={{ px: 2.5, height: 64 }}>
      <Box
        sx={{
          width: 36,
          height: 36,
          borderRadius: 2,
          display: "grid",
          placeItems: "center",
          color: "#fff",
          background: (t) => `linear-gradient(135deg, ${t.palette.primary.main}, ${t.palette.secondary.main})`,
        }}
      >
        <AutoAwesome fontSize="small" />
      </Box>
      <Box>
        <Typography variant="subtitle1" fontWeight={700} lineHeight={1.1}>
          Kithi AI
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Career OS
        </Typography>
      </Box>
    </Stack>
  );
}

export default function DashboardLayout() {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { mode, toggle } = useColorMode();

  const current = NAV_ITEMS.find((item) => location.pathname.startsWith(item.path));

  const handleLogout = () => {
    setMenuAnchor(null);
    logout();
    navigate("/login", { replace: true });
  };

  const drawer = (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Brand />
      <Divider />
      <List sx={{ px: 1.5, py: 1.5, flexGrow: 1, overflowY: "auto" }}>
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const selected = location.pathname.startsWith(item.path);
          return (
            <ListItemButton
              key={item.path}
              component={NavLink}
              to={item.path}
              selected={selected}
              onClick={() => setMobileOpen(false)}
              sx={{
                borderRadius: 2,
                mb: 0.25,
                "&.Mui-selected": {
                  bgcolor: alpha(theme.palette.primary.main, 0.16),
                  color: "primary.main",
                  "& .MuiListItemIcon-root": { color: "primary.main" },
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 38 }}>
                <Icon fontSize="small" />
              </ListItemIcon>
              <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: 14, fontWeight: selected ? 600 : 500 }} />
              {!item.ready && <Chip size="small" label="Soon" sx={{ height: 20, fontSize: 11 }} />}
            </ListItemButton>
          );
        })}
      </List>
      <Divider />
      <Box sx={{ p: 2 }}>
        <Typography variant="caption" color="text.secondary">
          Local-first. Your data and AI inference stay on this machine.
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <AppBar
        position="fixed"
        elevation={0}
        color="inherit"
        sx={{
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { md: `${DRAWER_WIDTH}px` },
          borderBottom: 1,
          borderColor: "divider",
          bgcolor: alpha(theme.palette.background.default, 0.85),
          backdropFilter: "blur(10px)",
        }}
      >
        <Toolbar>
          {!isDesktop && (
            <IconButton edge="start" onClick={() => setMobileOpen(true)} sx={{ mr: 1 }} aria-label="Open navigation">
              <MenuIcon />
            </IconButton>
          )}
          <Typography variant="h6" sx={{ flexGrow: 1 }} noWrap>
            {current?.label || "Kithi AI"}
          </Typography>
          <Tooltip title={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
            <IconButton onClick={toggle} aria-label="Toggle color mode">
              {mode === "dark" ? <LightModeOutlined /> : <DarkModeOutlined />}
            </IconButton>
          </Tooltip>
          <Tooltip title={user?.email || "Account"}>
            <IconButton onClick={(e) => setMenuAnchor(e.currentTarget)} sx={{ ml: 1 }} aria-label="Account menu">
              <Avatar sx={{ width: 34, height: 34, bgcolor: "primary.main", fontSize: 14 }}>{initials(user?.full_name)}</Avatar>
            </IconButton>
          </Tooltip>
          <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={() => setMenuAnchor(null)}>
            <Box sx={{ px: 2, py: 1, maxWidth: 260 }}>
              <Typography variant="subtitle2" noWrap>
                {user?.full_name}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap component="div">
                {user?.email}
              </Typography>
            </Box>
            <Divider />
            <MenuItem
              onClick={() => {
                setMenuAnchor(null);
                navigate("/settings");
              }}
            >
              <ListItemIcon>
                <SettingsOutlined fontSize="small" />
              </ListItemIcon>
              Settings
            </MenuItem>
            <MenuItem onClick={handleLogout}>
              <ListItemIcon>
                <LogoutOutlined fontSize="small" />
              </ListItemIcon>
              Sign out
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      <Box component="nav" sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}>
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          ModalProps={{ keepMounted: true }}
          sx={{ display: { xs: "block", md: "none" }, "& .MuiDrawer-paper": { width: DRAWER_WIDTH } }}
        >
          {drawer}
        </Drawer>
        <Drawer
          variant="permanent"
          open
          sx={{
            display: { xs: "none", md: "block" },
            "& .MuiDrawer-paper": { width: DRAWER_WIDTH, borderRight: 1, borderColor: "divider" },
          }}
        >
          {drawer}
        </Drawer>
      </Box>

      <Box component="main" sx={{ flexGrow: 1, minWidth: 0, p: { xs: 2, md: 4 }, pt: { xs: 10, md: 11 } }}>
        <Box sx={{ maxWidth: 1280, mx: "auto" }}>
          <AnimatedPage key={location.pathname}>
            <Outlet />
          </AnimatedPage>
        </Box>
      </Box>
    </Box>
  );
}
