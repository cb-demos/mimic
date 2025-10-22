/**
 * Instances page - manage and clean up scenario instances
 */

import { useState, useMemo } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  InputAdornment,
  Switch,
  FormControlLabel,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
  IconButton,
  Collapse,
  List,
  ListItem,
  ListItemText,
  Link,
} from '@mui/material';
import {
  Search,
  Delete,
  ExpandMore,
  ExpandLess,
  Warning,
  OpenInNew,
} from '@mui/icons-material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { cleanupApi, environmentsApi } from '../api/endpoints';
import type { Session } from '../types/api';

type SortField = 'created_at' | 'expires_at' | 'instance_name' | 'scenario_id';
type SortDirection = 'asc' | 'desc';

export function CleanupPage() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEnv, setSelectedEnv] = useState('all');
  const [expiredOnly, setExpiredOnly] = useState(false);
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [cleanupDialogOpen, setCleanupDialogOpen] = useState(false);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [bulkCleanupDialogOpen, setBulkCleanupDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cleanupResults, setCleanupResults] = useState<any>(null);

  // Fetch environments for filter
  const { data: environmentsData } = useQuery({
    queryKey: ['environments'],
    queryFn: environmentsApi.list,
  });

  // Fetch sessions
  const { data: sessions, isLoading } = useQuery({
    queryKey: ['cleanup-sessions', selectedEnv, expiredOnly],
    queryFn: () => {
      const env = selectedEnv === 'all' ? undefined : selectedEnv;
      return cleanupApi.list({ environment: env, expired_only: expiredOnly });
    },
  });

  // Cleanup individual session
  const cleanupMutation = useMutation({
    mutationFn: (sessionId: string) => cleanupApi.cleanup(sessionId, { dry_run: false }),
    onSuccess: (results) => {
      setCleanupResults(results);
      queryClient.invalidateQueries({ queryKey: ['cleanup-sessions'] });
      setCleanupDialogOpen(false);
      setSelectedSession(null);
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Cleanup failed');
    },
  });

  // Bulk cleanup expired
  const bulkCleanupMutation = useMutation({
    mutationFn: () => cleanupApi.cleanupExpired({ dry_run: false }),
    onSuccess: (results) => {
      setCleanupResults(results);
      queryClient.invalidateQueries({ queryKey: ['cleanup-sessions'] });
      setBulkCleanupDialogOpen(false);
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Bulk cleanup failed');
    },
  });

  // Filter and sort sessions
  const filteredSessions = useMemo(() => {
    if (!sessions?.sessions) return [];

    let filtered = sessions.sessions.filter((session) => {
      // Search filter
      const matchesSearch =
        !searchQuery ||
        session.session_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        session.instance_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        session.scenario_id.toLowerCase().includes(searchQuery.toLowerCase());

      return matchesSearch;
    });

    // Sort
    filtered.sort((a: Session, b: Session) => {
      let aVal: any = a[sortField as keyof Session];
      let bVal: any = b[sortField as keyof Session];

      if (sortField === 'created_at' || sortField === 'expires_at') {
        aVal = new Date(aVal as string).getTime();
        bVal = new Date(bVal as string).getTime();
      }

      if (sortDirection === 'asc') {
        return aVal < bVal ? -1 : 1;
      }
      return aVal > bVal ? -1 : 1;
    });

    return filtered;
  }, [sessions?.sessions, searchQuery, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  const handleCleanup = (session: Session) => {
    setSelectedSession(session);
    setCleanupDialogOpen(true);
  };

  const handleConfirmCleanup = () => {
    if (selectedSession) {
      cleanupMutation.mutate(selectedSession.session_id);
    }
  };

  const handleBulkCleanup = () => {
    setBulkCleanupDialogOpen(true);
  };

  const handleConfirmBulkCleanup = () => {
    bulkCleanupMutation.mutate();
  };

  const isExpired = (expiresAt: string | null) => {
    if (!expiresAt) return false;
    return new Date(expiresAt) < new Date();
  };

  const expiredCount = sessions?.sessions.filter((s: Session) => isExpired(s.expires_at || null)).length || 0;

  return (
    <Container maxWidth="lg">
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Instances
          </Typography>
          <Typography variant="body1" color="text.secondary">
            View and manage scenario instances
          </Typography>
        </Box>
        <Button
          variant="contained"
          color="warning"
          startIcon={<Delete />}
          onClick={handleBulkCleanup}
          disabled={expiredCount === 0}
        >
          Clean All Expired ({expiredCount})
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {cleanupResults && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setCleanupResults(null)}>
          Cleanup complete: {cleanupResults.cleaned_count || cleanupResults.results?.length || 0}{' '}
          resource(s) deleted
        </Alert>
      )}

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField
            size="small"
            placeholder="Search sessions..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            sx={{ flexGrow: 1, minWidth: 250 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
          />

          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Environment</InputLabel>
            <Select
              value={selectedEnv}
              label="Environment"
              onChange={(e) => setSelectedEnv(e.target.value)}
            >
              <MenuItem value="all">All Environments</MenuItem>
              {environmentsData?.environments.map((env) => (
                <MenuItem key={env.name} value={env.name}>
                  {env.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControlLabel
            control={
              <Switch checked={expiredOnly} onChange={(e) => setExpiredOnly(e.target.checked)} />
            }
            label="Expired only"
          />
        </Box>
      </Paper>

      {/* Sessions Table */}
      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : filteredSessions.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">
            {searchQuery || expiredOnly ? 'No sessions match your filters' : 'No sessions found'}
          </Typography>
        </Paper>
      ) : (
        <Paper>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell width="40" />
                  <TableCell>
                    <TableSortLabel
                      active={sortField === 'instance_name'}
                      direction={sortField === 'instance_name' ? sortDirection : 'asc'}
                      onClick={() => handleSort('instance_name')}
                    >
                      Run Name
                    </TableSortLabel>
                  </TableCell>
                  <TableCell>
                    <TableSortLabel
                      active={sortField === 'scenario_id'}
                      direction={sortField === 'scenario_id' ? sortDirection : 'asc'}
                      onClick={() => handleSort('scenario_id')}
                    >
                      Scenario
                    </TableSortLabel>
                  </TableCell>
                  <TableCell>Environment</TableCell>
                  <TableCell>
                    <TableSortLabel
                      active={sortField === 'created_at'}
                      direction={sortField === 'created_at' ? sortDirection : 'asc'}
                      onClick={() => handleSort('created_at')}
                    >
                      Created
                    </TableSortLabel>
                  </TableCell>
                  <TableCell>
                    <TableSortLabel
                      active={sortField === 'expires_at'}
                      direction={sortField === 'expires_at' ? sortDirection : 'asc'}
                      onClick={() => handleSort('expires_at')}
                    >
                      Expires
                    </TableSortLabel>
                  </TableCell>
                  <TableCell>Resources</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredSessions.map((session: Session) => (
                  <>
                    <TableRow key={session.session_id} hover>
                      <TableCell>
                        <IconButton
                          size="small"
                          onClick={() =>
                            setExpandedRow(
                              expandedRow === session.session_id ? null : session.session_id
                            )
                          }
                        >
                          {expandedRow === session.session_id ? <ExpandLess /> : <ExpandMore />}
                        </IconButton>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {session.instance_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" fontFamily="monospace">
                          {session.session_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {session.scenario_id}
                        </Typography>
                      </TableCell>
                      <TableCell>{session.environment}</TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {new Date(session.created_at).toLocaleDateString()}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {session.expires_at ? (
                          <Box>
                            <Typography variant="body2">
                              {new Date(session.expires_at).toLocaleDateString()}
                            </Typography>
                            {isExpired(session.expires_at) && (
                              <Chip label="Expired" size="small" color="error" />
                            )}
                          </Box>
                        ) : (
                          <Chip label="Never" size="small" />
                        )}
                      </TableCell>
                      <TableCell>
                        <Chip label={session.resources?.length || 0} size="small" />
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          size="small"
                          color="error"
                          variant="outlined"
                          onClick={() => handleCleanup(session)}
                          startIcon={<Delete />}
                        >
                          Clean Up
                        </Button>
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell colSpan={8} sx={{ py: 0, borderBottom: 'none' }}>
                        <Collapse in={expandedRow === session.session_id}>
                          <Box sx={{ p: 2, bgcolor: 'action.hover' }}>
                            <Typography variant="subtitle2" gutterBottom>
                              Resources ({session.resources?.length || 0})
                            </Typography>
                            {session.resources && session.resources.length > 0 ? (
                              <List dense>
                                {session.resources.map((resource, idx: number) => (
                                  <ListItem key={idx}>
                                    <ListItemText
                                      primary={
                                        resource.url ? (
                                          <Link
                                            href={resource.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            underline="hover"
                                            sx={{
                                              display: 'inline-flex',
                                              alignItems: 'center',
                                              gap: 0.5,
                                              fontFamily: 'monospace',
                                              fontSize: '0.875rem',
                                            }}
                                          >
                                            {resource.name}
                                            <OpenInNew sx={{ fontSize: '0.875rem' }} />
                                          </Link>
                                        ) : (
                                          <Typography
                                            component="span"
                                            sx={{ fontFamily: 'monospace', fontSize: '0.875rem' }}
                                          >
                                            {resource.name}
                                          </Typography>
                                        )
                                      }
                                      secondary={`${resource.type} • ID: ${resource.id}${resource.org_id ? ` • Org: ${resource.org_id}` : ''}`}
                                    />
                                  </ListItem>
                                ))}
                              </List>
                            ) : (
                              <Typography variant="body2" color="text.secondary">
                                No resources
                              </Typography>
                            )}
                          </Box>
                        </Collapse>
                      </TableCell>
                    </TableRow>
                  </>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Cleanup Confirmation Dialog */}
      <Dialog open={cleanupDialogOpen} onClose={() => setCleanupDialogOpen(false)}>
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Warning color="warning" />
            Confirm Cleanup
          </Box>
        </DialogTitle>
        <DialogContent>
          {selectedSession && (
            <>
              <Typography gutterBottom>
                Are you sure you want to clean up this session?
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                <strong>Run Name:</strong> {selectedSession.instance_name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <strong>Resources:</strong> {selectedSession.resources?.length || 0}
              </Typography>
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCleanupDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleConfirmCleanup}
            disabled={cleanupMutation.isPending}
          >
            {cleanupMutation.isPending ? <CircularProgress size={24} /> : 'Clean Up'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bulk Cleanup Dialog */}
      <Dialog open={bulkCleanupDialogOpen} onClose={() => setBulkCleanupDialogOpen(false)}>
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Warning color="warning" />
            Confirm Bulk Cleanup
          </Box>
        </DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            Clean up all expired sessions?
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            <strong>Sessions to clean:</strong> {expiredCount}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBulkCleanupDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleConfirmBulkCleanup}
            disabled={bulkCleanupMutation.isPending}
          >
            {bulkCleanupMutation.isPending ? <CircularProgress size={24} /> : 'Clean Up All'}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
