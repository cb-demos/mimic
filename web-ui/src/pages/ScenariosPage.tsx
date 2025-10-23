/**
 * Scenarios page - browse and select scenarios
 */

import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Paper,
  TextField,
  InputAdornment,
  ToggleButtonGroup,
  ToggleButton,
  FormControlLabel,
  Switch,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
} from '@mui/material';
import { Search, ViewList, ViewModule } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { scenariosApi } from '../api/endpoints';
import type { Scenario } from '../types/api';

type ViewMode = 'table' | 'card';

export function ScenariosPage() {
  const navigate = useNavigate();
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    const saved = localStorage.getItem('scenarios-view-mode');
    return (saved as ViewMode) || 'card';
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedPack, setSelectedPack] = useState<string>('all');
  const [showWip, setShowWip] = useState(false);
  const [detailsDialogOpen, setDetailsDialogOpen] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null);

  // Fetch scenarios
  const { data, isLoading, error } = useQuery({
    queryKey: ['scenarios'],
    queryFn: scenariosApi.list,
  });

  // Get unique packs
  const packs = useMemo(() => {
    if (!data?.scenarios) return [];
    const packSet = new Set(data.scenarios.map((s: Scenario) => s.scenario_pack || 'local'));
    return Array.from(packSet).sort();
  }, [data?.scenarios]);

  // Filter scenarios
  const filteredScenarios = useMemo(() => {
    if (!data?.scenarios) return [];

    return data.scenarios.filter((scenario: Scenario) => {
      // Search filter
      const matchesSearch =
        !searchQuery ||
        scenario.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        scenario.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        scenario.summary.toLowerCase().includes(searchQuery.toLowerCase());

      // Pack filter
      const scenarioPack = scenario.scenario_pack || 'local';
      const matchesPack = selectedPack === 'all' || scenarioPack === selectedPack;

      return matchesSearch && matchesPack;
    });
  }, [data?.scenarios, searchQuery, selectedPack]);

  const handleViewModeChange = (
    _event: React.MouseEvent<HTMLElement>,
    newMode: ViewMode | null,
  ) => {
    if (newMode) {
      setViewMode(newMode);
      localStorage.setItem('scenarios-view-mode', newMode);
    }
  };

  const handleShowDetails = (scenario: Scenario) => {
    setSelectedScenario(scenario);
    setDetailsDialogOpen(true);
  };

  const handleRun = (scenarioId: string) => {
    navigate(`/scenarios/${scenarioId}/run`);
  };

  const renderCardView = () => (
    <Grid container spacing={3}>
      {filteredScenarios.map((scenario: Scenario) => (
        <Grid size={{ xs: 12, sm: 6, md: 4 }} key={scenario.id}>
          <Card elevation={2} sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flexGrow: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
                  {scenario.name}
                </Typography>
                {scenario.wip && (
                  <Chip label="WIP" size="small" color="warning" sx={{ ml: 1 }} />
                )}
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                {scenario.id}
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                {scenario.summary}
              </Typography>
              <Chip
                label={scenario.scenario_pack || 'local'}
                size="small"
                variant="outlined"
              />
            </CardContent>
            <CardActions>
              <Button size="small" onClick={() => handleShowDetails(scenario)}>
                Details
              </Button>
              <Button
                size="small"
                variant="contained"
                onClick={() => handleRun(scenario.id)}
              >
                Run
              </Button>
            </CardActions>
          </Card>
        </Grid>
      ))}
    </Grid>
  );

  const renderTableView = () => (
    <TableContainer>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>ID</TableCell>
            <TableCell>Summary</TableCell>
            <TableCell>Pack</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {filteredScenarios.map((scenario: Scenario) => (
            <TableRow key={scenario.id} hover>
              <TableCell>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {scenario.name}
                  {scenario.wip && <Chip label="WIP" size="small" color="warning" />}
                </Box>
              </TableCell>
              <TableCell>
                <Typography variant="body2" fontFamily="monospace">
                  {scenario.id}
                </Typography>
              </TableCell>
              <TableCell>{scenario.summary}</TableCell>
              <TableCell>
                <Chip
                  label={scenario.scenario_pack || 'local'}
                  size="small"
                  variant="outlined"
                />
              </TableCell>
              <TableCell align="right">
                <Button size="small" onClick={() => handleShowDetails(scenario)}>
                  Details
                </Button>
                <Button
                  size="small"
                  variant="contained"
                  onClick={() => handleRun(scenario.id)}
                  sx={{ ml: 1 }}
                >
                  Run
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );

  return (
    <Container maxWidth="lg">
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Scenarios
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Browse and execute available scenarios
        </Typography>
      </Box>

      {/* Controls */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid size={{ xs: 12, sm: 6, md: 4 }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search scenarios..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <TextField
              fullWidth
              select
              size="small"
              label="Scenario Pack"
              value={selectedPack}
              onChange={(e) => setSelectedPack(e.target.value)}
              SelectProps={{ native: true }}
            >
              <option value="all">All Packs</option>
              {packs.map((pack: string) => (
                <option key={pack} value={pack}>
                  {pack}
                </option>
              ))}
            </TextField>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <FormControlLabel
              control={
                <Switch checked={showWip} onChange={(e) => setShowWip(e.target.checked)} />
              }
              label="Show WIP"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 2 }} sx={{ textAlign: 'right' }}>
            <ToggleButtonGroup
              value={viewMode}
              exclusive
              onChange={handleViewModeChange}
              size="small"
            >
              <ToggleButton value="card">
                <ViewModule />
              </ToggleButton>
              <ToggleButton value="table">
                <ViewList />
              </ToggleButton>
            </ToggleButtonGroup>
          </Grid>
        </Grid>

        {/* Stats */}
        <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
          <Chip
            label={`${filteredScenarios.length} ${filteredScenarios.length === 1 ? 'scenario' : 'scenarios'}`}
            color="primary"
            variant="outlined"
          />
          {data?.wip_enabled && (
            <Chip
              label={`${data.scenarios.filter((s: Scenario) => s.wip).length} WIP`}
              color="warning"
              variant="outlined"
            />
          )}
        </Box>
      </Paper>

      {/* Content */}
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {error && (
        <Alert severity="error">
          Failed to load scenarios: {(error as any).message}
        </Alert>
      )}

      {!isLoading && !error && filteredScenarios.length === 0 && (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">
            {searchQuery || selectedPack !== 'all'
              ? 'No scenarios match your filters'
              : 'No scenarios available'}
          </Typography>
        </Paper>
      )}

      {!isLoading && !error && filteredScenarios.length > 0 && (
        <Paper sx={{ p: viewMode === 'card' ? 3 : 0 }}>
          {viewMode === 'card' ? renderCardView() : renderTableView()}
        </Paper>
      )}

      {/* Details Dialog */}
      <Dialog
        open={detailsDialogOpen}
        onClose={() => setDetailsDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        {selectedScenario && (
          <>
            <DialogTitle>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {selectedScenario.name}
                {selectedScenario.wip && <Chip label="WIP" size="small" color="warning" />}
              </Box>
            </DialogTitle>
            <DialogContent>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Scenario ID
                </Typography>
                <Typography variant="body1" fontFamily="monospace">
                  {selectedScenario.id}
                </Typography>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Summary
                </Typography>
                <Typography variant="body1">{selectedScenario.summary}</Typography>
              </Box>

              {selectedScenario.details && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Description
                  </Typography>
                  <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                    {selectedScenario.details}
                  </Typography>
                </Box>
              )}

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Scenario Pack
                </Typography>
                <Chip
                  label={selectedScenario.scenario_pack || 'local'}
                  size="small"
                  variant="outlined"
                />
              </Box>

              {selectedScenario.parameter_schema &&
                Object.keys(selectedScenario.parameter_schema).length > 0 && (
                  <Box>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Parameters
                    </Typography>
                    <Paper variant="outlined" sx={{ p: 2 }}>
                      {Object.entries(selectedScenario.parameter_schema).map(
                        ([key, param]: [string, any]) => (
                          <Box key={key} sx={{ mb: 1 }}>
                            <Typography variant="body2" fontWeight="bold">
                              {key}
                              {param.required && (
                                <Chip label="required" size="small" sx={{ ml: 1 }} />
                              )}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Type: {param.type}
                              {param.default !== undefined && ` • Default: ${param.default}`}
                            </Typography>
                            {param.description && (
                              <Typography variant="body2">{param.description}</Typography>
                            )}
                          </Box>
                        ),
                      )}
                    </Paper>
                  </Box>
                )}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setDetailsDialogOpen(false)}>Close</Button>
              <Button
                variant="contained"
                onClick={() => {
                  setDetailsDialogOpen(false);
                  handleRun(selectedScenario.id);
                }}
              >
                Run Scenario
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </Container>
  );
}
