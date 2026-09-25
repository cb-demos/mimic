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
  Tooltip,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';
import {
  Search,
  Delete,
  PlaylistRemove,
  ExpandMore,
  ExpandLess,
  Warning,
} from '@mui/icons-material';
import { ResourceList } from '../components/ResourceList';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { cleanupApi, tenantsApi } from '../api/endpoints';
import type { CleanupResponse, CleanupResult, Session } from '../types/api';
import { ErrorAlert, type ErrorInfo } from '../components/ErrorAlert';
import { toErrorInfo } from '../utils/errorUtils';

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
  const [error, setError] = useState<ErrorInfo | null>(null);
  const [cleanupResults, setCleanupResults] = useState<CleanupResponse | null>(null);

  // Fetch environments for filter
  const { data: environmentsData } = useQuery({
    queryKey: ['environments'],
    queryFn: tenantsApi.list,
  });

  // Fetch sessions
  const { data: sessions, isLoading } = useQuery({
    queryKey: ['cleanup-sessions', selectedEnv, expiredOnly],
    queryFn: () => {
      const env = selectedEnv === 'all' ? undefined : selectedEnv;
      return cleanupApi.list({ tenant: env, expired_only: expiredOnly });
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
      setError(toErrorInfo(err));
    },
  });

  // Dry-run preview shown in the confirmation dialog (nothing is deleted)
  const previewMutation = useMutation({
    mutationFn: (sessionId: string) => cleanupApi.cleanup(sessionId, { dry_run: true }),
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
      setError(toErrorInfo(err));
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
    previewMutation.reset();
    previewMutation.mutate(session.session_id);
  };

  const handleCloseCleanupDialog = () => {
    setCleanupDialogOpen(false);
    previewMutation.reset();
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

  const expiredSessions =
    sessions?.sessions.filter((s: Session) => isExpired(s.expires_at || null)) || [];
  const expiredCount = expiredSessions.length;
  const expiredTotals = expiredSessions.reduce(
    (acc, s) => ({
      deleteCount: acc.deleteCount + (s.delete_count ?? s.resource_count),
      keepCount: acc.keepCount + (s.keep_count ?? 0) + (s.conditional_count ?? 0),
    }),
    { deleteCount: 0, keepCount: 0 }
  );

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

      {error && <ErrorAlert error={error} onClose={() => setError(null)} />}

      {cleanupResults && (
        <CleanupResultBanner results={cleanupResults} onClose={() => setCleanupResults(null)} />
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
            <InputLabel>Tenant</InputLabel>
            <Select
              value={selectedEnv}
              label="Tenant"
              onChange={(e) => setSelectedEnv(e.target.value)}
            >
              <MenuItem value="all">All Tenants</MenuItem>
              {environmentsData?.tenants.map((env) => (
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
                  <TableCell>Tenant</TableCell>
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
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="body2" fontWeight="medium">
                            {session.instance_name}
                          </Typography>
                          {session.status === 'failed' && (
                            <Tooltip title="This run stopped before finishing. Resources it created before stopping are tracked and can be cleaned up.">
                              <Chip label="Failed run" size="small" color="error" />
                            </Tooltip>
                          )}
                          {session.status === 'in_progress' && (
                            <Tooltip title="This run did not finish recording its results (it may still be running, or was interrupted).">
                              <Chip label="Incomplete" size="small" color="warning" />
                            </Tooltip>
                          )}
                        </Box>
                        <Typography variant="caption" color="text.secondary" fontFamily="monospace">
                          {session.session_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {session.scenario_id}
                        </Typography>
                      </TableCell>
                      <TableCell>{session.tenant}</TableCell>
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
                        <ResourceCountChips session={session} />
                      </TableCell>
                      <TableCell align="right">
                        {(session.delete_count ?? session.resource_count) === 0 ? (
                          <Tooltip title="Nothing to delete: every resource is kept. This only removes the run from the list.">
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => handleCleanup(session)}
                              startIcon={<PlaylistRemove />}
                            >
                              Remove
                            </Button>
                          </Tooltip>
                        ) : (
                          <Button
                            size="small"
                            color="error"
                            variant="outlined"
                            onClick={() => handleCleanup(session)}
                            startIcon={<Delete />}
                          >
                            Clean Up
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell colSpan={8} sx={{ py: 0, borderBottom: 'none' }}>
                        <Collapse in={expandedRow === session.session_id}>
                          <Box sx={{ p: 2, bgcolor: 'action.hover' }}>
                            <ResourceList
                              resources={session.resources || []}
                              showHeader={true}
                              showCleanupOutcome={true}
                            />
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
      <Dialog open={cleanupDialogOpen} onClose={handleCloseCleanupDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Warning color="warning" />
            Confirm Cleanup
          </Box>
        </DialogTitle>
        <DialogContent>
          {selectedSession && (
            <>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                <strong>Run Name:</strong> {selectedSession.instance_name}
              </Typography>
              <CleanupPreview
                isLoading={previewMutation.isPending}
                error={previewMutation.error}
                preview={previewMutation.data}
              />
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseCleanupDialog}>Cancel</Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleConfirmCleanup}
            disabled={cleanupMutation.isPending || previewMutation.isPending}
          >
            {cleanupMutation.isPending ? (
              <CircularProgress size={24} />
            ) : previewMutation.data && previewMutation.data.deleted_count === 0 ? (
              'Remove'
            ) : (
              'Clean Up'
            )}
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
          <Typography variant="body2" color="text.secondary">
            <strong>Resources to delete:</strong> {expiredTotals.deleteCount}
            {' · '}
            <strong>Kept or deleted only if unused</strong> (pre-existing, shared or flags):{' '}
            {expiredTotals.keepCount}
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

const RESOURCE_TYPE_LABELS: Record<string, string> = {
  github_repo: 'GitHub repo',
  cloudbees_component: 'Component',
  cloudbees_environment: 'Environment',
  cloudbees_application: 'Application',
  cloudbees_flag: 'Feature flag',
  session: 'Session',
};

function describeResult(r: CleanupResult): string {
  const type = RESOURCE_TYPE_LABELS[r.resource_type] || r.resource_type;
  return `${type}: ${r.resource_name || r.resource_id}`;
}

/** "3 to delete · 2 kept" chips for the Resources column */
function ResourceCountChips({ session }: { session: Session }) {
  const deleteCount = session.delete_count ?? session.resource_count;
  const keepCount = session.keep_count ?? 0;
  const conditionalCount = session.conditional_count ?? 0;
  return (
    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
      <Tooltip title="Resources this run created; cleanup deletes them">
        <Chip label={`${deleteCount} to delete`} size="small" color={deleteCount ? 'error' : 'default'} variant="outlined" />
      </Tooltip>
      {conditionalCount > 0 && (
        <Tooltip title="A shared application this run created (and its flags): deleted only if nothing else is still attached. Open Clean Up to see the live answer.">
          <Chip label={`${conditionalCount} if unused`} size="small" color="warning" variant="outlined" />
        </Tooltip>
      )}
      {keepCount > 0 && (
        <Tooltip title="Pre-existing resources, shared applications and feature flags; cleanup keeps them">
          <Chip label={`${keepCount} kept`} size="small" />
        </Tooltip>
      )}
    </Box>
  );
}

/** Dry-run preview listing what cleanup will delete and keep */
function CleanupPreview({
  isLoading,
  error,
  preview,
}: {
  isLoading: boolean;
  error: unknown;
  preview?: CleanupResponse;
}) {
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 2 }}>
        <CircularProgress size={18} />
        <Typography variant="body2">Checking what will be deleted...</Typography>
      </Box>
    );
  }
  if (error) {
    return (
      <Alert severity="warning" sx={{ mt: 2 }}>
        Could not preview this cleanup. Pre-existing, shared and flag resources are still kept,
        but review the resource list before continuing.
      </Alert>
    );
  }
  if (!preview) return null;

  const willDelete = preview.results.filter((r) => r.status === 'success');
  const willKeep = preview.results.filter((r) => r.status === 'skipped');
  const problems = preview.results.filter((r) => r.status === 'error');

  return (
    <Box sx={{ mt: 2 }}>
      {willDelete.length === 0 ? (
        <Alert severity="info" sx={{ mb: 2 }}>
          Nothing will be deleted. This run did not create any resources that cleanup removes;
          cleaning up only removes the run from this list.
        </Alert>
      ) : (
        <>
          <Typography variant="subtitle2" color="error">
            Will be deleted ({willDelete.length})
          </Typography>
          <List dense disablePadding sx={{ mb: 2 }}>
            {willDelete.map((r) => (
              <ListItem key={`del-${r.resource_type}-${r.resource_id}`} sx={{ py: 0 }}>
                <ListItemText primary={describeResult(r)} secondary={r.message} />
              </ListItem>
            ))}
          </List>
        </>
      )}
      {willKeep.length > 0 && (
        <>
          <Typography variant="subtitle2">Will be kept ({willKeep.length})</Typography>
          <List dense disablePadding>
            {willKeep.map((r) => (
              <ListItem key={`keep-${r.resource_type}-${r.resource_id}`} sx={{ py: 0 }}>
                <ListItemText primary={describeResult(r)} secondary={r.message} />
              </ListItem>
            ))}
          </List>
        </>
      )}
      {problems.length > 0 && (
        <Alert severity="warning" sx={{ mt: 2 }}>
          {problems.length} resource(s) could not be checked:{' '}
          {problems.map((r) => describeResult(r)).join(', ')}
        </Alert>
      )}
    </Box>
  );
}

/** Accurate post-cleanup summary: deleted / kept / already gone / failed */
function CleanupResultBanner({
  results,
  onClose,
}: {
  results: CleanupResponse;
  onClose: () => void;
}) {
  const deleted = results.deleted_count ?? 0;
  const kept = results.kept_count ?? 0;
  const alreadyGone = results.already_gone_count ?? 0;
  const failed = results.failed_count ?? 0;
  const failures = results.results.filter((r) => r.status === 'error');

  const parts = [`${deleted} deleted`];
  if (kept) parts.push(`${kept} kept (pre-existing, shared or flags)`);
  if (alreadyGone) parts.push(`${alreadyGone} already gone`);
  if (failed) parts.push(`${failed} failed`);

  const severity = failed > 0 ? 'warning' : deleted === 0 ? 'info' : 'success';

  return (
    <Alert severity={severity} sx={{ mb: 3 }} onClose={onClose}>
      Cleanup complete: {parts.join(' · ')}
      {failures.length > 0 && (
        <Box component="ul" sx={{ m: 0, mt: 1, pl: 2 }}>
          {failures.map((r) => (
            <li key={`fail-${r.resource_type}-${r.resource_id}`}>
              {describeResult(r)}: {r.message}
            </li>
          ))}
        </Box>
      )}
    </Alert>
  );
}
