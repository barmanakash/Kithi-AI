import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  LinearProgress,
  MenuItem,
  Skeleton,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import PageHeader from "../components/PageHeader";
import ConfirmDialog from "../components/ConfirmDialog";
import useApi from "../hooks/useApi";
import { useToast } from "../context/ToastContext";
import { salaryApi } from "../services/endpoints";
import { errorMessage } from "../utils/format";

const inr = (n) => `₹${Math.round(n || 0).toLocaleString("en-IN")}`;
const lpa = (n) => `${((n || 0) / 100000).toFixed(2)} LPA`;
const num = (v) => (v === "" || v == null ? 0 : Number(v));

function Stat({ label, value, hint }) {
  return (
    <Card variant="outlined" sx={{ height: "100%" }}>
      <CardContent>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        <Typography variant="h5" fontWeight={700}>{value}</Typography>
        {hint && <Typography variant="caption" color="text.secondary">{hint}</Typography>}
      </CardContent>
    </Card>
  );
}

function EstimateResult({ est }) {
  return (
    <Stack spacing={2}>
      <Grid container spacing={2}>
        <Grid item xs={6}><Stat label="Monthly in-hand (regular)" value={inr(est.monthly_in_hand_regular)} hint="Fixed pay only" /></Grid>
        <Grid item xs={6}><Stat label="Annual in-hand" value={inr(est.annual_in_hand)} hint={lpa(est.annual_in_hand)} /></Grid>
        <Grid item xs={6}><Stat label="CTC (estimate)" value={inr(est.ctc_estimate)} hint={lpa(est.ctc_estimate)} /></Grid>
        <Grid item xs={6}><Stat label="Income tax (estimate)" value={inr(est.income_tax_annual)} hint="Per year" /></Grid>
      </Grid>
      <Table size="small">
        <TableBody>
          {[
            ["Fixed pay", `${inr(est.fixed_annual)} (${est.fixed_percent_of_ctc}% of CTC)`],
            ["Variable pay (target)", `${inr(est.variable_annual)} (${est.variable_percent_of_ctc}% of CTC)`],
            ["Variable paid out", inr(est.variable_paid_annual)],
            ["Joining bonus", inr(est.joining_bonus)],
            ["Employer PF (in CTC)", inr(est.employer_pf_annual)],
            ["Employee PF (deducted)", inr(est.employee_pf_annual)],
            ["Professional tax", inr(est.professional_tax_annual)],
            ["Variable + bonus, after tax", inr(est.variable_and_bonus_net_annual)],
          ].map(([k, v]) => (
            <TableRow key={k}>
              <TableCell>{k}</TableCell>
              <TableCell align="right">{v}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Alert severity="info">
        <Typography variant="subtitle2">Assumptions</Typography>
        {est.assumptions.map((a) => <Typography key={a} variant="body2">• {a}</Typography>)}
      </Alert>
    </Stack>
  );
}

const EMPTY = { fixed_annual: "", variable_annual: "", variable_payout_percent: 100, joining_bonus: "", basic_percent: 40 };

function Estimator({ onSaved }) {
  const toast = useToast();
  const [form, setForm] = useState(EMPTY);
  const [est, setEst] = useState(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);
  const [meta, setMeta] = useState({ company: "", role: "", location: "" });
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const payload = () => ({
    fixed_annual: num(form.fixed_annual),
    variable_annual: num(form.variable_annual),
    variable_payout_percent: num(form.variable_payout_percent),
    joining_bonus: num(form.joining_bonus),
    basic_percent: num(form.basic_percent),
  });

  const calc = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      setEst(await salaryApi.estimate(payload()));
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await salaryApi.createOffer({ ...payload(), company: meta.company.trim(), role: meta.role.trim(), location: meta.location.trim() || null });
      toast.success("Offer saved");
      setSaveOpen(false);
      setMeta({ company: "", role: "", location: "" });
      onSaved();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Grid container spacing={2.5}>
      <Grid item xs={12} lg={5}>
        <Card>
          <CardHeader title="In-hand salary estimator" subheader="Amounts in INR per year. Estimates use the Indian new tax regime." />
          <CardContent sx={{ pt: 0 }}>
            <form onSubmit={calc}>
              <Stack spacing={2}>
                <TextField size="small" required type="number" label="Fixed pay per year (₹)" value={form.fixed_annual} onChange={set("fixed_annual")} helperText="Gross fixed pay, excluding employer PF. 12 LPA = 1200000" inputProps={{ min: 1 }} />
                <TextField size="small" type="number" label="Variable pay per year (₹)" value={form.variable_annual} onChange={set("variable_annual")} inputProps={{ min: 0 }} />
                <Stack direction="row" spacing={2}>
                  <TextField size="small" fullWidth type="number" label="Variable payout %" value={form.variable_payout_percent} onChange={set("variable_payout_percent")} inputProps={{ min: 0, max: 200 }} />
                  <TextField size="small" fullWidth type="number" label="Basic % of fixed" value={form.basic_percent} onChange={set("basic_percent")} inputProps={{ min: 10, max: 80 }} />
                </Stack>
                <TextField size="small" type="number" label="Joining bonus (₹)" value={form.joining_bonus} onChange={set("joining_bonus")} inputProps={{ min: 0 }} />
                <Stack direction="row" spacing={1}>
                  <Button type="submit" variant="contained" disabled={busy || num(form.fixed_annual) <= 0}>Calculate</Button>
                  <Button variant="outlined" disabled={!est} onClick={() => setSaveOpen(true)}>Save as offer</Button>
                </Stack>
              </Stack>
            </form>
          </CardContent>
        </Card>
      </Grid>
      <Grid item xs={12} lg={7}>
        <Card sx={{ height: "100%" }}>
          <CardHeader title="Breakdown" />
          <CardContent sx={{ pt: 0 }}>
            {est ? <EstimateResult est={est} /> : <Typography color="text.secondary">Enter your pay to see your CTC breakdown and estimated take-home.</Typography>}
          </CardContent>
        </Card>
      </Grid>

      <Dialog open={saveOpen} onClose={() => setSaveOpen(false)} fullWidth maxWidth="xs">
        <DialogTitle>Save as offer</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField size="small" required label="Company" value={meta.company} onChange={(e) => setMeta({ ...meta, company: e.target.value })} inputProps={{ maxLength: 150 }} />
            <TextField size="small" required label="Role" value={meta.role} onChange={(e) => setMeta({ ...meta, role: e.target.value })} inputProps={{ maxLength: 150 }} />
            <TextField size="small" label="Location (optional)" value={meta.location} onChange={(e) => setMeta({ ...meta, location: e.target.value })} inputProps={{ maxLength: 100 }} />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={save} disabled={saving || !meta.company.trim() || !meta.role.trim()}>Save</Button>
        </DialogActions>
      </Dialog>
    </Grid>
  );
}

function NegotiationDialog({ offer, onClose }) {
  const toast = useToast();
  const [form, setForm] = useState({ target_fixed_annual: "", target_variable_annual: "", tone: "polite", leverage_notes: "", points: "" });
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const generate = async () => {
    setBusy(true);
    setDraft(null);
    try {
      const body = {
        tone: form.tone,
        leverage_notes: form.leverage_notes.trim(),
        points_to_highlight: form.points.split("\n").map((p) => p.trim()).filter(Boolean).slice(0, 5),
      };
      if (form.target_fixed_annual !== "") body.target_fixed_annual = num(form.target_fixed_annual);
      if (form.target_variable_annual !== "") body.target_variable_annual = num(form.target_variable_annual);
      setDraft(await salaryApi.negotiation(offer.id, body));
    } catch (err) {
      toast.error(errorMessage(err, "Could not draft the message"));
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`Subject: ${draft.subject}\n\n${draft.body}`);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Could not copy. Select the text and copy it manually.");
    }
  };

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Negotiation message: {offer.company}</DialogTitle>
      <DialogContent>
        <Alert severity="info" sx={{ mb: 2 }}>This is only a draft. Nothing is sent. Check every figure before you use it.</Alert>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">Current offer: fixed {inr(offer.estimate.fixed_annual)}, variable {inr(offer.estimate.variable_annual)}</Typography>
              <TextField size="small" type="number" label="Fixed pay you want (₹/year)" value={form.target_fixed_annual} onChange={set("target_fixed_annual")} />
              <TextField size="small" type="number" label="Variable pay you want (₹/year, optional)" value={form.target_variable_annual} onChange={set("target_variable_annual")} />
              <TextField select size="small" label="Tone" value={form.tone} onChange={set("tone")}>
                <MenuItem value="polite">Warm and polite</MenuItem>
                <MenuItem value="confident">Confident and direct</MenuItem>
              </TextField>
              <TextField size="small" multiline minRows={2} label="Strengths to mention (one per line, optional)" value={form.points} onChange={set("points")} />
              <TextField size="small" multiline minRows={2} label="Extra facts (optional)" value={form.leverage_notes} onChange={set("leverage_notes")} helperText="Only true facts, e.g. an offer you really hold." inputProps={{ maxLength: 800 }} />
              {busy && <LinearProgress />}
              <Button variant="contained" onClick={generate} disabled={busy || (form.target_fixed_annual === "" && form.target_variable_annual === "")}>
                {busy ? "Drafting..." : "Draft message"}
              </Button>
            </Stack>
          </Grid>
          <Grid item xs={12} md={6}>
            {draft ? (
              <Stack spacing={1.5}>
                {draft.warnings.map((w) => <Alert key={w} severity="warning">{w}</Alert>)}
                <TextField size="small" label="Subject" value={draft.subject} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} />
                <TextField size="small" multiline minRows={10} label="Message" value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} />
                <Box><Button onClick={copy}>Copy to clipboard</Button></Box>
              </Stack>
            ) : (
              <Typography color="text.secondary">Your drafted email will appear here.</Typography>
            )}
          </Grid>
        </Grid>
      </DialogContent>
      <DialogActions><Button onClick={onClose}>Close</Button></DialogActions>
    </Dialog>
  );
}

