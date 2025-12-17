/**
 * Setup page - first-run wizard
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Paper,
  Stepper,
  Step,
  StepLabel,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  InputAdornment,
  IconButton,
} from '@mui/material';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import { useMutation, useQuery } from '@tanstack/react-query';
import { setupApi, configApi, tenantsApi, packsApi } from '../api/endpoints';
import type { RunSetupRequest, Environment } from '../types/api';
import { ErrorAlert, type ErrorInfo } from '../components/ErrorAlert';
import { toErrorInfo } from '../utils/errorUtils';

const STEPS = ['GitHub Setup', 'Select Tenant', 'CloudBees Setup', 'Scenario Pack (Optional)'];

interface SetupData {
  githubToken: string;
  githubUsername: string;
  environment: string;
  cloudbeesToken: string;
  scenarioPack?: {
    name: string;
    gitUrl: string;
  };
}

export function SetupPage() {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const [setupData, setSetupData] = useState<SetupData>({
    githubToken: '',
    githubUsername: '',
    environment: '',
    cloudbeesToken: '',
  });
  const [showGithubToken, setShowGithubToken] = useState(false);
  const [showCloudbeesToken, setShowCloudbeesToken] = useState(false);
  const [packName, setPackName] = useState('');
  const [packUrl, setPackUrl] = useState('');
  const [error, setError] = useState<ErrorInfo | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testSuccess, setTestSuccess] = useState<string | null>(null);

  // Fetch environments for step 2
  const { data: environmentsData, isLoading: loadingEnvs } = useQuery({
    queryKey: ['environments'],
    queryFn: tenantsApi.list,
  });

  // Test GitHub connection
  const testGithubConnection = async () => {
    setTestingConnection(true);
    setError(null);
    setTestSuccess(null);
    try {
      await configApi.setGithubToken(setupData.githubToken);
      await configApi.setGithubUsername(setupData.githubUsername);
      const result = await configApi.getGithub();
      if (result.has_token && result.username) {
        setTestSuccess('GitHub connection successful!');
      } else {
        setError({ message: 'Failed to verify GitHub credentials' });
      }
    } catch (err: any) {
      setError(toErrorInfo(err));
    } finally {
      setTestingConnection(false);
    }
  };

  // Test CloudBees connection
  const testCloudbeesConnection = async () => {
    setTestingConnection(true);
    setError(null);
    setTestSuccess(null);
    try {
      await configApi.setCloubeesToken(setupData.environment, setupData.cloudbeesToken);
      const result = await configApi.getCloudbees();
      const env = result.tenants.find(e => e.name === setupData.environment);
      if (env?.has_token) {
        setTestSuccess('CloudBees connection successful!');
      } else {
        setError({ message: 'Failed to verify CloudBees credentials' });
      }
    } catch (err: any) {
      setError(toErrorInfo(err));
    } finally {
      setTestingConnection(false);
    }
  };

  // Run setup mutation
  const setupMutation = useMutation({
    mutationFn: async (data: RunSetupRequest) => {
      const result = await setupApi.runSetup(data);

      // If scenario pack is provided, add it
      if (packName && packUrl) {
        await packsApi.add(packName, packUrl);
      }

      return result;
    },
    onSuccess: () => {
      navigate('/');
    },
    onError: (err: any) => {
      setError(toErrorInfo(err));
    },
  });

  const handleNext = async () => {
    setError(null);
    setTestSuccess(null);

    // Validate current step
    if (activeStep === 0) {
      if (!setupData.githubToken || !setupData.githubUsername) {
        setError({ message: 'GitHub token and username are required' });
        return;
      }
    } else if (activeStep === 1) {
      if (!setupData.environment) {
        setError({ message: 'Please select an environment' });
        return;
      }
    } else if (activeStep === 2) {
      if (!setupData.cloudbeesToken) {
        setError({ message: 'CloudBees PAT is required' });
        return;
      }
    }

    if (activeStep === STEPS.length - 1) {
      // Last step - run setup
      await setupMutation.mutateAsync({
        github_token: setupData.githubToken,
        github_username: setupData.githubUsername,
        environment: setupData.environment,
        cloudbees_token: setupData.cloudbeesToken,
      });
    } else {
      setActiveStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    setError(null);
    setTestSuccess(null);
    setActiveStep((prev) => prev - 1);
  };

  const renderStepContent = () => {
    switch (activeStep) {
      case 0:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              GitHub Credentials
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Enter your GitHub username and Personal Access Token. The token needs <code>repo</code> scope.
            </Typography>

            <TextField
              fullWidth
              label="GitHub Username"
              value={setupData.githubUsername}
              onChange={(e) =>
                setSetupData({ ...setupData, githubUsername: e.target.value })
              }
              sx={{ mb: 2 }}
              autoComplete="username"
            />

            <TextField
              fullWidth
              label="GitHub Personal Access Token"
              type={showGithubToken ? 'text' : 'password'}
              value={setupData.githubToken}
              onChange={(e) =>
                setSetupData({ ...setupData, githubToken: e.target.value })
              }
              sx={{ mb: 2 }}
              autoComplete="off"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowGithubToken(!showGithubToken)}
                      edge="end"
                    >
                      {showGithubToken ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            <Button
              variant="outlined"
              onClick={testGithubConnection}
              disabled={!setupData.githubToken || !setupData.githubUsername || testingConnection}
            >
              {testingConnection ? <CircularProgress size={24} /> : 'Test Connection'}
            </Button>
          </Box>
        );

      case 1:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Select CloudBees Tenant
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Choose the CloudBees tenant you want to use.
            </Typography>

            {loadingEnvs ? (
              <CircularProgress />
            ) : (
              <FormControl fullWidth>
                <InputLabel>Tenant</InputLabel>
                <Select
                  value={setupData.environment}
                  label="Tenant"
                  onChange={(e) =>
                    setSetupData({ ...setupData, environment: e.target.value })
                  }
                >
                  {environmentsData?.tenants.map((env: Environment) => (
                    <MenuItem key={env.name} value={env.name}>
                      {env.name} ({env.url})
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
          </Box>
        );

      case 2:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              CloudBees Personal Access Token
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Enter your CloudBees PAT for the <strong>{setupData.environment}</strong> tenant.
            </Typography>

            <TextField
              fullWidth
              label="CloudBees PAT"
              type={showCloudbeesToken ? 'text' : 'password'}
              value={setupData.cloudbeesToken}
              onChange={(e) =>
                setSetupData({ ...setupData, cloudbeesToken: e.target.value })
              }
              sx={{ mb: 2 }}
              autoComplete="off"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowCloudbeesToken(!showCloudbeesToken)}
                      edge="end"
                    >
                      {showCloudbeesToken ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            <Button
              variant="outlined"
              onClick={testCloudbeesConnection}
              disabled={!setupData.cloudbeesToken || testingConnection}
            >
              {testingConnection ? <CircularProgress size={24} /> : 'Test Connection'}
            </Button>
          </Box>
        );

      case 3:
        return (
          <Box>
            <Typography variant="h6" gutterBottom>
              Add Scenario Pack (Optional)
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              You can add a scenario pack now or skip this step and add one later from the Scenario Packs page.
            </Typography>

            <TextField
              fullWidth
              label="Pack Name"
              value={packName}
              onChange={(e) => setPackName(e.target.value)}
              sx={{ mb: 2 }}
              placeholder="e.g., my-scenarios"
            />

            <TextField
              fullWidth
              label="Git URL"
              value={packUrl}
              onChange={(e) => setPackUrl(e.target.value)}
              placeholder="e.g., https://github.com/username/repo.git"
              helperText="HTTPS or SSH Git URL"
            />
          </Box>
        );

      default:
        return null;
    }
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ mt: 8, mb: 4, textAlign: 'center' }}>
        <Typography variant="h3" gutterBottom>
          Welcome to Mimic
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Let's get you set up in just a few steps
        </Typography>
      </Box>

      <Paper sx={{ p: 4 }}>
        <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
          {STEPS.map((label) => (
            <Step key={label}>
              <StepLabel>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        {error && <ErrorAlert error={error} onClose={() => setError(null)} />}

        {testSuccess && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setTestSuccess(null)}>
            {testSuccess}
          </Alert>
        )}

        <Box sx={{ mb: 4 }}>{renderStepContent()}</Box>

        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Button disabled={activeStep === 0} onClick={handleBack}>
            Back
          </Button>
          <Button
            variant="contained"
            onClick={handleNext}
            disabled={setupMutation.isPending}
          >
            {setupMutation.isPending ? (
              <CircularProgress size={24} />
            ) : activeStep === STEPS.length - 1 ? (
              'Complete Setup'
            ) : (
              'Next'
            )}
          </Button>
        </Box>
      </Paper>
    </Container>
  );
}
