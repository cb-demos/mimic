/**
 * Configuration page - manage credentials and settings
 */

import { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  TextField,
  Button,
  Divider,
  Alert,
  CircularProgress,
  InputAdornment,
  IconButton,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
} from '@mui/material';
import { Visibility, VisibilityOff, CheckCircle, Error } from '@mui/icons-material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { configApi, environmentsApi } from '../api/endpoints';

export function ConfigPage() {
  const queryClient = useQueryClient();

  // GitHub state
  const [githubUsername, setGithubUsername] = useState('');
  const [githubToken, setGithubToken] = useState('');
  const [showGithubToken, setShowGithubToken] = useState(false);
  const [githubError, setGithubError] = useState<string | null>(null);
  const [githubSuccess, setGithubSuccess] = useState<string | null>(null);
  const [testingGithub, setTestingGithub] = useState(false);

  // CloudBees state
  const [selectedEnv, setSelectedEnv] = useState('');
  const [cloudbeesToken, setCloudbeesToken] = useState('');
  const [showCloudbeesToken, setShowCloudbeesToken] = useState(false);
  const [cloudbeesError, setCloudbeesError] = useState<string | null>(null);
  const [cloudbeesSuccess, setCloudbeesSuccess] = useState<string | null>(null);
  const [testingCloudbees, setTestingCloudbees] = useState(false);

  // Fetch GitHub config
  const { data: githubConfig, isLoading: loadingGithub } = useQuery({
    queryKey: ['github-config'],
    queryFn: configApi.getGithub,
  });

  // Fetch CloudBees config
  const { data: cloudbeesConfig, isLoading: loadingCloudbees } = useQuery({
    queryKey: ['cloudbees-config'],
    queryFn: configApi.getCloudbees,
  });

  // Fetch environments for selection
  const { data: environmentsData } = useQuery({
    queryKey: ['environments'],
    queryFn: environmentsApi.list,
  });

  // Initialize GitHub username from config
  useEffect(() => {
    if (githubConfig?.username) {
      setGithubUsername(githubConfig.username);
    }
  }, [githubConfig]);

  // Initialize selected environment
  useEffect(() => {
    if (environmentsData && !selectedEnv) {
      setSelectedEnv(environmentsData.current || '');
    }
  }, [environmentsData, selectedEnv]);

  // Save GitHub username
  const saveUsernameMutation = useMutation({
    mutationFn: (username: string) => configApi.setGithubUsername(username),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github-config'] });
      setGithubSuccess('GitHub username saved successfully');
      setGithubError(null);
    },
    onError: (err: any) => {
      setGithubError(err.response?.data?.detail || 'Failed to save GitHub username');
      setGithubSuccess(null);
    },
  });

  // Save GitHub token
  const saveTokenMutation = useMutation({
    mutationFn: (token: string) => configApi.setGithubToken(token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github-config'] });
      setGithubSuccess('GitHub token saved successfully');
      setGithubError(null);
      setGithubToken(''); // Clear token input after save
    },
    onError: (err: any) => {
      setGithubError(err.response?.data?.detail || 'Failed to save GitHub token');
      setGithubSuccess(null);
    },
  });

  // Save CloudBees token
  const saveCloudbeesMutation = useMutation({
    mutationFn: (data: { environment: string; token: string }) =>
      configApi.setCloubeesToken(data.environment, data.token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cloudbees-config'] });
      setCloudbeesSuccess('CloudBees token saved successfully');
      setCloudbeesError(null);
      setCloudbeesToken(''); // Clear token input after save
    },
    onError: (err: any) => {
      setCloudbeesError(err.response?.data?.detail || 'Failed to save CloudBees token');
      setCloudbeesSuccess(null);
    },
  });

  const handleSaveGithubUsername = () => {
    if (githubUsername) {
      saveUsernameMutation.mutate(githubUsername);
    }
  };

  const handleSaveGithubToken = () => {
    if (githubToken) {
      saveTokenMutation.mutate(githubToken);
    }
  };

  const handleTestGithubConnection = async () => {
    setTestingGithub(true);
    setGithubError(null);
    setGithubSuccess(null);
    try {
      // Save if values provided
      if (githubUsername && githubUsername !== githubConfig?.username) {
        await configApi.setGithubUsername(githubUsername);
      }
      if (githubToken) {
        await configApi.setGithubToken(githubToken);
      }

      const result = await configApi.getGithub();
      if (result.has_token && result.username) {
        setGithubSuccess('GitHub connection successful!');
        queryClient.invalidateQueries({ queryKey: ['github-config'] });
      } else {
        setGithubError('GitHub credentials incomplete');
      }
    } catch (err: any) {
      setGithubError(err.response?.data?.detail || 'Failed to test GitHub connection');
    } finally {
      setTestingGithub(false);
    }
  };

  const handleSaveCloudbeesToken = () => {
    if (selectedEnv && cloudbeesToken) {
      saveCloudbeesMutation.mutate({ environment: selectedEnv, token: cloudbeesToken });
    }
  };

  const handleTestCloudbeesConnection = async () => {
    setTestingCloudbees(true);
    setCloudbeesError(null);
    setCloudbeesSuccess(null);
    try {
      // Save token if provided
      if (cloudbeesToken && selectedEnv) {
        await configApi.setCloubeesToken(selectedEnv, cloudbeesToken);
      }

      const result = await configApi.getCloudbees();
      const env = result.environments.find((e) => e.name === selectedEnv);
      if (env?.has_token) {
        setCloudbeesSuccess('CloudBees connection successful!');
        queryClient.invalidateQueries({ queryKey: ['cloudbees-config'] });
      } else {
        setCloudbeesError('CloudBees token not set for this environment');
      }
    } catch (err: any) {
      setCloudbeesError(err.response?.data?.detail || 'Failed to test CloudBees connection');
    } finally {
      setTestingCloudbees(false);
    }
  };

  const getEnvStatus = (envName: string) => {
    const env = cloudbeesConfig?.environments.find((e) => e.name === envName);
    return env?.has_token;
  };

  return (
    <Container maxWidth="md">
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Configuration
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Manage GitHub and CloudBees credentials
        </Typography>
      </Box>

      {/* GitHub Section */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Typography variant="h5" sx={{ flexGrow: 1 }}>
            GitHub
          </Typography>
          {githubConfig?.has_token && githubConfig?.username && (
            <Chip icon={<CheckCircle />} label="Connected" color="success" size="small" />
          )}
        </Box>

        {githubSuccess && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setGithubSuccess(null)}>
            {githubSuccess}
          </Alert>
        )}

        {githubError && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setGithubError(null)}>
            {githubError}
          </Alert>
        )}

        {loadingGithub ? (
          <CircularProgress />
        ) : (
          <Grid container spacing={2}>
            <Grid size={{ xs: 12 }}>
              <TextField
                fullWidth
                label="GitHub Username"
                value={githubUsername}
                onChange={(e) => setGithubUsername(e.target.value)}
                helperText="Your GitHub username"
              />
              <Button
                variant="outlined"
                sx={{ mt: 1 }}
                onClick={handleSaveGithubUsername}
                disabled={
                  !githubUsername ||
                  githubUsername === githubConfig?.username ||
                  saveUsernameMutation.isPending
                }
              >
                {saveUsernameMutation.isPending ? <CircularProgress size={24} /> : 'Save Username'}
              </Button>
            </Grid>

            <Grid size={12}>
              <TextField
                fullWidth
                label="GitHub Personal Access Token"
                type={showGithubToken ? 'text' : 'password'}
                value={githubToken}
                onChange={(e) => setGithubToken(e.target.value)}
                helperText="Token with 'repo' scope"
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton onClick={() => setShowGithubToken(!showGithubToken)} edge="end">
                        {showGithubToken ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
              <Button
                variant="outlined"
                sx={{ mt: 1, mr: 1 }}
                onClick={handleSaveGithubToken}
                disabled={!githubToken || saveTokenMutation.isPending}
              >
                {saveTokenMutation.isPending ? <CircularProgress size={24} /> : 'Save Token'}
              </Button>
              <Button
                variant="contained"
                sx={{ mt: 1 }}
                onClick={handleTestGithubConnection}
                disabled={testingGithub}
              >
                {testingGithub ? <CircularProgress size={24} /> : 'Test Connection'}
              </Button>
            </Grid>
          </Grid>
        )}
      </Paper>

      {/* CloudBees Section */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h5" sx={{ mb: 2 }}>
          CloudBees
        </Typography>

        {cloudbeesSuccess && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setCloudbeesSuccess(null)}>
            {cloudbeesSuccess}
          </Alert>
        )}

        {cloudbeesError && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setCloudbeesError(null)}>
            {cloudbeesError}
          </Alert>
        )}

        {loadingCloudbees ? (
          <CircularProgress />
        ) : (
          <Grid container spacing={2}>
            <Grid size={12}>
              <FormControl fullWidth>
                <InputLabel>Environment</InputLabel>
                <Select
                  value={selectedEnv}
                  label="Environment"
                  onChange={(e) => {
                    setSelectedEnv(e.target.value);
                    setCloudbeesToken('');
                    setCloudbeesError(null);
                    setCloudbeesSuccess(null);
                  }}
                >
                  {environmentsData?.environments.map((env) => (
                    <MenuItem key={env.name} value={env.name}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                        {env.name}
                        {getEnvStatus(env.name) ? (
                          <CheckCircle color="success" fontSize="small" />
                        ) : (
                          <Error color="error" fontSize="small" />
                        )}
                      </Box>
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid size={12}>
              <TextField
                fullWidth
                label="CloudBees Personal Access Token"
                type={showCloudbeesToken ? 'text' : 'password'}
                value={cloudbeesToken}
                onChange={(e) => setCloudbeesToken(e.target.value)}
                helperText={`Token for ${selectedEnv} environment`}
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
                sx={{ mt: 1, mr: 1 }}
                onClick={handleSaveCloudbeesToken}
                disabled={!cloudbeesToken || !selectedEnv || saveCloudbeesMutation.isPending}
              >
                {saveCloudbeesMutation.isPending ? <CircularProgress size={24} /> : 'Save Token'}
              </Button>
              <Button
                variant="contained"
                sx={{ mt: 1 }}
                onClick={handleTestCloudbeesConnection}
                disabled={testingCloudbees}
              >
                {testingCloudbees ? <CircularProgress size={24} /> : 'Test Connection'}
              </Button>
            </Grid>

            {cloudbeesConfig && (
              <Grid size={12}>
                <Divider sx={{ my: 2 }} />
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Environment Status
                </Typography>
                {cloudbeesConfig.environments.map((env) => (
                  <Box key={env.name} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    {env.has_token ? (
                      <CheckCircle color="success" fontSize="small" sx={{ mr: 1 }} />
                    ) : (
                      <Error color="error" fontSize="small" sx={{ mr: 1 }} />
                    )}
                    <Typography variant="body2">
                      {env.name}: {env.has_token ? 'Token configured' : 'No token'}
                    </Typography>
                  </Box>
                ))}
              </Grid>
            )}
          </Grid>
        )}
      </Paper>
    </Container>
  );
}