function Offers({ refreshKey, onChanged }) {
  const toast = useToast();
  const offers = useApi(() => salaryApi.offers(), [refreshKey]);
  const [selected, setSelected] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [negotiate, setNegotiate] = useState(null);
  const [toDelete, setToDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const list = offers.data?.offers || [];

  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length < 6 ? [...s, id] : s));

  const compare = async () => {
    try {
      setComparison(await salaryApi.compare(selected));
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const remove = async () => {
    setDeleting(true);
    try {
      await salaryApi.removeOffer(toDelete.id);
      setSelected((s) => s.filter((x) => x !== toDelete.id));
      setComparison(null);
      toast.success("Offer deleted");
      setToDelete(null);
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Stack spacing={2.5}>
      <Card>
        <CardHeader
          title="Saved offers"
          subheader="Tick two or more to compare take-home pay."
          action={<Button variant="outlined" size="small" disabled={selected.length < 2} onClick={compare}>Compare ({selected.length})</Button>}
        />
        <CardContent sx={{ pt: 0 }}>
          {offers.error && <Alert severity="error">{offers.error}</Alert>}
          {offers.loading && !offers.data ? (
            <Skeleton variant="rounded" height={80} />
          ) : list.length === 0 ? (
            <Typography color="text.secondary">No offers saved yet. Use the estimator and choose "Save as offer".</Typography>
          ) : (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox" />
                  <TableCell>Company / role</TableCell>
                  <TableCell align="right">CTC</TableCell>
                  <TableCell align="right">Monthly in-hand</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {list.map((o) => (
                  <TableRow key={o.id} hover>
                    <TableCell padding="checkbox"><Checkbox checked={selected.includes(o.id)} onChange={() => toggle(o.id)} inputProps={{ "aria-label": `Select ${o.company}` }} /></TableCell>
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>{o.company}</Typography>
                      <Typography variant="caption" color="text.secondary">{o.role}{o.location ? ` · ${o.location}` : ""}</Typography>
                    </TableCell>
                    <TableCell align="right">{inr(o.estimate.ctc_estimate)}</TableCell>
                    <TableCell align="right">{inr(o.estimate.monthly_in_hand_regular)}</TableCell>
                    <TableCell align="right">
                      <Button size="small" onClick={() => setNegotiate(o)}>Negotiate</Button>
                      <Tooltip title="Delete">
                        <IconButton size="small" color="error" aria-label="Delete offer" onClick={() => setToDelete(o)}><DeleteOutline fontSize="small" /></IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {comparison && (
        <Card>
          <CardHeader title="Comparison" subheader={`Ranked by ${comparison.ranked_by}`} />
          <CardContent sx={{ pt: 0 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Offer</TableCell>
                  <TableCell align="right">Fixed</TableCell>
                  <TableCell align="right">Variable</TableCell>
                  <TableCell align="right">Monthly in-hand</TableCell>
                  <TableCell align="right">Annual in-hand</TableCell>
                  <TableCell align="right">Behind best by</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {comparison.offers.map((o) => (
                  <TableRow key={o.id}>
                    <TableCell>{o.company} - {o.role}</TableCell>
                    <TableCell align="right">{inr(o.fixed_annual)}</TableCell>
                    <TableCell align="right">{inr(o.variable_annual)}</TableCell>
                    <TableCell align="right">{inr(o.monthly_in_hand_regular)}</TableCell>
                    <TableCell align="right">{inr(o.annual_in_hand)}</TableCell>
                    <TableCell align="right">{o.gap_to_best_annual ? inr(o.gap_to_best_annual) : "Best"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>{comparison.note}</Typography>
          </CardContent>
        </Card>
      )}

      {negotiate && <NegotiationDialog offer={negotiate} onClose={() => setNegotiate(null)} />}
      <ConfirmDialog
        open={Boolean(toDelete)}
        title="Delete this offer?"
        message="The saved offer will be removed."
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={remove}
        onClose={() => setToDelete(null)}
      />
    </Stack>
  );
}

export default function SalaryIntelligence() {
  const [tab, setTab] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);
  return (
    <>
      <PageHeader
        title="Salary Intelligence"
        subtitle="Break down CTC, estimate your take-home, compare offers and prepare a negotiation message. No market salary data is invented."
      />
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2.5 }}>
        <Tab label="Estimator" />
        <Tab label="My offers" />
      </Tabs>
      {tab === 0 ? (
        <Estimator onSaved={() => setRefreshKey((k) => k + 1)} />
      ) : (
        <Offers refreshKey={refreshKey} onChanged={() => setRefreshKey((k) => k + 1)} />
      )}
    </>
  );
}
