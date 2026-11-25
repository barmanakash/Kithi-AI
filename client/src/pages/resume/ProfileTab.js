import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  FormControlLabel,
  Grid,
  IconButton,
  LinearProgress,
  MenuItem,
  Paper,
  Skeleton,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteOutline from "@mui/icons-material/DeleteOutline";
import SaveOutlined from "@mui/icons-material/SaveOutlined";
import ConfirmDialog from "../../components/ConfirmDialog";
import TagInput from "../../components/TagInput";
import { useToast } from "../../context/ToastContext";
import { profileApi } from "../../services/endpoints";
import { COMPLETENESS_LABELS, errorMessage } from "../../utils/format";
import {
  EMPLOYMENT_OPTIONS,
  blankCertification,
  blankEducation,
  blankExperience,
  blankProject,
  toForm,
  toPayload,
  validateForm,
} from "../../utils/profileMapper";

function Section({ title, subtitle, action, children }) {
  return (
    <Paper variant="outlined" sx={{ p: 3 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 2 }}>
        <Box>
          <Typography variant="h6">{title}</Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        {action}
      </Stack>
      {children}
    </Paper>
  );
}

function ListEditor({ title, subtitle, items, onChange, create, addLabel, emptyText, renderItem }) {
  const update = (index, patch) => onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  const remove = (index) => onChange(items.filter((_, i) => i !== index));
  return (
    <Section
      title={title}
      subtitle={subtitle}
      action={
        <Button size="small" startIcon={<AddIcon />} onClick={() => onChange([...items, create()])}>
          {addLabel}
        </Button>
      }
    >
      {items.length === 0 && (
        <Typography variant="body2" color="text.secondary">
          {emptyText}
        </Typography>
      )}
      <Stack spacing={2}>
        {items.map((item, index) => (
          <Box key={index} sx={{ p: 2, border: 1, borderColor: "divider", borderRadius: 2 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
              <Typography variant="subtitle2" color="text.secondary">
                #{index + 1}
              </Typography>
              <IconButton size="small" onClick={() => remove(index)} aria-label={`Remove ${title} entry ${index + 1}`}>
                <DeleteOutline fontSize="small" />
              </IconButton>
            </Stack>
            {renderItem(item, (patch) => update(index, patch))}
          </Box>
        ))}
      </Stack>
    </Section>
  );
}

const Field = (props) => <TextField size="small" fullWidth {...props} />;

export default function ProfileTab() {
  const toast = useToast();
  const [form, setForm] = useState(null);
  const [completeness, setCompleteness] = useState(null);
  const [exists, setExists] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [errors, setErrors] = useState([]);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = async () => {
    setLoadError("");
    try {
      const res = await profileApi.get();
      setForm(toForm(res.profile));
      setCompleteness(res.completeness);
      setExists(res.exists);
      setDirty(false);
    } catch (err) {
      setLoadError(errorMessage(err));
    }
  };

  useEffect(() => {
    load();
  }, []);

  const change = (patch) => {
    setForm((f) => ({ ...f, ...patch }));
    setDirty(true);
  };
  const set = (key) => (e) => change({ [key]: e.target.value });

  const handleSave = async () => {
    const problems = validateForm(form);
    setErrors(problems);
    if (problems.length) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    setSaving(true);
    try {
      const res = await profileApi.save(toPayload(form));
      setForm(toForm(res.profile));
      setCompleteness(res.completeness);
      setExists(true);
      setDirty(false);
      toast.success("Profile saved");
    } catch (err) {
      setErrors([errorMessage(err, "Could not save the profile")]);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await profileApi.remove();
      toast.success("Profile deleted");
      setConfirmDelete(false);
      await load();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  if (loadError) {
    return (
      <Alert severity="error" action={<Button color="inherit" size="small" onClick={load}>Retry</Button>}>
        {loadError}
      </Alert>
    );
  }
  if (!form) {
    return (
      <Stack spacing={2}>
        <Skeleton variant="rounded" height={80} />
        <Skeleton variant="rounded" height={260} />
        <Skeleton variant="rounded" height={260} />
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            Profile completeness
          </Typography>
          <Typography variant="subtitle1" fontWeight={700}>
            {completeness?.percent ?? 0}%
          </Typography>
        </Stack>
        <LinearProgress variant="determinate" value={completeness?.percent ?? 0} sx={{ height: 8, borderRadius: 4 }} />
        {completeness?.missing?.length > 0 && (
          <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mt: 2 }}>
            {completeness.missing.map((key) => (
              <Chip key={key} size="small" variant="outlined" label={COMPLETENESS_LABELS[key] || key} />
            ))}
          </Stack>
        )}
        {!exists && (
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>
            Nothing is saved yet. Only information you enter here is ever used by the AI agents.
          </Typography>
        )}
      </Paper>

      {errors.length > 0 && (
        <Alert severity="error">
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            Please fix the following:
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
            {errors.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </Box>
        </Alert>
      )}

      <Section title="Personal information">
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Field label="Full name" value={form.full_name} onChange={set("full_name")} inputProps={{ maxLength: 120 }} />
          </Grid>
          <Grid item xs={12} md={6}>
            <Field label="Professional headline" value={form.headline} onChange={set("headline")} inputProps={{ maxLength: 200 }} placeholder="e.g. Full-stack developer (React, FastAPI)" />
          </Grid>
          <Grid item xs={12} md={6}>
            <Field label="Phone" value={form.phone} onChange={set("phone")} inputProps={{ maxLength: 30 }} />
          </Grid>
          <Grid item xs={12} md={6}>
            <Field label="Current location" value={form.location} onChange={set("location")} inputProps={{ maxLength: 200 }} />
          </Grid>
          <Grid item xs={12}>
            <Field label="Professional summary" value={form.summary} onChange={set("summary")} multiline minRows={3} inputProps={{ maxLength: 3000 }} helperText={`${form.summary.length}/3000`} />
          </Grid>
          <Grid item xs={12} md={4}>
            <Field label="LinkedIn URL" value={form.linkedin_url} onChange={set("linkedin_url")} />
          </Grid>
          <Grid item xs={12} md={4}>
            <Field label="GitHub URL" value={form.github_url} onChange={set("github_url")} />
          </Grid>
          <Grid item xs={12} md={4}>
            <Field label="Portfolio URL" value={form.portfolio_url} onChange={set("portfolio_url")} />
          </Grid>
        </Grid>
      </Section>

      <ListEditor
        title="Work experience"
        items={form.experience}
        onChange={(experience) => change({ experience })}
        create={blankExperience}
        addLabel="Add role"
        emptyText="No roles added yet."
        renderItem={(item, update) => (
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Field label="Company" required value={item.company} onChange={(e) => update({ company: e.target.value })} inputProps={{ maxLength: 150 }} />
            </Grid>
            <Grid item xs={12} md={6}>
              <Field label="Job title" required value={item.title} onChange={(e) => update({ title: e.target.value })} inputProps={{ maxLength: 150 }} />
            </Grid>
            <Grid item xs={12} md={4}>
              <Field label="Location" value={item.location} onChange={(e) => update({ location: e.target.value })} inputProps={{ maxLength: 200 }} />
            </Grid>
            <Grid item xs={6} md={3}>
              <Field label="Start" type="month" value={item.start_date} onChange={(e) => update({ start_date: e.target.value })} InputLabelProps={{ shrink: true }} helperText="YYYY-MM" />
            </Grid>
            <Grid item xs={6} md={3}>
              <Field label="End" type="month" value={item.current ? "" : item.end_date} disabled={item.current} onChange={(e) => update({ end_date: e.target.value })} InputLabelProps={{ shrink: true }} helperText="YYYY-MM" />
            </Grid>
            <Grid item xs={12} md={2}>
              <FormControlLabel control={<Checkbox checked={item.current} onChange={(e) => update({ current: e.target.checked })} />} label="Current" />
            </Grid>
            <Grid item xs={12}>
              <Field label="Description" value={item.description} onChange={(e) => update({ description: e.target.value })} multiline minRows={2} inputProps={{ maxLength: 3000 }} />
            </Grid>
            <Grid item xs={12}>
              <Field
                label="Achievements (one per line)"
                value={item.achievements}
                onChange={(e) => update({ achievements: e.target.value })}
                multiline
                minRows={2}
                helperText="Only list achievements that are true. Add real numbers where you have them."
              />
            </Grid>
          </Grid>
        )}
      />

      <Section title="Skills">
        <Stack spacing={2}>
          <TagInput label="Technical skills" value={form.technical_skills} onChange={(technical_skills) => change({ technical_skills })} placeholder="Type a skill and press Enter" helperText="e.g. Python, React, MongoDB" />
          <TagInput label="Soft skills" value={form.soft_skills} onChange={(soft_skills) => change({ soft_skills })} placeholder="Type a skill and press Enter" />
        </Stack>
      </Section>

      <ListEditor
        title="Education"
        items={form.education}
        onChange={(education) => change({ education })}
        create={blankEducation}
        addLabel="Add education"
        emptyText="No education added yet."
        renderItem={(item, update) => (
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Field label="Institution" required value={item.institution} onChange={(e) => update({ institution: e.target.value })} inputProps={{ maxLength: 200 }} />
            </Grid>
            <Grid item xs={12} md={6}>
              <Field label="Degree" required value={item.degree} onChange={(e) => update({ degree: e.target.value })} inputProps={{ maxLength: 150 }} />
            </Grid>
            <Grid item xs={12} md={4}>
              <Field label="Field of study" value={item.field_of_study} onChange={(e) => update({ field_of_study: e.target.value })} inputProps={{ maxLength: 200 }} />
            </Grid>
            <Grid item xs={4} md={2.5}>
              <Field label="Start year" type="number" value={item.start_year} onChange={(e) => update({ start_year: e.target.value })} />
            </Grid>
            <Grid item xs={4} md={2.5}>
              <Field label="End year" type="number" value={item.end_year} onChange={(e) => update({ end_year: e.target.value })} />
            </Grid>
            <Grid item xs={4} md={3}>
              <Field label="Grade" value={item.grade} onChange={(e) => update({ grade: e.target.value })} inputProps={{ maxLength: 50 }} />
            </Grid>
          </Grid>
        )}
      />

      <ListEditor
        title="Certifications"
        items={form.certifications}
        onChange={(certifications) => change({ certifications })}
        create={blankCertification}
        addLabel="Add certification"
        emptyText="No certifications added yet."
        renderItem={(item, update) => (
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Field label="Name" required value={item.name} onChange={(e) => update({ name: e.target.value })} inputProps={{ maxLength: 200 }} />
            </Grid>
            <Grid item xs={8} md={3}>
              <Field label="Issuer" value={item.issuer} onChange={(e) => update({ issuer: e.target.value })} inputProps={{ maxLength: 200 }} />
            </Grid>
            <Grid item xs={4} md={3}>
              <Field label="Year" type="number" value={item.year} onChange={(e) => update({ year: e.target.value })} />
            </Grid>
            <Grid item xs={12}>
              <Field label="Credential URL" value={item.url} onChange={(e) => update({ url: e.target.value })} />
            </Grid>
          </Grid>
        )}
      />

      <ListEditor
        title="Projects"
        subtitle="Real projects only. These are used to match you to jobs and tailor your resume."
        items={form.projects}
        onChange={(projects) => change({ projects })}
        create={blankProject}
        addLabel="Add project"
        emptyText="No projects added yet."
        renderItem={(item, update) => (
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Field label="Project name" required value={item.name} onChange={(e) => update({ name: e.target.value })} inputProps={{ maxLength: 150 }} />
            </Grid>
            <Grid item xs={12} md={6}>
              <Field label="URL (repository or demo)" value={item.url} onChange={(e) => update({ url: e.target.value })} />
            </Grid>
            <Grid item xs={12}>
              <Field label="Description" value={item.description} onChange={(e) => update({ description: e.target.value })} multiline minRows={2} inputProps={{ maxLength: 2000 }} />
            </Grid>
            <Grid item xs={12}>
              <TagInput label="Technologies" value={item.technologies} onChange={(technologies) => update({ technologies })} placeholder="Type a technology and press Enter" />
            </Grid>
          </Grid>
        )}
      />

      <Section title="Job preferences">
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <Field label="Salary expectation (minimum)" type="number" value={form.salary.min} onChange={(e) => change({ salary: { ...form.salary, min: e.target.value } })} />
          </Grid>
          <Grid item xs={12} md={6}>
            <Field label="Salary expectation (maximum)" type="number" value={form.salary.max} onChange={(e) => change({ salary: { ...form.salary, max: e.target.value } })} />
          </Grid>
          <Grid item xs={6} md={3}>
            <Field label="Currency" value={form.salary.currency} onChange={(e) => change({ salary: { ...form.salary, currency: e.target.value.toUpperCase().slice(0, 3) } })} />
          </Grid>
          <Grid item xs={6} md={3}>
            <Field select label="Period" value={form.salary.period} onChange={(e) => change({ salary: { ...form.salary, period: e.target.value } })}>
              <MenuItem value="annual">Annual</MenuItem>
              <MenuItem value="monthly">Monthly</MenuItem>
            </Field>
          </Grid>
          <Grid item xs={12} md={6}>
            <Field label="Notice period (days)" type="number" value={form.notice_period_days} onChange={set("notice_period_days")} inputProps={{ min: 0, max: 365 }} />
          </Grid>
          <Grid item xs={12}>
            <TagInput label="Preferred locations" value={form.preferred_locations} onChange={(preferred_locations) => change({ preferred_locations })} placeholder="Type a city and press Enter" />
          </Grid>
          <Grid item xs={12}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Employment preferences
            </Typography>
            <Stack direction="row" flexWrap="wrap" gap={1}>
              {EMPLOYMENT_OPTIONS.map(([value, label]) => {
                const selected = form.employment_preferences.includes(value);
                return (
                  <Chip
                    key={value}
                    label={label}
                    color={selected ? "primary" : "default"}
                    variant={selected ? "filled" : "outlined"}
                    onClick={() =>
                      change({
                        employment_preferences: selected
                          ? form.employment_preferences.filter((v) => v !== value)
                          : [...form.employment_preferences, value],
                      })
                    }
                  />
                );
              })}
            </Stack>
          </Grid>
        </Grid>
      </Section>

      <Paper
        variant="outlined"
        sx={{
          p: 2,
          position: "sticky",
          bottom: 16,
          zIndex: 5,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 2,
          backdropFilter: "blur(8px)",
        }}
      >
        <Button color="error" onClick={() => setConfirmDelete(true)} disabled={!exists || saving}>
          Delete profile
        </Button>
        <Stack direction="row" spacing={2} alignItems="center">
          {dirty && (
            <Typography variant="caption" color="text.secondary">
              Unsaved changes
            </Typography>
          )}
          <Button variant="contained" startIcon={<SaveOutlined />} onClick={handleSave} disabled={saving || (!dirty && exists)}>
            {saving ? "Saving..." : "Save profile"}
          </Button>
        </Stack>
      </Paper>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete your candidate profile?"
        message="All saved profile information will be permanently removed. Your uploaded resumes are not affected."
        confirmLabel="Delete profile"
        loading={deleting}
        onConfirm={handleDelete}
        onClose={() => setConfirmDelete(false)}
      />
    </Stack>
  );
}
