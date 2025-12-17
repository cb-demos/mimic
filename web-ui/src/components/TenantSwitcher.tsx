/**
 * Tenant switcher component for the app header
 * Displays current tenant and allows switching between configured tenants
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
import { listTenants, selectTenant } from '../api/endpoints/tenants';
import type { TenantInfo } from '../types/api';

export function TenantSwitcher() {
  const [tenants, setTenants] = useState<TenantInfo[]>([]);
  const [currentTenant, setCurrentTenant] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch tenants on mount
  useEffect(() => {
    loadTenants();
  }, []);

  const loadTenants = async () => {
    try {
      setInitialLoading(true);
      const response = await listTenants();
      setTenants(response.tenants);
      setCurrentTenant(response.current || '');
      setError(null);
    } catch (err) {
      console.error('Failed to load tenants:', err);
      setError('Failed to load tenants');
    } finally {
      setInitialLoading(false);
    }
  };

  const handleChange = async (event: SelectChangeEvent<string>) => {
    const newTenant = event.target.value;

    // Don't do anything if selecting the same tenant
    if (newTenant === currentTenant) return;

    try {
      setLoading(true);
      setError(null);

      // Call API to switch tenant
      await selectTenant(newTenant);

      // Reload the page to refresh all state with new tenant
      window.location.reload();
    } catch (err) {
      console.error('Failed to switch tenant:', err);
      setError('Failed to switch tenant');
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
  if (error && tenants.length === 0) {
    return (
      <Chip
        label="No tenants"
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
        value={currentTenant}
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
        {tenants.map((tenant) => (
          <MenuItem key={tenant.name} value={tenant.name}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
              {tenant.is_current && <CloudDone fontSize="small" color="success" />}
              <Box sx={{ flexGrow: 1 }}>{tenant.name}</Box>
              {tenant.is_preset && (
                <Tooltip title="Preset tenant">
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
