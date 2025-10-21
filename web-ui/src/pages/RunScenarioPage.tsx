/**
 * Run scenario page - execute a scenario with parameters
 * Implements CLI-parity flow: credentials → properties → preview → execution
 */

import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Autocomplete,
  Box,
  Container,
  Typography,
  Paper,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Checkbox,
  Divider,
  Alert,
  CircularProgress,
  Chip,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  TextField,
} from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { configApi, scenariosApi } from '../api/endpoints';
import { ParameterForm } from '../components/ParameterForm';
import { ProgressDisplay } from '../components/ProgressDisplay';
import { PropertyCheckDialog } from '../components/PropertyCheckDialog';
import { PreviewDialog } from '../components/PreviewDialog';
import { CredentialValidationStatus } from '../components/CredentialValidationStatus';
import { useProgress } from '../hooks/useProgress';
import type {
  CachedOrg,
  CheckPropertiesResponse,
  ScenarioPreviewResponse,
  ValidateAllCredentialsResponse,
} from '../types/api';

const EXPIRATION_OPTIONS = [
  { value: 1, label: '1 day' },
  { value: 7, label: '7 days' },
  { value: 14, label: '14 days' },
  { value: 30, label: '30 days' },
  { value: 0, label: 'Never' },
];

export function RunScenarioPage() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const navigate = useNavigate();

  // Form state
  const [organizationId, setOrganizationId] = useState('');
  const [orgInputValue, setOrgInputValue] = useState('');
  const [inviteeUsername, setInviteeUsername] = useState('');
  const [ttlDays, setTtlDays] = useState(7);
  const [dryRun, setDryRun] = useState(false);
  const [parameters, setParameters] = useState<Record<string, any>>({});

  // Execution state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [runName, setRunName] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [orgFetchError, setOrgFetchError] = useState<string | null>(null);

  // Credential validation state
  const [isValidatingCredentials, setIsValidatingCredentials] = useState(false);
  const [credentialValidation, setCredentialValidation] =
    useState<ValidateAllCredentialsResponse | null>(null);

  // Property check state
  const [showPropertyDialog, setShowPropertyDialog] = useState(false);
  const [propertyCheckResult, setPropertyCheckResult] = useState<CheckPropertiesResponse | null>(
    null
  );

  // Preview state
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState<ScenarioPreviewResponse | null>(null);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  // Cached data
  const [cachedOrgs, setCachedOrgs] = useState<CachedOrg[]>([]);
  const [expirationOptions, setExpirationOptions] = useState<Array<{ value: number; label: string }>>(
    EXPIRATION_OPTIONS
  );

  // Load cached organizations on mount
  useEffect(() => {
    const loadCachedOrgs = async () => {
      try {
        const response = await configApi.getCachedOrgs();
        setCachedOrgs(response.orgs);
      } catch (err) {
        console.error('Failed to load cached organizations:', err);
      }
    };
    loadCachedOrgs();
  }, []);

  // Load recent expiration values on mount
  useEffect(() => {
    const loadRecentExpirations = async () => {
      try {
        const response = await configApi.getRecentValues('expiration_days');
        const recentOptions = response.values
          .map((v) => {
            const days = parseInt(v, 10);
            return isNaN(days) ? null : { value: days, label: `${days} days` };
          })
          .filter((opt): opt is { value: number; label: string } => opt !== null);

        const allOptions = [...recentOptions, ...EXPIRATION_OPTIONS];
        const seen = new Set<number>();
        const uniqueOptions = allOptions.filter((opt) => {
          if (seen.has(opt.value)) return false;
          seen.add(opt.value);
          return true;
        });

        setExpirationOptions(uniqueOptions);
      } catch (err) {
        console.error('Failed to load recent expiration values:', err);
      }
    };
    loadRecentExpirations();
  }, []);

  // Validate credentials on organization selection
  useEffect(() => {
    if (organizationId && !isValidatingCredentials) {
      validateCredentials();
    }
  }, [organizationId]);

  // Fetch scenario details
  const { data: scenario, isLoading: loadingScenario } = useQuery({
    queryKey: ['scenario', scenarioId],
    queryFn: () => scenariosApi.get(scenarioId!),
    enabled: !!scenarioId,
  });

  // Use progress hook for SSE
  const { isConnected, isComplete } = useProgress(sessionId);

  // Validate credentials
  const validateCredentials = async () => {
    if (!organizationId.trim()) return;

    setIsValidatingCredentials(true);
    setCredentialValidation(null);
    setError(null);

    try {
      // Get credentials from config
      const githubConfig = await configApi.getGitHubConfig();
      const cloudbeesConfig = await configApi.getCloudBeesConfig();

      if (!githubConfig.has_token) {
        setError('GitHub token not configured. Please configure it in the Config page.');
        setIsValidatingCredentials(false);
        return;
      }

      const currentEnv = localStorage.getItem('current_environment') || 'prod';
      const envCredentials = cloudbeesConfig.environments.find((env) => env.name === currentEnv);

      if (!envCredentials?.has_token) {
        setError(
          `CloudBees token not configured for environment '${currentEnv}'. Please configure it in the Config page.`
        );
        setIsValidatingCredentials(false);
        return;
      }

      // For now, we can't validate without actual tokens (they're in keyring)
      // So we'll skip validation and let the backend handle it
      // TODO: Add a way to get tokens from backend for validation
      setIsValidatingCredentials(false);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to validate credentials');
      setIsValidatingCredentials(false);
    }
  };

  // Check properties
  const checkProperties = async () => {
    if (!organizationId.trim() || !scenarioId) return null;

    try {
      const result = await scenariosApi.checkProperties(scenarioId, {
        organization_id: organizationId,
      });

      setPropertyCheckResult(result);

      // If there are missing properties, show the dialog
      if (result.missing_properties.length > 0 || result.missing_secrets.length > 0) {
        setShowPropertyDialog(true);
        return null;
      }

      return result;
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to check properties');
      return null;
    }
  };

  // Load preview
  const loadPreview = async (params: Record<string, any>) => {
    if (!scenarioId) return null;

    setIsLoadingPreview(true);
    setError(null);

    try {
      const preview = await scenariosApi.previewScenario(scenarioId, {
        organization_id: organizationId,
        parameters: params,
      });

      setPreviewData(preview);
      return preview;
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load preview');
      return null;
    } finally {
      setIsLoadingPreview(false);
    }
  };

  // Run scenario mutation
  const runMutation = useMutation({
    mutationFn: async () => {
      return scenariosApi.run(scenarioId!, organizationId, parameters, ttlDays, dryRun, inviteeUsername || undefined);
    },
    onSuccess: (result) => {
      setSessionId(result.session_id);
      setRunName(result.session_id);
      setIsRunning(true);
      setError(null);
      setShowPreview(false);

      // Save organization ID and expiration to recent values
      if (organizationId) {
        configApi.addRecentValue('expiration_days', ttlDays.toString()).catch(console.error);
      }
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to start scenario execution');
      setIsRunning(false);
    },
  });

  // Handle parameter form submission - starts the execution flow
  const handleParametersSubmit = async (params: Record<string, any>) => {
    if (!organizationId.trim()) {
      setError('CloudBees Organization ID is required');
      return;
    }

    setParameters(params);
    setError(null);

    // For dry run mode, skip all checks and go straight to execution
    if (dryRun) {
      runMutation.mutate();
      return;
    }

    // Step 1: Check properties
    const propertyCheckPassed = await checkProperties();
    if (propertyCheckPassed === null) {
      // Properties dialog is showing, wait for user to create them
      return;
    }

    // Step 2: Load and show preview
    const preview = await loadPreview(params);
    if (preview) {
      setShowPreview(true);
    }
  };

  // Handle properties created - continue to preview
  const handlePropertiesCreated = async () => {
    setShowPropertyDialog(false);

    // Load and show preview (use current parameters state)
    const preview = await loadPreview(parameters);
    if (preview) {
      setShowPreview(true);
    }
  };

  // Handle preview confirmation - execute the scenario
  const handlePreviewConfirm = () => {
    runMutation.mutate();
  };

  // Handle organization autocomplete change (when option is selected from dropdown)
  const handleOrgChange = async (_event: any, value: string | CachedOrg | null) => {
    if (typeof value === 'object' && value !== null) {
      // User selected a cached org from the dropdown
      setOrganizationId(value.org_id);
      // Update display to show formatted version
      const displayValue = `${value.display_name} (${value.org_id.substring(0, 8)}...)`;
      setOrgInputValue(displayValue);
    } else if (typeof value === 'string') {
      // User typed and pressed Enter (freeSolo mode)
      setOrganizationId(value);
      setOrgInputValue(value);
    } else {
      // User cleared the field
      setOrganizationId('');
      setOrgInputValue('');
    }
  };

  // Handle organization input blur - fetch org name for new entries
  const handleOrgBlur = async () => {
    const trimmedId = organizationId.trim();

    // Only fetch if:
    // 1. Org ID is not empty
    // 2. It's not already in cached orgs (i.e., it's a new entry)
    if (!trimmedId || cachedOrgs.some((org) => org.org_id === trimmedId)) {
      return;
    }

    try {
      setOrgFetchError(null);
      const response = await configApi.fetchOrgName(trimmedId);

      // Update cached orgs (this persists via backend)
      setCachedOrgs((prev) => [
        ...prev.filter((org) => org.org_id !== response.org_id),
        { org_id: response.org_id, display_name: response.display_name },
      ]);

      // Update the input display to show "Name (ID...)" format
      const displayValue = `${response.display_name} (${response.org_id.substring(0, 8)}...)`;
      setOrgInputValue(displayValue);
    } catch (err) {
      setOrgFetchError('Invalid organization ID');
    }
  };

  const handleRunAnother = () => {
    setSessionId(null);
    setRunName(null);
    setIsRunning(false);
    setError(null);
    setCredentialValidation(null);
    setPropertyCheckResult(null);
    setPreviewData(null);
  };

  const handleViewCleanup = () => {
    navigate('/cleanup');
  };

  if (loadingScenario) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  if (!scenario) {
    return (
      <Container maxWidth="lg">
        <Alert severity="error">Scenario not found</Alert>
      </Container>
    );
  }

  const expirationLabel =
    ttlDays === 0 ? 'Never' : `${ttlDays} day${ttlDays > 1 ? 's' : ''}`;

  return (
    <Container maxWidth="lg">
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Typography variant="h4">{scenario.scenario.name}</Typography>
          {scenario.scenario.wip && <Chip label="WIP" size="small" color="warning" />}
        </Box>
        <Typography variant="body1" color="text.secondary">
          {scenario.scenario.summary}
        </Typography>
        <Box sx={{ mt: 1, display: 'flex', gap: 1 }}>
          <Chip label={scenario.scenario.id} size="small" variant="outlined" />
          {scenario.scenario.scenario_pack && (
            <Chip label={scenario.scenario.scenario_pack} size="small" variant="outlined" />
          )}
        </Box>
      </Box>

      {!isRunning && !isComplete && (
        <>
          {/* Configuration Form */}
          <Paper sx={{ p: 3, mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Configuration
            </Typography>

            <Autocomplete
              freeSolo
              options={cachedOrgs}
              getOptionLabel={(option) =>
                typeof option === 'string'
                  ? option
                  : `${option.display_name} (${option.org_id.substring(0, 8)}...)`
              }
              value={cachedOrgs.find((org) => org.org_id === organizationId) || null}
              inputValue={orgInputValue}
              onChange={handleOrgChange}
              onInputChange={(_event, value) => {
                // Update both the actual org ID and the display value when typing
                setOrganizationId(value);
                setOrgInputValue(value);

                // Clear org fetch error when user starts typing
                if (orgFetchError) {
                  setOrgFetchError(null);
                }
              }}
              onBlur={handleOrgBlur}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="CloudBees Organization"
                  required
                  helperText={
                    orgFetchError ||
                    'Select from recent organizations or enter a new organization ID'
                  }
                  error={!!orgFetchError || (!organizationId.trim() && !!error)}
                />
              )}
              sx={{ mb: 2 }}
            />

            {/* Credential validation status */}
            {credentialValidation && (
              <CredentialValidationStatus
                isValidating={isValidatingCredentials}
                validationResult={credentialValidation}
                error={null}
              />
            )}

            <TextField
              fullWidth
              label="Invitee Username (Optional)"
              value={inviteeUsername}
              onChange={(e) => setInviteeUsername(e.target.value)}
              helperText="Optional: GitHub username to invite as collaborator to created repositories"
              sx={{ mb: 3 }}
            />

            <Divider sx={{ my: 3 }} />

            <Typography variant="h6" gutterBottom>
              Scenario Parameters
            </Typography>

            {scenario.scenario.parameter_schema &&
            Object.keys(scenario.scenario.parameter_schema.properties || {}).length > 0 ? (
              <ParameterForm
                schema={scenario.scenario.parameter_schema}
                onSubmit={handleParametersSubmit}
                submitLabel={dryRun ? 'Show Preview (Dry Run)' : 'Run Scenario'}
              />
            ) : (
              <Typography variant="body2" color="text.secondary">
                This scenario does not require any parameters.
              </Typography>
            )}

            <Divider sx={{ my: 3 }} />

            <Typography variant="h6" gutterBottom>
              Options
            </Typography>

            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Expiration</InputLabel>
              <Select
                value={ttlDays}
                label="Expiration"
                onChange={(e) => setTtlDays(e.target.value as number)}
              >
                {expirationOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControlLabel
              control={<Checkbox checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />}
              label="Dry run (show preview without creating resources)"
            />

            {error && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {error}
              </Alert>
            )}

            {(!scenario.scenario.parameter_schema ||
              Object.keys(scenario.scenario.parameter_schema.properties || {}).length === 0) && (
              <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 3 }}>
                <Button variant="outlined" onClick={() => navigate('/scenarios')}>
                  Cancel
                </Button>
                <Button
                  variant="contained"
                  size="large"
                  onClick={() => handleParametersSubmit({})}
                  disabled={runMutation.isPending || isLoadingPreview}
                >
                  {runMutation.isPending || isLoadingPreview ? (
                    <>
                      <CircularProgress size={24} sx={{ mr: 1 }} />
                      {isLoadingPreview ? 'Loading Preview...' : 'Starting...'}
                    </>
                  ) : dryRun ? (
                    'Show Preview (Dry Run)'
                  ) : (
                    'Run Scenario'
                  )}
                </Button>
              </Box>
            )}
          </Paper>

          {/* Actions */}
          {(!scenario.scenario.parameter_schema ||
            Object.keys(scenario.scenario.parameter_schema.properties || {}).length === 0) ? null : (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button variant="outlined" onClick={() => navigate('/scenarios')}>
                Cancel
              </Button>
            </Box>
          )}
        </>
      )}

      {/* Progress Display */}
      {(isRunning || isComplete) && sessionId && (
        <>
          <Paper sx={{ p: 3, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6">
                {isComplete ? 'Execution Complete' : 'Executing Scenario'}
              </Typography>
              {!isComplete && (
                <Chip
                  label={isConnected ? 'Connected' : 'Connecting...'}
                  color={isConnected ? 'success' : 'default'}
                  size="small"
                />
              )}
            </Box>

            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Session ID: <code>{sessionId}</code>
              </Typography>
              {runName && (
                <Typography variant="body2" color="text.secondary">
                  Run Name: <strong>{runName}</strong>
                </Typography>
              )}
            </Box>

            <ProgressDisplay sessionId={sessionId} />

            {isComplete && (
              <Alert severity="success" sx={{ mt: 2 }}>
                Scenario execution completed successfully!
              </Alert>
            )}
          </Paper>

          {isComplete && (
            <Card sx={{ mb: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Next Steps
                </Typography>
                <List>
                  <ListItem>
                    <ListItemText
                      primary="View Resources"
                      secondary="Check the created resources in the Cleanup page"
                    />
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Run Another Scenario"
                      secondary="Configure and execute another scenario"
                    />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          )}

          {/* Actions */}
          {isComplete && (
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
              <Button variant="outlined" onClick={handleViewCleanup}>
                View in Cleanup
              </Button>
              <Button variant="contained" onClick={handleRunAnother}>
                Run Another
              </Button>
            </Box>
          )}
        </>
      )}

      {/* Property Check Dialog */}
      {propertyCheckResult && (
        <PropertyCheckDialog
          open={showPropertyDialog}
          onClose={() => setShowPropertyDialog(false)}
          organizationId={organizationId}
          missingProperties={propertyCheckResult.missing_properties}
          missingSecrets={propertyCheckResult.missing_secrets}
          onPropertiesCreated={handlePropertiesCreated}
        />
      )}

      {/* Preview Dialog */}
      {previewData && (
        <PreviewDialog
          open={showPreview}
          onClose={() => setShowPreview(false)}
          onConfirm={handlePreviewConfirm}
          preview={previewData}
          scenarioName={scenario.scenario.name}
          environment={localStorage.getItem('current_environment') || 'prod'}
          expirationLabel={expirationLabel}
          isSubmitting={runMutation.isPending}
        />
      )}
    </Container>
  );
}
