/**
 * ResourceList component - displays created resources grouped by type
 * with clickable links to view them in their respective platforms
 */

import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemText,
  Link,
  Paper,
  Divider,
} from '@mui/material';
import { OpenInNew } from '@mui/icons-material';
import type { Resource } from '../types/api';

interface ResourceListProps {
  resources: Resource[];
  showHeader?: boolean;
}

/**
 * Groups resources by their type for organized display
 */
function groupResourcesByType(resources: Resource[]): Map<string, Resource[]> {
  const grouped = new Map<string, Resource[]>();

  for (const resource of resources) {
    if (!grouped.has(resource.type)) {
      grouped.set(resource.type, []);
    }
    grouped.get(resource.type)!.push(resource);
  }

  return grouped;
}

/**
 * Formats resource type for display (e.g., "repository" -> "Repositories")
 */
function formatResourceType(type: string): string {
  const formatted = type.charAt(0).toUpperCase() + type.slice(1);
  // Add 's' for pluralization if not already plural
  return formatted.endsWith('s') ? formatted : `${formatted}s`;
}

/**
 * Displays a list of created resources grouped by type
 */
export function ResourceList({ resources, showHeader = true }: ResourceListProps) {
  if (!resources || resources.length === 0) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          No resources created
        </Typography>
      </Box>
    );
  }

  const groupedResources = groupResourcesByType(resources);
  const resourceTypes = Array.from(groupedResources.keys()).sort();

  return (
    <Box>
      {showHeader && (
        <Typography variant="subtitle2" gutterBottom sx={{ mb: 2 }}>
          Resources Created ({resources.length})
        </Typography>
      )}

      {resourceTypes.map((type, typeIndex) => {
        const typeResources = groupedResources.get(type)!;

        return (
          <Box key={type} sx={{ mb: typeIndex < resourceTypes.length - 1 ? 3 : 0 }}>
            <Typography
              variant="subtitle2"
              color="text.secondary"
              sx={{ mb: 1, fontWeight: 600 }}
            >
              {formatResourceType(type)} ({typeResources.length})
            </Typography>

            <Paper variant="outlined" sx={{ overflow: 'hidden' }}>
              <List dense disablePadding>
                {typeResources.map((resource, idx) => (
                  <Box key={`${resource.type}-${resource.id}`}>
                    <ListItem sx={{ py: 1.5 }}>
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
                                fontWeight: 500,
                              }}
                            >
                              {resource.name}
                              <OpenInNew sx={{ fontSize: '0.875rem' }} />
                            </Link>
                          ) : (
                            <Typography
                              component="span"
                              sx={{
                                fontFamily: 'monospace',
                                fontSize: '0.875rem',
                                fontWeight: 500,
                              }}
                            >
                              {resource.name}
                            </Typography>
                          )
                        }
                        secondary={
                          <Typography
                            component="span"
                            variant="caption"
                            color="text.secondary"
                          >
                            ID: {resource.id}
                            {resource.org_id && ` • Org: ${resource.org_id}`}
                          </Typography>
                        }
                      />
                    </ListItem>
                    {idx < typeResources.length - 1 && <Divider />}
                  </Box>
                ))}
              </List>
            </Paper>
          </Box>
        );
      })}
    </Box>
  );
}
