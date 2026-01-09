/**
 * Scenario Packs page - manage scenario packs
 */

import { useState } from 'react';
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
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  IconButton,
  Switch,
  Chip,
  Alert,
  CircularProgress,
  Autocomplete,
} from '@mui/material';
import { Add, Delete, Refresh, Link as LinkIcon, AccountTree, CallMerge, SwapHoriz } from '@mui/icons-material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { packsApi } from '../api/endpoints';
import type { ScenarioPack, AddScenarioPackRequest } from '../types/api';
import { ErrorAlert, type ErrorInfo } from '../components/ErrorAlert';
import { toErrorInfo } from '../utils/errorUtils';
import { BranchPRSelector } from '../components/BranchPRSelector';

// Type for Autocomplete options
type RefOption =
  | {
      type: 'branch';
      label: string;
      branch: string;
      group: string;
      isDefault: boolean;
      protected: boolean;
    }
  | {
      type: 'pr';
      label: string;
      branch: string;
      prNumber: number;
      prTitle: string;
      prAuthor: string;
      prHeadRepoUrl: string | null;
      group: string;
    };

export function PacksPage() {
  const queryClient = useQueryClient();
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [switchDialogOpen, setSwitchDialogOpen] = useState(false);
  const [selectedPack, setSelectedPack] = useState<string | null>(null);
  const [selectedPackForSwitch, setSelectedPackForSwitch] = useState<ScenarioPack | null>(null);
  const [newPackName, setNewPackName] = useState('');
  const [newPackUrl, setNewPackUrl] = useState('');
  const [selectedRef, setSelectedRef] = useState<{
    type: 'branch' | 'pr';
    branch: string;
    prNumber?: number;
    prTitle?: string;
    prAuthor?: string;
    prHeadRepoUrl?: string | null;
  } | null>(null);
  const [error, setError] = useState<ErrorInfo | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Fetch packs
  const { data: packs, isLoading } = useQuery({
    queryKey: ['scenario-packs'],
    queryFn: packsApi.list,
  });

  // Helper to check if URL is a git URL
  const isGitUrl = (url: string) => {
    return (
      url.startsWith('https://') ||
      url.startsWith('http://') ||
      url.startsWith('git@') ||
      url.startsWith('ssh://') ||
      url.startsWith('git://')
    );
  };

  // Fetch refs for Add Pack dialog
  const { data: refs, isLoading: isLoadingRefs } = useQuery({
    queryKey: ['discover-refs', newPackUrl],
    queryFn: () => packsApi.discoverRefs(newPackUrl),
    enabled: addDialogOpen && isGitUrl(newPackUrl),
  });

  // Add pack mutation
  const addMutation = useMutation({
    mutationFn: (data: AddScenarioPackRequest) => packsApi.addPack(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scenario-packs'] });
      queryClient.invalidateQueries({ queryKey: ['scenarios'] });
      setSuccess('Scenario pack added successfully');
      setAddDialogOpen(false);
      setNewPackName('');
      setNewPackUrl('');
      setSelectedRef(null);
      setError(null);
    },
    onError: (err: any) => {
      setError(toErrorInfo(err));
    },
  });

  // Remove pack mutation
  const removeMutation = useMutation({
    mutationFn: (packName: string) => packsApi.remove(packName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scenario-packs'] });
      queryClient.invalidateQueries({ queryKey: ['scenarios'] });
      setSuccess('Scenario pack removed successfully');
      setRemoveDialogOpen(false);
      setSelectedPack(null);
      setError(null);
    },
    onError: (err: any) => {
      setError(toErrorInfo(err));
    },
  });

  // Enable/disable pack mutation
  const toggleMutation = useMutation({
    mutationFn: (data: { packName: string; enabled: boolean }) =>
      packsApi.setEnabled(data.packName, data.enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scenario-packs'] });
      queryClient.invalidateQueries({ queryKey: ['scenarios'] });
      setError(null);
    },
    onError: (err: any) => {
      setError(toErrorInfo(err));
    },
  });

  // Update pack mutation
  const updateMutation = useMutation({
    mutationFn: (packName?: string) => packsApi.update(packName),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['scenario-packs'] });
      queryClient.invalidateQueries({ queryKey: ['scenarios'] });
      const updated = result.updated?.length || 0;
      const errors = Object.keys(result.errors || {}).length;
      setSuccess(
        `Update complete: ${updated} pack(s) updated${errors > 0 ? `, ${errors} error(s)` : ''}`
      );
      setError(null);
    },
    onError: (err: any) => {
      setError(toErrorInfo(err));
    },
  });

  // Switch ref mutation
  const switchRefMutation = useMutation({
    mutationFn: ({ packName, request }: { packName: string; request: { branch?: string; pr_number?: number } }) =>
      packsApi.switchRef(packName, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scenario-packs'] });
      queryClient.invalidateQueries({ queryKey: ['scenarios'] });
      setSuccess('Successfully switched branch/PR');
      setSwitchDialogOpen(false);
      setSelectedPackForSwitch(null);
      setError(null);
    },
    onError: (err: any) => {
      setError(toErrorInfo(err));
    },
  });

  const handleRemove = (packName: string) => {
    setSelectedPack(packName);
    setRemoveDialogOpen(true);
  };

  const handleConfirmRemove = () => {
    if (selectedPack) {
      removeMutation.mutate(selectedPack);
    }
  };

  const handleToggle = (packName: string, enabled: boolean) => {
    toggleMutation.mutate({ packName, enabled });
  };

  const handleUpdateAll = () => {
    updateMutation.mutate(undefined);
  };

  const handleUpdatePack = (packName: string) => {
    updateMutation.mutate(packName);
  };

  const handleSwitchRef = (pack: ScenarioPack) => {
    setSelectedPackForSwitch(pack);
    setSwitchDialogOpen(true);
  };

  const handleConfirmSwitch = (selection: {
    type: 'branch' | 'pr';
    branch: string;
    prNumber?: number;
  }) => {
    if (!selectedPackForSwitch) return;

    const request = selection.type === 'branch'
      ? { branch: selection.branch }
      : { pr_number: selection.prNumber };

    switchRefMutation.mutate({
      packName: selectedPackForSwitch.name,
      request,
    });
  };

  const isLocalPath = (path: string) => {
    return (
      path.startsWith('/') || // Absolute path
      path.startsWith('~/') || // Home directory
      path.startsWith('./') || // Relative path
      path.startsWith('../') ||// Parent directory
      path.startsWith('file://') // Explicit file:// scheme
    );
  };

  const isValidLocation = (location: string) => {
    return isGitUrl(location) || isLocalPath(location);
  };

  const getLocationType = (location: string) => {
    if (location.startsWith('file://')) {
      return 'local';
    }
    if (isGitUrl(location)) {
      return 'git';
    }
    if (isLocalPath(location)) {
      return 'local';
    }
    return 'unknown';
  };

  const getLocationLabel = (location: string) => {
    const type = getLocationType(location);
    if (type === 'local') {
      return location.replace('file://', '');
    }
    return location;
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Scenario Packs
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Manage installed scenario packs
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={handleUpdateAll}
            disabled={updateMutation.isPending || !packs?.packs.length}
          >
            {updateMutation.isPending ? 'Updating...' : 'Update All'}
          </Button>
          <Button variant="contained" startIcon={<Add />} onClick={() => setAddDialogOpen(true)}>
            Add Pack
          </Button>
        </Box>
      </Box>

      {error && <ErrorAlert error={error} onClose={() => setError(null)} />}

      {success && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccess(null)}>
          {success}
        </Alert>
      )}

      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : !packs || packs.packs.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary" gutterBottom>
            No scenario packs installed
          </Typography>
          <Button
            variant="contained"
            startIcon={<Add />}
            onClick={() => setAddDialogOpen(true)}
            sx={{ mt: 2 }}
          >
            Add Your First Pack
          </Button>
        </Paper>
      ) : (
        <Paper>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Enabled</TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell>Location</TableCell>
                  <TableCell>Current Ref</TableCell>
                  <TableCell>Scenarios</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {packs.packs.map((pack: ScenarioPack) => (
                  <TableRow key={pack.name} hover>
                    <TableCell>
                      <Switch
                        checked={pack.enabled}
                        onChange={(e) => handleToggle(pack.name, e.target.checked)}
                        disabled={toggleMutation.isPending}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body1" fontWeight="medium">
                        {pack.name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <LinkIcon fontSize="small" color="action" />
                        <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                          <Typography
                            variant="body2"
                            fontFamily="monospace"
                            fontSize="0.875rem"
                            sx={{
                              maxWidth: 400,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {getLocationLabel(pack.git_url)}
                          </Typography>
                          <Chip
                            label={getLocationType(pack.git_url)}
                            size="small"
                            variant="outlined"
                            sx={{ maxWidth: 'fit-content', mt: 0.5, textTransform: 'capitalize' }}
                          />
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      {getLocationType(pack.git_url) === 'git' && pack.current_ref ? (
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          {pack.current_ref.type === 'pr' ? (
                            <Chip
                              icon={<CallMerge fontSize="small" />}
                              label={`PR #${pack.current_ref.pr_number}: ${pack.current_ref.pr_title || 'Untitled'}`}
                              size="small"
                              color="secondary"
                              sx={{
                                maxWidth: 200,
                                '& .MuiChip-label': {
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                },
                              }}
                            />
                          ) : (
                            <Chip
                              icon={<AccountTree fontSize="small" />}
                              label={pack.current_ref.branch}
                              size="small"
                              variant="outlined"
                            />
                          )}
                        </Box>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          N/A
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      <Chip label={pack.scenario_count} size="small" color="primary" />
                    </TableCell>
                    <TableCell align="right">
                      {getLocationType(pack.git_url) === 'git' && (
                        <Button
                          size="small"
                          startIcon={<SwapHoriz />}
                          onClick={() => handleSwitchRef(pack)}
                          disabled={switchRefMutation.isPending}
                          sx={{ mr: 1 }}
                        >
                          Switch
                        </Button>
                      )}
                      <Button
                        size="small"
                        startIcon={<Refresh />}
                        onClick={() => handleUpdatePack(pack.name)}
                        disabled={updateMutation.isPending}
                      >
                        Update
                      </Button>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => handleRemove(pack.name)}
                        disabled={removeMutation.isPending}
                        sx={{ ml: 1 }}
                      >
                        <Delete />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Add Pack Dialog */}
      <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Scenario Pack</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Add a scenario pack from a Git repository or local directory.
            Git packs will be cloned, while local packs use symlinks for instant access.
          </Typography>

          <TextField
            fullWidth
            label="Pack Name"
            value={newPackName}
            onChange={(e) => setNewPackName(e.target.value)}
            sx={{ mb: 2 }}
            placeholder="e.g., my-scenarios"
            helperText="A unique name for this pack"
          />

          <TextField
            fullWidth
            label="Location"
            value={newPackUrl}
            onChange={(e) => {
              setNewPackUrl(e.target.value);
              setSelectedRef(null); // Clear selection when URL changes
            }}
            placeholder="e.g., https://github.com/user/repo.git or /Users/me/scenarios"
            helperText={
              newPackUrl
                ? `Type: ${getLocationType(newPackUrl)} ${!isValidLocation(newPackUrl) ? '(invalid)' : ''}`
                : 'Git URL (https://, ssh://) or local directory path (/, ~/, ./)'
            }
            error={!!newPackUrl && !isValidLocation(newPackUrl)}
            sx={{ mb: 2 }}
          />

          {/* Branch/PR Selector for GitHub URLs */}
          {isGitUrl(newPackUrl) && (
            <Autocomplete<RefOption>
              options={
                refs && !refs.error
                  ? [
                      ...refs.branches.map(
                        (b): RefOption => ({
                          type: 'branch',
                          label: b.name,
                          branch: b.name,
                          group: 'Branches',
                          isDefault: b.name === refs.default_branch,
                          protected: b.protected,
                        })
                      ),
                      ...refs.pull_requests.map(
                        (pr): RefOption => ({
                          type: 'pr',
                          label: `#${pr.number}: ${pr.title}`,
                          branch: pr.head_branch,
                          prNumber: pr.number,
                          prTitle: pr.title,
                          prAuthor: pr.author,
                          prHeadRepoUrl: pr.head_repo_url ?? null,
                          group: 'Pull Requests',
                        })
                      ),
                    ]
                  : []
              }
              groupBy={(option) => option.group}
              getOptionLabel={(option) => option.label}
              loading={isLoadingRefs}
              value={
                selectedRef && refs && !refs.error
                  ? selectedRef.type === 'pr'
                    ? ({
                        type: 'pr',
                        label: `#${selectedRef.prNumber}: ${selectedRef.prTitle}`,
                        branch: selectedRef.branch,
                        prNumber: selectedRef.prNumber!,
                        prTitle: selectedRef.prTitle!,
                        prAuthor: selectedRef.prAuthor!,
                        prHeadRepoUrl: selectedRef.prHeadRepoUrl ?? null,
                        group: 'Pull Requests',
                      } satisfies RefOption)
                    : ({
                        type: 'branch',
                        label: selectedRef.branch,
                        branch: selectedRef.branch,
                        group: 'Branches',
                        isDefault: selectedRef.branch === refs.default_branch,
                        protected: false,
                      } satisfies RefOption)
                  : null
              }
              onChange={(_, value) => {
                if (value) {
                  if (value.type === 'pr') {
                    setSelectedRef({
                      type: 'pr',
                      branch: value.branch,
                      prNumber: value.prNumber,
                      prTitle: value.prTitle,
                      prAuthor: value.prAuthor,
                      prHeadRepoUrl: value.prHeadRepoUrl,
                    });
                  } else {
                    setSelectedRef({
                      type: 'branch',
                      branch: value.branch,
                    });
                  }
                } else {
                  setSelectedRef(null);
                }
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Branch or Pull Request"
                  placeholder="Select a branch or PR (optional)"
                  helperText={
                    refs?.error
                      ? refs.error
                      : `Default: ${refs?.default_branch || 'main'}`
                  }
                  error={!!refs?.error}
                />
              )}
              renderOption={(props, option) => {
                const { key, ...otherProps } = props as any;
                return (
                  <li key={key} {...otherProps}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
                      {option.type === 'pr' ? (
                        <CallMerge fontSize="small" color="action" />
                      ) : (
                        <AccountTree fontSize="small" color="action" />
                      )}
                      <Typography variant="body2" sx={{ flexGrow: 1 }}>
                        {option.label}
                      </Typography>
                      {option.type === 'branch' && option.isDefault && (
                        <Chip label="Default" size="small" color="primary" variant="outlined" />
                      )}
                      {option.type === 'branch' && option.protected && (
                        <Chip label="Protected" size="small" color="warning" variant="outlined" />
                      )}
                    </Box>
                  </li>
                );
              }}
              sx={{ mb: 2 }}
            />
          )}

          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error.message}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => {
              const request: AddScenarioPackRequest = {
                name: newPackName,
                git_url: newPackUrl,
              };
              if (selectedRef) {
                request.branch = selectedRef.branch;
                if (selectedRef.type === 'pr') {
                  request.pr_number = selectedRef.prNumber;
                  request.pr_title = selectedRef.prTitle;
                  request.pr_author = selectedRef.prAuthor;
                  request.pr_head_repo_url = selectedRef.prHeadRepoUrl;
                }
              }
              addMutation.mutate(request);
            }}
            disabled={
              !newPackName ||
              !newPackUrl ||
              !isValidLocation(newPackUrl) ||
              addMutation.isPending
            }
          >
            {addMutation.isPending ? <CircularProgress size={24} /> : 'Add Pack'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Remove Pack Dialog */}
      <Dialog open={removeDialogOpen} onClose={() => setRemoveDialogOpen(false)}>
        <DialogTitle>Remove Scenario Pack</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to remove the scenario pack <strong>{selectedPack}</strong>?
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            This will remove the pack from your local machine. Scenarios from this pack will no
            longer be available.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRemoveDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleConfirmRemove}
            disabled={removeMutation.isPending}
          >
            {removeMutation.isPending ? <CircularProgress size={24} /> : 'Remove'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Switch Branch Dialog */}
      <Dialog
        open={switchDialogOpen}
        onClose={() => setSwitchDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Switch Branch or Pull Request</DialogTitle>
        <DialogContent>
          {selectedPackForSwitch && (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Current: <strong>{selectedPackForSwitch.current_ref?.type === 'pr'
                  ? `PR #${selectedPackForSwitch.current_ref.pr_number}: ${selectedPackForSwitch.current_ref.pr_title}`
                  : selectedPackForSwitch.current_ref?.branch || 'Unknown'}</strong>
              </Typography>
              <BranchPRSelector
                gitUrl={selectedPackForSwitch.git_url}
                onSelect={handleConfirmSwitch}
                defaultBranch={selectedPackForSwitch.current_ref?.branch}
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSwitchDialogOpen(false)}>Cancel</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
