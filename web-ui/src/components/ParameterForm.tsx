/**
 * Dynamic parameter form generator component
 * Generates form fields from scenario parameter schemas
 *
 * Accepts JSON Schema format: { properties: {...}, required: [...] }
 * This matches the CLI's parameter handling logic in parameter_handler.py
 */

import { useEffect, useState } from 'react';
import {
  Autocomplete,
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
import { configApi } from '../api/endpoints';
import type { ParameterSchema, ParameterProperty } from '../types/api';

interface ParameterFormProps {
  schema: ParameterSchema;
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
    // Iterate over schema.properties (matches CLI logic in parameter_handler.py line 95)
    Object.entries(schema.properties).forEach(([key, config]) => {
      if (config.default !== undefined) {
        defaults[key] = config.default;
      }
    });
    reset(defaults);
  };

  const handleFormSubmit = async (values: Record<string, any>) => {
    // Save parameter values to recent values
    for (const [key, value] of Object.entries(values)) {
      if (value && typeof value === 'string' && value.trim()) {
        const category = key === 'target_org' ? 'github_orgs' : key;
        try {
          await configApi.addRecentValue(category, value);
        } catch (err) {
          console.error(`Failed to save recent value for ${key}:`, err);
        }
      }
    }
    onSubmit(values);
  };

  return (
    <Box component="form" onSubmit={handleSubmit(handleFormSubmit)} noValidate>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {/* Iterate over schema.properties (matches CLI logic in parameter_handler.py line 95) */}
        {Object.entries(schema.properties).map(([name, config]) => {
          // Check if required using schema.required array (matches CLI logic line 96)
          const isRequired = schema.required.includes(name);
          return (
            <ParameterField
              key={name}
              name={name}
              config={config}
              isRequired={isRequired}
              control={control}
              error={errors[name]?.message as string}
            />
          );
        })}
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
  config: ParameterProperty;
  isRequired: boolean;
  control: any;
  error?: string;
  onValueChange?: (name: string, value: any) => void;
}

function ParameterField({
  name,
  config,
  isRequired,
  control,
  error,
  onValueChange,
}: ParameterFieldProps) {
  const [recentValues, setRecentValues] = useState<string[]>([]);

  // Load recent values for this parameter
  useEffect(() => {
    const loadRecentValues = async () => {
      try {
        // Use parameter name as category, with special case for target_org
        const category = name === 'target_org' ? 'github_orgs' : name;
        const response = await configApi.getRecentValues(category);
        setRecentValues(response.values);
      } catch (err) {
        console.error(`Failed to load recent values for ${name}:`, err);
      }
    };
    loadRecentValues();
  }, [name]);
  // Enum field (dropdown)
  if (config.enum && config.enum.length > 0) {
    return (
      <Controller
        name={name}
        control={control}
        rules={{
          required: isRequired ? `${name} is required` : undefined,
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
          required: isRequired ? `${name} is required` : undefined,
        }}
        render={({ field }) => (
          <TextField
            {...field}
            type="number"
            label={name}
            fullWidth
            error={!!error}
            helperText={error || config.description}
          />
        )}
      />
    );
  }

  // String field with autocomplete (default)
  return (
    <Controller
      name={name}
      control={control}
      rules={{
        required: isRequired ? `${name} is required` : undefined,
        pattern: config.pattern
          ? { value: new RegExp(config.pattern), message: `Invalid format for ${name}` }
          : undefined,
      }}
      render={({ field }) => (
        <Autocomplete
          freeSolo
          options={recentValues}
          value={field.value || ''}
          onChange={(_event, value) => {
            field.onChange(value || '');
            if (onValueChange && value) {
              onValueChange(name, value);
            }
          }}
          onInputChange={(_event, value) => {
            field.onChange(value || '');
          }}
          renderInput={(params) => (
            <TextField
              {...params}
              label={name}
              fullWidth
              error={!!error}
              helperText={error || config.description}
              placeholder={config.placeholder}
              required={isRequired}
            />
          )}
        />
      )}
    />
  );
}
