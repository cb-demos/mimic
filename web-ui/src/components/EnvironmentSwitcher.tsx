/**
 * Environment switcher component for the app header
 * Displays current environment and allows switching between configured environments
 */

import { useState, useEffect } from 'react';
import {
  Select,
  MenuItem,
  FormControl,
  Box,
  CircularProgress,
  Chip,
  Tooltip,
} from '@mui/material';
import type { SelectChangeEvent } from '@mui/material';
import { Cloud, CloudDone } from '@mui/icons-material';
import { listEnvironments, selectEnvironment } from '../api/endpoints/environments';
import type { EnvironmentInfo } from '../types/api';

export function EnvironmentSwitcher() {
  const [environments, setEnvironments] = useState<EnvironmentInfo[]>([]);
  const [currentEnv, setCurrentEnv] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch environments on mount
  useEffect(() => {
    loadEnvironments();
  }, []);

  const loadEnvironments = async () => {
    try {
      setInitialLoading(true);
      const response = await listEnvironments();
      setEnvironments(response.environments);
      setCurrentEnv(response.current || '');
      setError(null);
    } catch (err) {
      console.error('Failed to load environments:', err);
      setError('Failed to load environments');
    } finally {
      setInitialLoading(false);
    }
  };

  const handleChange = async (event: SelectChangeEvent<string>) => {
    const newEnv = event.target.value;

    // Don't do anything if selecting the same environment
    if (newEnv === currentEnv) return;

    try {
      setLoading(true);
      setError(null);

      // Call API to switch environment
      await selectEnvironment(newEnv);

      // Update local state
      setCurrentEnv(newEnv);

      // Update environments list to reflect new current
      setEnvironments(prev =>
        prev.map(env => ({
          ...env,
          is_current: env.name === newEnv,
        }))
      );
    } catch (err) {
      console.error('Failed to switch environment:', err);
      setError('Failed to switch environment');
      // Revert to previous selection on error
      event.preventDefault();
    } finally {
      setLoading(false);
    }
  };

  // Show loading spinner on initial load
  if (initialLoading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', ml: 2 }}>
        <CircularProgress size={20} color="inherit" />
      </Box>
    );
  }

  // Show error state
  if (error && environments.length === 0) {
    return (
      <Chip
        label="No environments"
        color="error"
        size="small"
        sx={{ ml: 2 }}
      />
    );
  }

  return (
    <FormControl
      size="small"
      sx={{
        ml: 2,
        minWidth: 150,
      }}
    >
      <Select
        value={currentEnv}
        onChange={handleChange}
        disabled={loading}
        sx={{
          color: 'inherit',
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: 'rgba(255, 255, 255, 0.23)',
          },
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: 'rgba(255, 255, 255, 0.4)',
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: 'rgba(255, 255, 255, 0.6)',
          },
          '& .MuiSelect-icon': {
            color: 'inherit',
          },
        }}
        startAdornment={
          loading ? (
            <CircularProgress size={16} sx={{ mr: 1 }} color="inherit" />
          ) : (
            <Cloud sx={{ mr: 1, fontSize: 20 }} />
          )
        }
      >
        {environments.map((env) => (
          <MenuItem key={env.name} value={env.name}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
              {env.is_current && <CloudDone fontSize="small" color="success" />}
              <Box sx={{ flexGrow: 1 }}>{env.name}</Box>
              {env.is_preset && (
                <Tooltip title="Preset environment">
                  <Chip
                    label="preset"
                    size="small"
                    variant="outlined"
                    sx={{ height: 20, fontSize: '0.7rem' }}
                  />
                </Tooltip>
              )}
            </Box>
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}
