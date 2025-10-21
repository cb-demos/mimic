/**
 * Environments page - manage CloudBees environments
 */

import { useState, useRef } from 'react';
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
  Chip,
  Alert,
  CircularProgress,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  ButtonGroup,
  ClickAwayListener,
  Grow,
  MenuItem,
  MenuList,
  Popper,
} from '@mui/material';
import { Add, Delete, Settings, CheckCircle, ArrowDropDown, DeleteOutline } from '@mui/icons-material';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { environmentsApi } from '../api/endpoints';
import type { Environment } from '../types/api';
import { AddPresetEnvironmentDialog } from '../components/AddPresetEnvironmentDialog';

export function EnvironmentsPage() {
  const queryClient = useQueryClient();
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [addPresetDialogOpen, setAddPresetDialogOpen] = useState(false);
  const [propsDialogOpen, setPropsDialogOpen] = useState(false);
  const [selectedEnv, setSelectedEnv] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [propertyToDelete, setPropertyToDelete] = useState<string | null>(null);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const addButtonRef = useRef<HTMLDivElement | null>(null);

  // Add environment form
  const [newEnv, setNewEnv] = useState({
    name: '',
    url: '',
    endpoint_id: '',
  });

  // Add property form
  const [newProp, setNewProp] = useState({
    key: '',
    value: '',
  });

  // Fetch environments
  const { data, isLoading } = useQuery({
    queryKey: ['environments'],
    queryFn: environmentsApi.list,
  });

  // Fetch properties for selected environment
  const { data: propertiesData, isLoading: loadingProps } = useQuery({
    queryKey: ['environment-properties', selectedEnv],
    queryFn: () => environmentsApi.getProperties(selectedEnv!),
    enabled: !!selectedEnv,
  });

  // Select environment mutation
  const selectMutation = useMutation({
    mutationFn: (envName: string) => environmentsApi.select(envName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environments'] });
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to select environment');
    },
  });

  // Add environment mutation
  const addMutation = useMutation({
    mutationFn: (env: { name: string; url: string; endpoint_id: string }) =>
      environmentsApi.add(env.name, env.url, env.endpoint_id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environments'] });
      queryClient.invalidateQueries({ queryKey: ['preset-environments'] });
      setAddDialogOpen(false);
      setNewEnv({ name: '', url: '', endpoint_id: '' });
      setError(null);
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to add environment');
    },
  });

  // Remove environment mutation
  const removeMutation = useMutation({
    mutationFn: (envName: string) => environmentsApi.remove(envName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environments'] });
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to remove environment');
    },
  });

  // Add property mutation
  const addPropMutation = useMutation({
    mutationFn: (data: { envName: string; key: string; value: string }) =>
      environmentsApi.addProperty(data.envName, data.key, data.value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environment-properties', selectedEnv] });
      setNewProp({ key: '', value: '' });
      setError(null);
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to add property');
    },
  });

  // Delete property mutation
  const deletePropMutation = useMutation({
    mutationFn: (data: { envName: string; propertyKey: string }) =>
      environmentsApi.deleteEnvironmentProperty(data.envName, data.propertyKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['environment-properties', selectedEnv] });
      setDeleteConfirmOpen(false);
      setPropertyToDelete(null);
      setError(null);
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to delete property');
    },
  });

  const handleManageProps = (envName: string) => {
    setSelectedEnv(envName);
    setPropsDialogOpen(true);
  };

  const handleClosePropsDialog = () => {
    setPropsDialogOpen(false);
    setSelectedEnv(null);
    setNewProp({ key: '', value: '' });
    setError(null);
  };

  const handleAddProperty = () => {
    if (selectedEnv && newProp.key && newProp.value) {
      addPropMutation.mutate({
        envName: selectedEnv,
        key: newProp.key,
        value: newProp.value,
      });
    }
  };

  const handleDeleteProperty = (propertyKey: string) => {
    setPropertyToDelete(propertyKey);
    setDeleteConfirmOpen(true);
  };

  const confirmDeleteProperty = () => {
    if (selectedEnv && propertyToDelete) {
      deletePropMutation.mutate({
        envName: selectedEnv,
        propertyKey: propertyToDelete,
      });
    }
  };

  const handlePresetSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ['environments'] });
    queryClient.invalidateQueries({ queryKey: ['preset-environments'] });
  };

  const isBuiltInProperty = (key: string) => {
    return key === 'UNIFY_API' || key === 'ENDPOINT_ID';
  };

  if (isLoading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Environments
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Manage CloudBees environments and properties
          </Typography>
        </Box>
        <ButtonGroup variant="contained" ref={addButtonRef}>
          <Button startIcon={<Add />} onClick={() => setAddPresetDialogOpen(true)}>
            Add Preset
          </Button>
          <Button
            size="small"
            onClick={() => setAddMenuOpen((prev) => !prev)}
          >
            <ArrowDropDown />
          </Button>
        </ButtonGroup>
        <Popper
          open={addMenuOpen}
          anchorEl={addButtonRef.current}
          role={undefined}
          placement="bottom-end"
          transition
          disablePortal
        >
          {({ TransitionProps }) => (
            <Grow {...TransitionProps}>
              <Paper>
                <ClickAwayListener onClickAway={() => setAddMenuOpen(false)}>
                  <MenuList>
                    <MenuItem
                      onClick={() => {
                        setAddMenuOpen(false);
                        setAddPresetDialogOpen(true);
                      }}
                    >
                      Add Preset Environment
                    </MenuItem>
                    <MenuItem
                      onClick={() => {
                        setAddMenuOpen(false);
                        setAddDialogOpen(true);
                      }}
                    >
                      Add Custom Environment
                    </MenuItem>
                  </MenuList>
                </ClickAwayListener>
              </Paper>
            </Grow>
          )}
        </Popper>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {data && (
        <Paper>
          <Box sx={{ p: 2, bgcolor: 'primary.main', color: 'primary.contrastText' }}>
            <Typography variant="body2">
              Current Environment: <strong>{data.current}</strong>
            </Typography>
          </Box>

          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell width="40">Current</TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell>URL</TableCell>
                  <TableCell>Endpoint ID</TableCell>
                  <TableCell>Flag API</TableCell>
                  <TableCell>Properties</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.environments.map((env: Environment) => (
                  <TableRow key={env.name} hover>
                    <TableCell>
                      {env.name === data.current && (
                        <CheckCircle color="success" fontSize="small" />
                      )}
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {env.name}
                        {env.is_preset ? (
                          <Chip label="Preset" size="small" color="primary" />
                        ) : (
                          <Chip label="Custom" size="small" color="default" />
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" fontFamily="monospace" fontSize="0.875rem">
                        {env.url}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" fontFamily="monospace" fontSize="0.875rem">
                        {env.endpoint_id}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={env.flag_api_type === 'org' ? 'Org Flags' : 'App Flags'}
                        size="small"
                        color={env.flag_api_type === 'org' ? 'warning' : 'info'}
                      />
                    </TableCell>
                    <TableCell>
                      <Button
                        size="small"
                        startIcon={<Settings />}
                        onClick={() => handleManageProps(env.name)}
                      >
                        Manage
                      </Button>
                    </TableCell>
                    <TableCell align="right">
                      <Button
                        size="small"
                        variant={env.name === data.current ? 'outlined' : 'contained'}
                        onClick={() => selectMutation.mutate(env.name)}
                        disabled={env.name === data.current || selectMutation.isPending}
                      >
                        {env.name === data.current ? 'Selected' : 'Select'}
                      </Button>
                      {!env.is_preset && (
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => removeMutation.mutate(env.name)}
                          disabled={removeMutation.isPending}
                          sx={{ ml: 1 }}
                        >
                          <Delete />
                        </IconButton>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {/* Add Environment Dialog */}
      <Dialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add Custom Environment</DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Environment Name"
            value={newEnv.name}
            onChange={(e) => setNewEnv({ ...newEnv, name: e.target.value })}
            sx={{ mt: 2, mb: 2 }}
            placeholder="e.g., staging"
          />
          <TextField
            fullWidth
            label="URL"
            value={newEnv.url}
            onChange={(e) => setNewEnv({ ...newEnv, url: e.target.value })}
            sx={{ mb: 2 }}
            placeholder="e.g., https://staging.cloudbees.io"
          />
          <TextField
            fullWidth
            label="Endpoint ID"
            value={newEnv.endpoint_id}
            onChange={(e) => setNewEnv({ ...newEnv, endpoint_id: e.target.value })}
            placeholder="e.g., cb-staging"
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
            onClick={() => addMutation.mutate(newEnv)}
            disabled={!newEnv.name || !newEnv.url || !newEnv.endpoint_id || addMutation.isPending}
          >
            {addMutation.isPending ? <CircularProgress size={24} /> : 'Add'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add Preset Environment Dialog */}
      <AddPresetEnvironmentDialog
        open={addPresetDialogOpen}
        onClose={() => setAddPresetDialogOpen(false)}
        onSuccess={handlePresetSuccess}
      />

      {/* Delete Property Confirmation Dialog */}
      <Dialog open={deleteConfirmOpen} onClose={() => setDeleteConfirmOpen(false)}>
        <DialogTitle>Delete Property</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete the property <strong>{propertyToDelete}</strong>?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirmOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="error"
            onClick={confirmDeleteProperty}
            disabled={deletePropMutation.isPending}
          >
            {deletePropMutation.isPending ? <CircularProgress size={24} /> : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Properties Dialog */}
      <Dialog
        open={propsDialogOpen}
        onClose={handleClosePropsDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          Environment Properties: {selectedEnv}
        </DialogTitle>
        <DialogContent>
          {loadingProps ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Properties are available as template variables in scenarios (e.g., $&#123;env.PROPERTY_NAME&#125;)
              </Typography>

              {propertiesData?.properties && Object.keys(propertiesData.properties).length > 0 ? (
                <Paper variant="outlined" sx={{ mb: 3 }}>
                  <List>
                    {Object.entries(propertiesData.properties).map(([key, value]) => (
                      <ListItem key={key} divider>
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography variant="body2" fontWeight="medium">
                                {key}
                              </Typography>
                              {isBuiltInProperty(key) && (
                                <Chip label="Built-in" size="small" color="default" />
                              )}
                            </Box>
                          }
                          secondary={
                            <Typography
                              variant="body2"
                              component="span"
                              fontFamily="monospace"
                              sx={{ wordBreak: 'break-all' }}
                            >
                              {value as string}
                            </Typography>
                          }
                        />
                        <ListItemSecondaryAction>
                          {!isBuiltInProperty(key) && (
                            <IconButton
                              edge="end"
                              aria-label="delete"
                              onClick={() => handleDeleteProperty(key)}
                              size="small"
                              color="error"
                            >
                              <DeleteOutline />
                            </IconButton>
                          )}
                        </ListItemSecondaryAction>
                      </ListItem>
                    ))}
                  </List>
                </Paper>
              ) : (
                <Alert severity="info" sx={{ mb: 3 }}>
                  No properties set for this environment
                </Alert>
              )}

              <Typography variant="h6" gutterBottom>
                Add Property
              </Typography>
              <TextField
                fullWidth
                label="Property Key"
                value={newProp.key}
                onChange={(e) => setNewProp({ ...newProp, key: e.target.value })}
                sx={{ mb: 2 }}
                placeholder="e.g., UNIFY_API"
              />
              <TextField
                fullWidth
                label="Property Value"
                value={newProp.value}
                onChange={(e) => setNewProp({ ...newProp, value: e.target.value })}
                placeholder="e.g., https://api.cloudbees.io"
              />

              {error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {error}
                </Alert>
              )}

              <Button
                variant="contained"
                fullWidth
                sx={{ mt: 2 }}
                onClick={handleAddProperty}
                disabled={!newProp.key || !newProp.value || addPropMutation.isPending}
              >
                {addPropMutation.isPending ? <CircularProgress size={24} /> : 'Add Property'}
              </Button>
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClosePropsDialog}>Close</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
