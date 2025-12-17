/**
 * Configuration page - manage credentials and settings
 */

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router';
import {
  Box,
  Container,
  Typography,
  Paper,
  TextField,
  Button,
  Alert,
  CircularProgress,
  InputAdornment,
  IconButton,
  Grid,
  Chip,
} from '@mui/material';
import { Visibility, VisibilityOff, CheckCircle, Error, Settings } from '@mui/icons-material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { configApi } from '../api/endpoints';
import { ErrorAlert, type ErrorInfo } from '../components/ErrorAlert';
import { toErrorInfo } from '../utils/errorUtils';

export function ConfigPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // GitHub state
  const [githubUsername, setGithubUsername] = useState('');
  const [githubToken, setGithubToken] = useState('');
  const [showGithubToken, setShowGithubToken] = useState(false);
  const [githubError, setGithubError] = useState<ErrorInfo | null>(null);
  const [githubSuccess, setGithubSuccess] = useState<string | null>(null);
  const [testingGithub, setTestingGithub] = useState(false);

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

  // Initialize GitHub username from config
  useEffect(() => {
    if (githubConfig?.username) {
      setGithubUsername(githubConfig.username);
    }
  }, [githubConfig]);

  // Save GitHub username
  const saveUsernameMutation = useMutation({
    mutationFn: (username: string) => configApi.setGithubUsername(username),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['github-config'] });
      setGithubSuccess('GitHub username saved successfully');
      setGithubError(null);
    },
    onError: (err: any) => {
      setGithubError(toErrorInfo(err));
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
      setGithubError(toErrorInfo(err));
      setGithubSuccess(null);
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
        setGithubError({ message: 'GitHub credentials incomplete' });
      }
    } catch (err: any) {
      setGithubError(toErrorInfo(err));
    } finally {
      setTestingGithub(false);
    }
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
          <ErrorAlert error={githubError} onClose={() => setGithubError(null)} />
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
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Typography variant="h5">
            CloudBees
          </Typography>
          <Button
            variant="contained"
            startIcon={<Settings />}
            onClick={() => navigate('/tenants')}
          >
            Manage in Tenants
          </Button>
        </Box>

        <Alert severity="info" sx={{ mb: 2 }}>
          CloudBees credentials are now managed in the Tenants page where you can update tokens directly for each tenant.
        </Alert>

        {loadingCloudbees ? (
          <CircularProgress />
        ) : cloudbeesConfig ? (
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Credential Status
            </Typography>
            {cloudbeesConfig.tenants.map((env) => (
              <Box key={env.name} sx={{ display: 'flex', alignItems: 'center', mb: 1, mt: 1 }}>
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
          </Box>
        ) : null}
      </Paper>
    </Container>
  );
}
