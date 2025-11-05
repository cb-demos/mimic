/**
 * Property Check Dialog - Shows missing properties/secrets and allows creation
 */

import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  Box,
  Typography,
  CircularProgress,
  Chip,
} from '@mui/material';
import { useMutation } from '@tanstack/react-query';
import { scenariosApi } from '../api/endpoints';
import type { CreatePropertyRequest } from '../types/api';

interface PropertyCheckDialogProps {
  open: boolean;
  onClose: () => void;
  organizationId: string;
  missingProperties: string[];
  missingSecrets: string[];
  onPropertiesCreated: () => void;
}

export function PropertyCheckDialog({
  open,
  onClose,
  organizationId,
  missingProperties,
  missingSecrets,
  onPropertiesCreated,
}: PropertyCheckDialogProps) {
  const [propertyValues, setPropertyValues] = useState<Record<string, string>>({});
  const [currentProperty, setCurrentProperty] = useState<string | null>(null);
  const [createdProperties, setCreatedProperties] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  // Mutation for creating a single property
  const createPropertyMutation = useMutation({
    mutationFn: (request: CreatePropertyRequest) => scenariosApi.createProperty(request),
    onSuccess: (_, variables) => {
      setCreatedProperties((prev) => new Set([...prev, variables.name]));
      setCurrentProperty(null);
      setError(null);

      // Check if all missing properties have been created
      const allMissing = [...missingProperties, ...missingSecrets];
      const allCreated = allMissing.every((name) =>
        createdProperties.has(name) || name === variables.name
      );

      if (allCreated) {
        // Notify parent that all properties have been created
        setTimeout(() => {
          onPropertiesCreated();
        }, 500);
      }
    },
    onError: (err: any) => {
      setError(err.message || 'Failed to create property');
    },
  });

  const handleCreateProperty = (name: string, isSecret: boolean) => {
    const value = propertyValues[name];
    if (!value || !value.trim()) {
      setError(`Please enter a value for ${name}`);
      return;
    }

    setCurrentProperty(name);
    createPropertyMutation.mutate({
      organization_id: organizationId,
      name,
      value,
      is_secret: isSecret,
    });
  };

  const handleValueChange = (name: string, value: string) => {
    setPropertyValues((prev) => ({
      ...prev,
      [name]: value,
    }));
    setError(null);
  };

  const allMissing = [...missingProperties, ...missingSecrets];
  const allCreated = allMissing.every((name) => createdProperties.has(name));

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6">Required Properties & Secrets</Typography>
          {allCreated && (
            <Chip label="All Created" color="success" size="small" />
          )}
        </Box>
      </DialogTitle>

      <DialogContent>
        {missingProperties.length === 0 && missingSecrets.length === 0 ? (
          <Alert severity="success">
            All required properties and secrets exist!
          </Alert>
        ) : (
          <>
            <Alert severity="warning" sx={{ mb: 2 }}>
              This scenario requires {missingProperties.length + missingSecrets.length} property
              {missingProperties.length + missingSecrets.length > 1 ? 'ies' : 'y'} or secret
              {missingProperties.length + missingSecrets.length > 1 ? 's' : ''} that are missing
              from your organization. Please create them below.
            </Alert>

            {error && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
                {error}
              </Alert>
            )}

            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Value</TableCell>
                    <TableCell align="right">Action</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {missingProperties.map((propName) => {
                    const isCreated = createdProperties.has(propName);
                    const isCreating = currentProperty === propName;

                    return (
                      <TableRow key={propName}>
                        <TableCell>
                          <Typography variant="body2" fontFamily="monospace">
                            {propName}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip label="Property" size="small" color="primary" />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            fullWidth
                            placeholder="Enter value"
                            value={propertyValues[propName] || ''}
                            onChange={(e) => handleValueChange(propName, e.target.value)}
                            disabled={isCreated || isCreating}
                          />
                        </TableCell>
                        <TableCell align="right">
                          {isCreated ? (
                            <Chip label="Created" color="success" size="small" />
                          ) : (
                            <Button
                              size="small"
                              variant="contained"
                              onClick={() => handleCreateProperty(propName, false)}
                              disabled={isCreating}
                            >
                              {isCreating ? <CircularProgress size={20} /> : 'Create'}
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}

                  {missingSecrets.map((secretName) => {
                    const isCreated = createdProperties.has(secretName);
                    const isCreating = currentProperty === secretName;

                    return (
                      <TableRow key={secretName}>
                        <TableCell>
                          <Typography variant="body2" fontFamily="monospace">
                            {secretName}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <Chip label="Secret" size="small" color="secondary" />
                        </TableCell>
                        <TableCell>
                          <TextField
                            size="small"
                            fullWidth
                            type="password"
                            placeholder="Enter secret value"
                            value={propertyValues[secretName] || ''}
                            onChange={(e) => handleValueChange(secretName, e.target.value)}
                            disabled={isCreated || isCreating}
                            helperText={
                              propertyValues[secretName] && !isCreated
                                ? `Length: ${propertyValues[secretName].length} characters`
                                : ''
                            }
                          />
                        </TableCell>
                        <TableCell align="right">
                          {isCreated ? (
                            <Chip label="Created" color="success" size="small" />
                          ) : (
                            <Button
                              size="small"
                              variant="contained"
                              onClick={() => handleCreateProperty(secretName, true)}
                              disabled={isCreating}
                            >
                              {isCreating ? <CircularProgress size={20} /> : 'Create'}
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>

            {allCreated && (
              <Alert severity="success" sx={{ mt: 2 }}>
                All required properties and secrets have been created successfully!
              </Alert>
            )}
          </>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} disabled={createPropertyMutation.isPending}>
          {allCreated ? 'Close' : 'Cancel'}
        </Button>
        {allCreated && (
          <Button
            onClick={onPropertiesCreated}
            variant="contained"
            color="primary"
          >
            Continue
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
