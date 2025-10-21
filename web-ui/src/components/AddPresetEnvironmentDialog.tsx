/**
 * Add Preset Environment Dialog - Multi-step wizard for adding preset environments
 */

import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Stepper,
  Step,
  StepLabel,
  Box,
  TextField,
  Typography,
  Alert,
  CircularProgress,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Radio,
  Chip,
  Paper,
} from '@mui/material';
import { CheckCircle, Error as ErrorIcon } from '@mui/icons-material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { environmentsApi } from '../api/endpoints';
import type { PresetEnvironmentInfo } from '../types/api';

interface AddPresetEnvironmentDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const steps = ['Select Preset', 'Enter Credentials', 'Validate', 'Confirm'];

export function AddPresetEnvironmentDialog({ open, onClose, onSuccess }: AddPresetEnvironmentDialogProps) {
  const [activeStep, setActiveStep] = useState(0);
  const [selectedPreset, setSelectedPreset] = useState<PresetEnvironmentInfo | null>(null);
  const [pat, setPat] = useState('');
  const [orgId, setOrgId] = useState('');
  const [customProperties, setCustomProperties] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<{
    valid: boolean;
    org_name?: string;
    error?: string;
  } | null>(null);

  // Fetch available presets
  const { data: presetsData, isLoading: loadingPresets } = useQuery({
    queryKey: ['preset-environments'],
    queryFn: environmentsApi.listPresetEnvironments,
    enabled: open,
  });

  // Validate credentials mutation
  const validateMutation = useMutation({
    mutationFn: (data: { pat: string; org_id: string; environment_url: string }) =>
      environmentsApi.validateCredentials(data),
    onSuccess: (result) => {
      setValidationResult(result);
      if (result.valid) {
        setError(null);
        setActiveStep(3); // Move to confirmation step
      } else {
        setError(result.error || 'Validation failed');
      }
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Validation failed');
      setValidationResult({ valid: false, error: err.response?.data?.detail });
    },
  });

  // Add preset environment mutation
  const addMutation = useMutation({
    mutationFn: (data: { name: string; pat: string; org_id: string; custom_properties?: Record<string, string> }) =>
      environmentsApi.addPresetEnvironment(data),
    onSuccess: () => {
      onSuccess();
      handleClose();
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to add environment');
    },
  });

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (!open) {
      setActiveStep(0);
      setSelectedPreset(null);
      setPat('');
      setOrgId('');
      setCustomProperties({});
      setError(null);
      setValidationResult(null);
    }
  }, [open]);

  const handleClose = () => {
    onClose();
  };

  const handleNext = () => {
    setError(null);

    if (activeStep === 0 && !selectedPreset) {
      setError('Please select a preset environment');
      return;
    }

    if (activeStep === 1) {
      if (!pat || !orgId) {
        setError('Please enter both PAT and Organization ID');
        return;
      }
      // Move to validation step
      setActiveStep(2);
      // Auto-trigger validation
      setTimeout(() => {
        if (selectedPreset) {
          validateMutation.mutate({
            pat,
            org_id: orgId,
            environment_url: selectedPreset.url,
          });
        }
      }, 100);
      return;
    }

    setActiveStep((prevStep) => prevStep + 1);
  };

  const handleBack = () => {
    setError(null);
    setActiveStep((prevStep) => prevStep - 1);
  };

  const handleConfirm = () => {
    if (!selectedPreset) return;

    addMutation.mutate({
      name: selectedPreset.name,
      pat,
      org_id: orgId,
      custom_properties: Object.keys(customProperties).length > 0 ? customProperties : undefined,
    });
  };

  const getAvailablePresets = () => {
    return presetsData?.presets.filter((p) => !p.is_configured) || [];
  };

  const renderStepContent = () => {
    switch (activeStep) {
      case 0: // Select Preset
        const availablePresets = getAvailablePresets();
        return (
          <Box sx={{ mt: 2 }}>
            {loadingPresets ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                <CircularProgress />
              </Box>
            ) : availablePresets.length === 0 ? (
              <Alert severity="info">
                All preset environments are already configured. You can add custom environments instead.
              </Alert>
            ) : (
              <>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Select a CloudBees environment to configure:
                </Typography>
                <List>
                  {availablePresets.map((preset) => (
                    <ListItem key={preset.name} disablePadding>
                      <ListItemButton
                        selected={selectedPreset?.name === preset.name}
                        onClick={() => setSelectedPreset(preset)}
                      >
                        <Radio checked={selectedPreset?.name === preset.name} />
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography variant="h6">{preset.name}</Typography>
                              <Chip
                                label={preset.flag_api_type === 'org' ? 'Org Flags' : 'App Flags'}
                                size="small"
                                color={preset.flag_api_type === 'org' ? 'warning' : 'primary'}
                              />
                            </Box>
                          }
                          secondary={
                            <Box>
                              <Typography variant="body2" color="text.secondary">
                                {preset.description}
                              </Typography>
                              <Typography
                                variant="caption"
                                fontFamily="monospace"
                                color="text.secondary"
                              >
                                {preset.url}
                              </Typography>
                            </Box>
                          }
                        />
                      </ListItemButton>
                    </ListItem>
                  ))}
                </List>
              </>
            )}
          </Box>
        );

      case 1: // Enter Credentials
        return (
          <Box sx={{ mt: 2 }}>
            <Alert severity="info" sx={{ mb: 3 }}>
              Enter your CloudBees credentials for <strong>{selectedPreset?.name}</strong>
            </Alert>

            <TextField
              fullWidth
              label="CloudBees Personal Access Token (PAT)"
              type="password"
              value={pat}
              onChange={(e) => setPat(e.target.value)}
              sx={{ mb: 2 }}
              placeholder="cb_pat_..."
              helperText="Your CloudBees personal access token"
            />

            <TextField
              fullWidth
              label="Organization ID"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              placeholder="e.g., 12345678-abcd-1234-abcd-123456789abc"
              helperText="CloudBees organization ID to validate credentials"
            />
          </Box>
        );

      case 2: // Validate
        return (
          <Box sx={{ mt: 2 }}>
            {validateMutation.isPending ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', p: 4 }}>
                <CircularProgress sx={{ mb: 2 }} />
                <Typography>Validating credentials...</Typography>
              </Box>
            ) : validationResult?.valid ? (
              <Alert severity="success" icon={<CheckCircle />}>
                <Typography variant="h6" gutterBottom>
                  Credentials Validated Successfully!
                </Typography>
                {validationResult.org_name && (
                  <Typography variant="body2">
                    Organization: <strong>{validationResult.org_name}</strong>
                  </Typography>
                )}
                <Typography variant="body2" sx={{ mt: 1 }}>
                  Click Next to confirm and add this environment.
                </Typography>
              </Alert>
            ) : (
              <Alert severity="error" icon={<ErrorIcon />}>
                <Typography variant="h6" gutterBottom>
                  Validation Failed
                </Typography>
                <Typography variant="body2">
                  {validationResult?.error || 'Please check your credentials and try again.'}
                </Typography>
              </Alert>
            )}
          </Box>
        );

      case 3: // Confirm
        return (
          <Box sx={{ mt: 2 }}>
            <Alert severity="info" sx={{ mb: 3 }}>
              Review and confirm your environment configuration
            </Alert>

            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                Environment
              </Typography>
              <Typography variant="h6" gutterBottom>
                {selectedPreset?.name}
              </Typography>

              <Typography variant="subtitle2" color="text.secondary" gutterBottom sx={{ mt: 2 }}>
                URL
              </Typography>
              <Typography variant="body2" fontFamily="monospace" gutterBottom>
                {selectedPreset?.url}
              </Typography>

              <Typography variant="subtitle2" color="text.secondary" gutterBottom sx={{ mt: 2 }}>
                Flag API Type
              </Typography>
              <Chip
                label={selectedPreset?.flag_api_type === 'org' ? 'Org Flags' : 'App Flags'}
                size="small"
                color={selectedPreset?.flag_api_type === 'org' ? 'warning' : 'primary'}
              />

              {validationResult?.org_name && (
                <>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom sx={{ mt: 2 }}>
                    Organization
                  </Typography>
                  <Typography variant="body2">{validationResult.org_name}</Typography>
                </>
              )}

              {selectedPreset?.default_properties && Object.keys(selectedPreset.default_properties).length > 0 && (
                <>
                  <Typography variant="subtitle2" color="text.secondary" gutterBottom sx={{ mt: 2 }}>
                    Default Properties
                  </Typography>
                  <List dense>
                    {Object.entries(selectedPreset.default_properties).map(([key, value]) => (
                      <ListItem key={key} sx={{ py: 0.5 }}>
                        <ListItemText
                          primary={
                            <Typography variant="body2" fontFamily="monospace">
                              {key} = {value}
                            </Typography>
                          }
                        />
                      </ListItem>
                    ))}
                  </List>
                </>
              )}
            </Paper>
          </Box>
        );

      default:
        return null;
    }
  };

  const canProceed = () => {
    switch (activeStep) {
      case 0:
        return selectedPreset !== null;
      case 1:
        return pat.length > 0 && orgId.length > 0;
      case 2:
        return validationResult?.valid || false;
      case 3:
        return true;
      default:
        return false;
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>Add Preset Environment</DialogTitle>
      <DialogContent>
        <Stepper activeStep={activeStep} sx={{ pt: 3, pb: 2 }}>
          {steps.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {error && (
          <Alert severity="error" sx={{ mt: 2, mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {renderStepContent()}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Box sx={{ flex: '1 1 auto' }} />
        {activeStep > 0 && activeStep !== 2 && (
          <Button onClick={handleBack} disabled={validateMutation.isPending || addMutation.isPending}>
            Back
          </Button>
        )}
        {activeStep < steps.length - 1 ? (
          <Button
            variant="contained"
            onClick={handleNext}
            disabled={!canProceed() || validateMutation.isPending}
          >
            {validateMutation.isPending ? <CircularProgress size={24} /> : 'Next'}
          </Button>
        ) : (
          <Button
            variant="contained"
            onClick={handleConfirm}
            disabled={!canProceed() || addMutation.isPending}
          >
            {addMutation.isPending ? <CircularProgress size={24} /> : 'Add Environment'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
