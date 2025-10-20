/**
 * Run scenario page - execute a scenario with parameters
 */

import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
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
} from '@mui/material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { scenariosApi } from '../api/endpoints';
import { ParameterForm } from '../components/ParameterForm';
import { ProgressDisplay } from '../components/ProgressDisplay';
import { useProgress } from '../hooks/useProgress';

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
  const [ttlDays, setTtlDays] = useState(7);
  const [dryRun, setDryRun] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [runName, setRunName] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch scenario details
  const { data: scenario, isLoading: loadingScenario } = useQuery({
    queryKey: ['scenario', scenarioId],
    queryFn: () => scenariosApi.get(scenarioId!),
    enabled: !!scenarioId,
  });

  // Use progress hook for SSE
  const { isConnected, isComplete } = useProgress(sessionId);

  // Run scenario mutation
  const runMutation = useMutation({
    mutationFn: (data: { parameters: Record<string, any>; ttl_days: number; dry_run: boolean }) =>
      scenariosApi.run(scenarioId!, data.parameters, data.ttl_days, data.dry_run),
    onSuccess: (result) => {
      setSessionId(result.session_id);
      setRunName(result.session_id);
      setIsRunning(true);
      setError(null);
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to start scenario execution');
      setIsRunning(false);
    },
  });

  // Handle parameter form submission
  const handleParametersSubmit = (parameters: Record<string, any>) => {
    runMutation.mutate({
      parameters,
      ttl_days: ttlDays,
      dry_run: dryRun,
    });
  };

  const handleRunAnother = () => {
    setSessionId(null);
    setRunName(null);
    setIsRunning(false);
    setError(null);
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
              Parameters
            </Typography>

            {scenario.scenario.parameter_schema && Object.keys(scenario.scenario.parameter_schema).length > 0 ? (
              <ParameterForm
                schema={scenario.scenario.parameter_schema}
                onSubmit={handleParametersSubmit}
                submitLabel="Run Scenario"
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
                {EXPIRATION_OPTIONS.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControlLabel
              control={
                <Checkbox checked={previewMode} onChange={(e) => setPreviewMode(e.target.checked)} />
              }
              label="Preview mode (show what will be created without creating)"
            />

            <FormControlLabel
              control={<Checkbox checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />}
              label="Dry run (test API calls without creating resources)"
            />

            {error && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {error}
              </Alert>
            )}

            {(!scenario.scenario.parameter_schema || Object.keys(scenario.scenario.parameter_schema).length === 0) && (
              <Box sx={{ display: 'flex', gap: 2, justifyContent: 'flex-end', mt: 3 }}>
                <Button variant="outlined" onClick={() => navigate('/scenarios')}>
                  Cancel
                </Button>
                <Button
                  variant="contained"
                  size="large"
                  onClick={() => handleParametersSubmit({})}
                  disabled={runMutation.isPending}
                >
                  {runMutation.isPending ? (
                    <>
                      <CircularProgress size={24} sx={{ mr: 1 }} />
                      Starting...
                    </>
                  ) : (
                    'Run Scenario'
                  )}
                </Button>
              </Box>
            )}
          </Paper>

          {/* Actions */}
          {(!scenario.scenario.parameter_schema || Object.keys(scenario.scenario.parameter_schema).length === 0) ? null : (
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
    </Container>
  );
}
