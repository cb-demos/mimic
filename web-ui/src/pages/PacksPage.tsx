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
} from '@mui/material';
import { Add, Delete, Refresh, Link as LinkIcon } from '@mui/icons-material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { packsApi } from '../api/endpoints';
import type { ScenarioPack } from '../types/api';

export function PacksPage() {
  const queryClient = useQueryClient();
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [selectedPack, setSelectedPack] = useState<string | null>(null);
  const [newPackName, setNewPackName] = useState('');
  const [newPackUrl, setNewPackUrl] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Fetch packs
  const { data: packs, isLoading } = useQuery({
    queryKey: ['scenario-packs'],
    queryFn: packsApi.list,
  });

  // Add pack mutation
  const addMutation = useMutation({
    mutationFn: (data: { name: string; git_url: string }) => packsApi.add(data.name, data.git_url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scenario-packs'] });
      queryClient.invalidateQueries({ queryKey: ['scenarios'] });
      setSuccess('Scenario pack added successfully');
      setAddDialogOpen(false);
      setNewPackName('');
      setNewPackUrl('');
      setError(null);
    },
    onError: (err: any) => {
      setError(err.message || 'Failed to add scenario pack');
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
      setError(err.message || 'Failed to remove scenario pack');
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
      setError(err.message || 'Failed to update pack status');
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
      setError(err.message || 'Failed to update pack(s)');
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

  const isGitUrl = (url: string) => {
    return (
      url.startsWith('https://') ||
      url.startsWith('http://') ||
      url.startsWith('git@') ||
      url.startsWith('ssh://') ||
      url.startsWith('git://')
    );
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

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

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
                      <Chip label={pack.scenario_count} size="small" color="primary" />
                    </TableCell>
                    <TableCell align="right">
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
            onChange={(e) => setNewPackUrl(e.target.value)}
            placeholder="e.g., https://github.com/user/repo.git or /Users/me/scenarios"
            helperText={
              newPackUrl
                ? `Type: ${getLocationType(newPackUrl)} ${!isValidLocation(newPackUrl) ? '(invalid)' : ''}`
                : 'Git URL (https://, ssh://) or local directory path (/, ~/, ./)'
            }
            error={!!newPackUrl && !isValidLocation(newPackUrl)}
          />

          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => addMutation.mutate({ name: newPackName, git_url: newPackUrl })}
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
    </Container>
  );
}
