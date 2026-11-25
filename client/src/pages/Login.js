import { useState } from "react";
import { Link as RouterLink, useLocation, useNavigate } from "react-router-dom";
import { Alert, Button, Checkbox, FormControlLabel, Link, Stack, TextField, Typography } from "@mui/material";
import AuthShell from "../layouts/AuthShell";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../utils/format";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await login(email.trim(), password, remember);
      navigate(location.state?.from?.pathname || "/overview", { replace: true });
    } catch (err) {
      setError(errorMessage(err, "Sign in failed"));
      setSubmitting(false);
    }
  };

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to continue your job search.">
      <form onSubmit={handleSubmit} noValidate>
        <Stack spacing={2}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            fullWidth
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            fullWidth
          />
          <FormControlLabel
            control={<Checkbox checked={remember} onChange={(e) => setRemember(e.target.checked)} />}
            label="Keep me signed in on this device"
          />
          <Button type="submit" variant="contained" size="large" disabled={submitting || !email || !password}>
            {submitting ? "Signing in..." : "Sign in"}
          </Button>
          <Typography variant="body2" align="center" color="text.secondary">
            New to Kithi AI?{" "}
            <Link component={RouterLink} to="/register">
              Create an account
            </Link>
          </Typography>
        </Stack>
      </form>
    </AuthShell>
  );
}
