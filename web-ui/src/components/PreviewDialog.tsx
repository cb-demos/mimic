/**
 * Preview Dialog - Shows what resources will be created before execution
 */

import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  Chip,
  Divider,
  Alert,
} from '@mui/material';
import type { ScenarioPreviewResponse } from '../types/api';

interface PreviewDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  preview: ScenarioPreviewResponse | null;
  scenarioName: string;
  environment: string;
  expirationLabel: string;
  isSubmitting?: boolean;
}

export function PreviewDialog({
  open,
  onClose,
  onConfirm,
  preview,
  scenarioName,
  environment,
  expirationLabel,
  isSubmitting = false,
}: PreviewDialogProps) {
  if (!preview) {
    return null;
  }

  const { repositories, components, environments, applications, flags } = preview.preview;

  const totalResources =
    repositories.length +
    components.length +
    environments.length +
    applications.length +
    flags.length;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="h6">Preview Resources</Typography>
          <Chip label={`${totalResources} total`} color="primary" size="small" />
        </Box>
      </DialogTitle>

      <DialogContent>
        {/* Scenario info */}
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2">
            <strong>Scenario:</strong> {scenarioName}
          </Typography>
          <Typography variant="body2">
            <strong>Environment:</strong> {environment}
          </Typography>
          <Typography variant="body2">
            <strong>Expiration:</strong> {expirationLabel}
          </Typography>
        </Alert>

        {/* Resources preview */}
        <Typography variant="subtitle2" gutterBottom>
          The following resources will be created:
        </Typography>

        {/* Repositories */}
        {repositories.length > 0 && (
          <>
            <Box sx={{ mt: 2 }}>
              <Typography variant="body1" fontWeight="medium" gutterBottom>
                GitHub Repositories ({repositories.length})
              </Typography>
              <List dense>
                {repositories.slice(0, 5).map((repo, index) => (
                  <ListItem key={index} sx={{ pl: 2 }}>
                    <ListItemText
                      primary={repo.name}
                      secondary={`from ${repo.source}`}
                      primaryTypographyProps={{ fontFamily: 'monospace', fontSize: '0.9rem' }}
                      secondaryTypographyProps={{ fontSize: '0.8rem' }}
                    />
                  </ListItem>
                ))}
                {repositories.length > 5 && (
                  <ListItem sx={{ pl: 2 }}>
                    <ListItemText
                      secondary={`... and ${repositories.length - 5} more`}
                      secondaryTypographyProps={{ fontSize: '0.8rem', fontStyle: 'italic' }}
                    />
                  </ListItem>
                )}
              </List>
            </Box>
            <Divider sx={{ my: 2 }} />
          </>
        )}

        {/* Components */}
        {components.length > 0 && (
          <>
            <Box sx={{ mt: 2 }}>
              <Typography variant="body1" fontWeight="medium" gutterBottom>
                CloudBees Components ({components.length})
              </Typography>
              <List dense>
                {components.slice(0, 5).map((component, index) => (
                  <ListItem key={index} sx={{ pl: 2 }}>
                    <ListItemText
                      primary={component}
                      primaryTypographyProps={{ fontFamily: 'monospace', fontSize: '0.9rem' }}
                    />
                  </ListItem>
                ))}
                {components.length > 5 && (
                  <ListItem sx={{ pl: 2 }}>
                    <ListItemText
                      secondary={`... and ${components.length - 5} more`}
                      secondaryTypographyProps={{ fontSize: '0.8rem', fontStyle: 'italic' }}
                    />
                  </ListItem>
                )}
              </List>
            </Box>
            <Divider sx={{ my: 2 }} />
          </>
        )}

        {/* Environments */}
        {environments.length > 0 && (
          <>
            <Box sx={{ mt: 2 }}>
              <Typography variant="body1" fontWeight="medium" gutterBottom>
                CloudBees Environments ({environments.length})
              </Typography>
              <List dense>
                {environments.map((env, index) => (
                  <ListItem key={index} sx={{ pl: 2 }}>
                    <ListItemText
                      primary={env.name}
                      primaryTypographyProps={{ fontFamily: 'monospace', fontSize: '0.9rem' }}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
            <Divider sx={{ my: 2 }} />
          </>
        )}

        {/* Applications */}
        {applications.length > 0 && (
          <>
            <Box sx={{ mt: 2 }}>
              <Typography variant="body1" fontWeight="medium" gutterBottom>
                CloudBees Applications ({applications.length})
              </Typography>
              <List dense>
                {applications.map((app, index) => (
                  <ListItem key={index} sx={{ pl: 2 }}>
                    <ListItemText
                      primary={app.name}
                      secondary={`${app.components.length} components, ${app.environments.length} environments`}
                      primaryTypographyProps={{ fontFamily: 'monospace', fontSize: '0.9rem' }}
                      secondaryTypographyProps={{ fontSize: '0.8rem' }}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
            <Divider sx={{ my: 2 }} />
          </>
        )}

        {/* Feature Flags */}
        {flags.length > 0 && (
          <>
            <Box sx={{ mt: 2 }}>
              <Typography variant="body1" fontWeight="medium" gutterBottom>
                Feature Flags ({flags.length})
              </Typography>
              <List dense>
                {flags.map((flag, index) => (
                  <ListItem key={index} sx={{ pl: 2 }}>
                    <ListItemText
                      primary={flag.name}
                      secondary={`${flag.type}, in: ${flag.environments.join(', ')}`}
                      primaryTypographyProps={{ fontFamily: 'monospace', fontSize: '0.9rem' }}
                      secondaryTypographyProps={{ fontSize: '0.8rem' }}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          </>
        )}

        {totalResources === 0 && (
          <Alert severity="warning">
            No resources will be created. This scenario might be empty or have conditional
            resources based on parameters.
          </Alert>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button onClick={onConfirm} variant="contained" color="primary" disabled={isSubmitting}>
          {isSubmitting ? 'Creating...' : 'Create Resources'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
