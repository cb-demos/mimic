/**
 * Dynamic parameter form generator component
 * Generates form fields from scenario parameter schemas
 */

import {
  Box,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  FormHelperText,
  Checkbox,
  FormControlLabel,
  Button,
  Typography,
} from '@mui/material';
import { Controller, useForm } from 'react-hook-form';

interface ParameterSchema {
  type: 'string' | 'number' | 'boolean';
  description?: string;
  default?: any;
  enum?: string[];
  pattern?: string;
  min?: number;
  max?: number;
  required?: boolean;
}

interface ParameterFormProps {
  schema: Record<string, ParameterSchema>;
  initialValues?: Record<string, any>;
  onSubmit: (values: Record<string, any>) => void;
  submitLabel?: string;
}

export function ParameterForm({
  schema,
  initialValues = {},
  onSubmit,
  submitLabel = 'Submit',
}: ParameterFormProps) {
  const {
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({
    defaultValues: initialValues,
  });

  const handleReset = () => {
    const defaults: Record<string, any> = {};
    Object.entries(schema).forEach(([key, config]) => {
      if (config.default !== undefined) {
        defaults[key] = config.default;
      }
    });
    reset(defaults);
  };

  return (
    <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {Object.entries(schema).map(([name, config]) => (
          <ParameterField
            key={name}
            name={name}
            config={config}
            control={control}
            error={errors[name]?.message as string}
          />
        ))}
      </Box>

      <Box sx={{ display: 'flex', gap: 2, mt: 3 }}>
        <Button type="submit" variant="contained" color="primary">
          {submitLabel}
        </Button>
        <Button type="button" variant="outlined" onClick={handleReset}>
          Reset to Defaults
        </Button>
      </Box>
    </Box>
  );
}

interface ParameterFieldProps {
  name: string;
  config: ParameterSchema;
  control: any;
  error?: string;
}

function ParameterField({ name, config, control, error }: ParameterFieldProps) {
  // Enum field (dropdown)
  if (config.enum && config.enum.length > 0) {
    return (
      <Controller
        name={name}
        control={control}
        rules={{
          required: config.required ? `${name} is required` : undefined,
        }}
        render={({ field }) => (
          <FormControl fullWidth error={!!error}>
            <InputLabel>{name}</InputLabel>
            <Select {...field} label={name}>
              {config.enum!.map((option) => (
                <MenuItem key={option} value={option}>
                  {option}
                </MenuItem>
              ))}
            </Select>
            {config.description && <FormHelperText>{config.description}</FormHelperText>}
            {error && <FormHelperText error>{error}</FormHelperText>}
          </FormControl>
        )}
      />
    );
  }

  // Boolean field (checkbox)
  if (config.type === 'boolean') {
    return (
      <Controller
        name={name}
        control={control}
        render={({ field }) => (
          <FormControl error={!!error}>
            <FormControlLabel
              control={<Checkbox {...field} checked={field.value || false} />}
              label={
                <Box>
                  <Typography variant="body1">{name}</Typography>
                  {config.description && (
                    <Typography variant="caption" color="text.secondary">
                      {config.description}
                    </Typography>
                  )}
                </Box>
              }
            />
            {error && <FormHelperText error>{error}</FormHelperText>}
          </FormControl>
        )}
      />
    );
  }

  // Number field
  if (config.type === 'number') {
    return (
      <Controller
        name={name}
        control={control}
        rules={{
          required: config.required ? `${name} is required` : undefined,
          min: config.min !== undefined ? { value: config.min, message: `Minimum value is ${config.min}` } : undefined,
          max: config.max !== undefined ? { value: config.max, message: `Maximum value is ${config.max}` } : undefined,
        }}
        render={({ field }) => (
          <TextField
            {...field}
            type="number"
            label={name}
            fullWidth
            error={!!error}
            helperText={error || config.description}
            inputProps={{
              min: config.min,
              max: config.max,
            }}
          />
        )}
      />
    );
  }

  // String field (default)
  return (
    <Controller
      name={name}
      control={control}
      rules={{
        required: config.required ? `${name} is required` : undefined,
        pattern: config.pattern ? { value: new RegExp(config.pattern), message: `Invalid format for ${name}` } : undefined,
      }}
      render={({ field }) => (
        <TextField
          {...field}
          label={name}
          fullWidth
          error={!!error}
          helperText={error || config.description}
        />
      )}
    />
  );
}
