/**
 * Dashboard page - overview and quick actions
 */

import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Button,
  List,
  ListItem,
  ListItemText,
  Chip,
  Alert,
  CircularProgress,
  Divider,
} from '@mui/material';
import {
  PlayArrow,
  Delete,
  Refresh,
  CheckCircle,
  Error,
  Warning,
  Flag,
  CloudQueue,
  Folder,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import {
  scenariosApi,
  cleanupApi,
  packsApi,
  environmentsApi,
  configApi,
} from '../api/endpoints';
import type { Session } from '../types/api';

export function DashboardPage() {
  const navigate = useNavigate();

  // Fetch all data in parallel
  const { data: scenarios } = useQuery({
    queryKey: ['scenarios'],
    queryFn: scenariosApi.list,
  });

  const { data: sessions } = useQuery({
    queryKey: ['cleanup-sessions'],
    queryFn: () => cleanupApi.list({ expired_only: false }),
  });

  const { data: packs } = useQuery({
    queryKey: ['scenario-packs'],
    queryFn: packsApi.list,
  });

  const { data: environments } = useQuery({
    queryKey: ['environments'],
    queryFn: environmentsApi.list,
  });

  const { data: githubConfig } = useQuery({
    queryKey: ['github-config'],
    queryFn: configApi.getGithub,
  });

  const { data: cloudbeesConfig } = useQuery({
    queryKey: ['cloudbees-config'],
    queryFn: configApi.getCloudbees,
  });

  const isExpired = (expiresAt: string | null | undefined) => {
    if (!expiresAt) return false;
    return new Date(expiresAt) < new Date();
  };

  const isExpiringSoon = (expiresAt: string | null | undefined) => {
    if (!expiresAt) return false;
    const daysUntilExpiry =
      (new Date(expiresAt).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24);
    return daysUntilExpiry > 0 && daysUntilExpiry < 2;
  };

  const activeSessions = sessions?.sessions.filter((s: Session) => !isExpired(s.expires_at)) || [];
  const expiredSessions = sessions?.sessions.filter((s: Session) => isExpired(s.expires_at)) || [];
  const expiringSoon = sessions?.sessions.filter((s: Session) => isExpiringSoon(s.expires_at)) || [];
  const recentSessions = [...(sessions?.sessions || [])].slice(0, 5);

  const currentEnv = environments?.current;
  const currentEnvHasToken = cloudbeesConfig?.environments.find(
    (e) => e.name === currentEnv
  )?.has_token;

  const githubConnected = githubConfig?.has_token && githubConfig?.username;

  const isLoading =
    !scenarios || !sessions || !packs || !environments || !githubConfig || !cloudbeesConfig;

  return (
    <Container maxWidth="lg">
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Overview of your Mimic environment
        </Typography>
      </Box>

      {/* Connection Status */}
      {!isLoading && (!githubConnected || !currentEnvHasToken) && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          {!githubConnected && !currentEnvHasToken
            ? 'GitHub and CloudBees credentials not configured. '
            : !githubConnected
              ? 'GitHub credentials not configured. '
              : 'CloudBees credentials not configured for current environment. '}
          <Button color="inherit" size="small" onClick={() => navigate('/config')}>
            Configure Now
          </Button>
        </Alert>
      )}

      {/* Expiring Soon Alert */}
      {expiringSoon.length > 0 && (
        <Alert severity="info" icon={<Warning />} sx={{ mb: 3 }}>
          {expiringSoon.length} session(s) expiring in less than 2 days.{' '}
          <Button color="inherit" size="small" onClick={() => navigate('/cleanup')}>
            View Sessions
          </Button>
        </Alert>
      )}

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          {/* Stats Cards */}
          <Grid container spacing={3} sx={{ mb: 4 }}>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <CloudQueue color="primary" sx={{ mr: 1 }} />
                    <Typography variant="h6">Sessions</Typography>
                  </Box>
                  <Typography variant="h3">{activeSessions.length}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Active • {expiredSessions.length} expired
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <Flag color="primary" sx={{ mr: 1 }} />
                    <Typography variant="h6">Scenarios</Typography>
                  </Box>
                  <Typography variant="h3">{scenarios?.scenarios.length || 0}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Available scenarios
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <Folder color="primary" sx={{ mr: 1 }} />
                    <Typography variant="h6">Packs</Typography>
                  </Box>
                  <Typography variant="h3">{packs?.packs.length || 0}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    Installed packs
                  </Typography>
                </CardContent>
              </Card>
            </Grid>

            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <CloudQueue color="primary" sx={{ mr: 1 }} />
                    <Typography variant="h6">Environment</Typography>
                  </Box>
                  <Typography variant="h6" sx={{ mb: 1 }}>
                    {currentEnv}
                  </Typography>
                  <Chip
                    icon={currentEnvHasToken ? <CheckCircle /> : <Error />}
                    label={currentEnvHasToken ? 'Connected' : 'Not configured'}
                    color={currentEnvHasToken ? 'success' : 'error'}
                    size="small"
                  />
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Grid container spacing={3}>
            {/* Quick Actions */}
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 3, height: '100%' }}>
                <Typography variant="h6" gutterBottom>
                  Quick Actions
                </Typography>
                <List>
                  <ListItem sx={{ px: 0 }}>
                    <Button
                      variant="contained"
                      fullWidth
                      startIcon={<PlayArrow />}
                      onClick={() => navigate('/scenarios')}
                      sx={{ justifyContent: 'flex-start' }}
                    >
                      Run New Scenario
                    </Button>
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <Button
                      variant="outlined"
                      fullWidth
                      startIcon={<Delete />}
                      onClick={() => navigate('/cleanup')}
                      disabled={expiredSessions.length === 0}
                      sx={{ justifyContent: 'flex-start' }}
                    >
                      Cleanup Expired ({expiredSessions.length})
                    </Button>
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <Button
                      variant="outlined"
                      fullWidth
                      startIcon={<Refresh />}
                      onClick={() => navigate('/packs')}
                      sx={{ justifyContent: 'flex-start' }}
                    >
                      Update Scenario Packs
                    </Button>
                  </ListItem>
                </List>

                <Divider sx={{ my: 2 }} />

                <Typography variant="subtitle2" gutterBottom color="text.secondary">
                  Connection Status
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {githubConnected ? (
                      <CheckCircle color="success" fontSize="small" sx={{ mr: 1 }} />
                    ) : (
                      <Error color="error" fontSize="small" sx={{ mr: 1 }} />
                    )}
                    <Typography variant="body2">
                      GitHub: {githubConnected ? 'Connected' : 'Not configured'}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {currentEnvHasToken ? (
                      <CheckCircle color="success" fontSize="small" sx={{ mr: 1 }} />
                    ) : (
                      <Error color="error" fontSize="small" sx={{ mr: 1 }} />
                    )}
                    <Typography variant="body2">
                      CloudBees ({currentEnv}): {currentEnvHasToken ? 'Connected' : 'Not configured'}
                    </Typography>
                  </Box>
                </Box>
              </Paper>
            </Grid>

            {/* Recent Sessions */}
            <Grid size={{ xs: 12, md: 6 }}>
              <Paper sx={{ p: 3, height: '100%' }}>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mb: 2,
                  }}
                >
                  <Typography variant="h6">Recent Sessions</Typography>
                  <Button size="small" onClick={() => navigate('/cleanup')}>
                    View All
                  </Button>
                </Box>
                {recentSessions.length === 0 ? (
                  <Typography color="text.secondary" align="center" sx={{ py: 4 }}>
                    No sessions yet. Run a scenario to get started!
                  </Typography>
                ) : (
                  <List>
                    {recentSessions.map((session: Session) => (
                      <ListItem
                        key={session.session_id}
                        sx={{
                          px: 0,
                          borderBottom: '1px solid',
                          borderColor: 'divider',
                          '&:last-child': { borderBottom: 'none' },
                        }}
                      >
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              {session.instance_name}
                              {isExpired(session.expires_at) && (
                                <Chip label="Expired" size="small" color="error" />
                              )}
                              {isExpiringSoon(session.expires_at) && (
                                <Chip label="Expiring soon" size="small" color="warning" />
                              )}
                            </Box>
                          }
                          secondary={
                            <>
                              {session.scenario_id} • {session.environment}
                              <br />
                              {new Date(session.created_at).toLocaleDateString()} •{' '}
                              {session.resources?.length || 0} resources
                            </>
                          }
                        />
                      </ListItem>
                    ))}
                  </List>
                )}
              </Paper>
            </Grid>
          </Grid>
        </>
      )}
    </Container>
  );
}
