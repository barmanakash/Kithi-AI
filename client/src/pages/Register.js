import { useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { Alert, Button, Link, Stack, TextField, Typography } from "@mui/material";
import AuthShell from "../layouts/AuthShell";
import { useAuth } from "../context/AuthContext";
import { errorMessage } from "../utils/format";

/** Mirrors the backend password rules so users get instant feedback. */
export function passwordProblem(value) {
  if (value.length < 8) return "Use at least 8 characters.";
  if (new TextEncoder().encode(value).length > 72) return "Password must be at most 72 bytes.";
  if (!(/[A-Za-z]/.test(value) && /\d/.test(value))) return "Include both letters and numbers.";
  return "";
}

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const pwError = form.password ? passwordProblem(form.password) : "";
  const mismatch = form.confirm && form.confirm !== form.password;
  const valid = form.full_name.trim() && form.email.trim() && form.password && !pwError && form.confirm === form.password;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!valid) return;
    setError("");
    setSubmitting(true);
    try {
      await register({ full_name: form.full_name.trim(), email: form.email.trim(), password: form.password });
      navigate("/overview", { replace: true });
    } catch (err) {
      setError(errorMessage(err, "Could not create the account"));
      setSubmitting(false);
    }
  };

  return (
    <AuthShell title="Create your account" subtitle="Your data stays local. No external AI services are used.">
      <form onSubmit={handleSubmit} noValidate>
        <Stack spacing={2}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField label="Full name" autoComplete="name" value={form.full_name} onChange={set("full_name")} required autoFocus fullWidth inputProps={{ maxLength: 120 }} />
          <TextField label="Email" type="email" autoComplete="email" value={form.email} onChange={set("email")} required fullWidth />
          <TextField
            label="Password"
            type="password"
            autoComplete="new-password"
            value={form.password}
            onChange={set("password")}
            required
            fullWidth
            error={Boolean(pwError)}
            helperText={pwError || "At least 8 characters, with letters and numbers."}
          />
          <TextField
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            value={form.confirm}
            onChange={set("confirm")}
            required
            fullWidth
            error={Boolean(mismatch)}
            helperText={mismatch ? "Passwords do not match." : " "}
          />
          <Button type="submit" variant="contained" size="large" disabled={submitting || !valid}>
            {submitting ? "Creating account..." : "Create account"}
          </Button>
          <Typography variant="body2" align="center" color="text.secondary">
            Already have an account?{" "}
            <Link component={RouterLink} to="/login">
              Sign in
            </Link>
          </Typography>
        </Stack>
      </form>
    </AuthShell>
  );
}
