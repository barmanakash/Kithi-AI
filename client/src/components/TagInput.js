import { Autocomplete, Chip, TextField } from "@mui/material";

/** Free-text multi-value input (skills, locations, technologies). Press Enter to add. */
export default function TagInput({ label, value = [], onChange, placeholder, helperText, suggestions = [] }) {
  return (
    <Autocomplete
      multiple
      freeSolo
      autoSelect
      filterSelectedOptions
      options={suggestions}
      value={value}
      onChange={(_, next) => onChange(next.map((item) => String(item).trim()).filter(Boolean))}
      renderTags={(tags, getTagProps) =>
        tags.map((option, index) => {
          const { key, ...tagProps } = getTagProps({ index });
          return <Chip key={key} size="small" label={option} {...tagProps} />;
        })
      }
      renderInput={(params) => (
        <TextField
          {...params}
          size="small"
          label={label}
          placeholder={value.length ? "" : placeholder}
          helperText={helperText}
        />
      )}
    />
  );
}
