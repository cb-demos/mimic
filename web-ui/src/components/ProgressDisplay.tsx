/**
 * Progress display component for real-time scenario execution
 */

import {
  Box,
  Card,
  CardContent,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Typography,
  Alert,
  Chip,
} from '@mui/material';
import {
  CheckCircle,
  Error,
  HourglassEmpty,
  PlayArrow,
} from '@mui/icons-material';
import { useProgress, type TaskProgress } from '../hooks/useProgress';

interface ProgressDisplayProps {
  sessionId: string | null;
  onComplete?: () => void;
}

export function ProgressDisplay({ sessionId, onComplete }: ProgressDisplayProps) {
  const { tasks, isComplete, error } = useProgress(sessionId);

  // Call onComplete callback when scenario finishes
  if (isComplete && onComplete) {
    onComplete();
  }

  // Show loading state when no session
  if (!sessionId) {
    return (
      <Card>
        <CardContent>
          <Typography variant="body2" color="text.secondary">
            No scenario running
          </Typography>
        </CardContent>
      </Card>
    );
  }

  // Show error state
  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="error">
            <Typography variant="body2">{error.message}</Typography>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  // Convert tasks Map to array for rendering
  const taskList = Array.from(tasks.values());

  return (
    <Card>
      <CardContent>
        <Box sx={{ mb: 2 }}>
          <Typography variant="h6" gutterBottom>
            Scenario Progress
          </Typography>
          {isComplete && (
            <Alert severity="success" sx={{ mb: 2 }}>
              Scenario completed successfully!
            </Alert>
          )}
        </Box>

        <List>
          {taskList.map((task) => (
            <TaskItem key={task.id} task={task} />
          ))}
        </List>

        {taskList.length === 0 && (
          <Typography variant="body2" color="text.secondary">
            Waiting for scenario to start...
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

function TaskItem({ task }: { task: TaskProgress }) {
  const progress = task.total > 0 ? (task.current / task.total) * 100 : 0;

  const getIcon = () => {
    switch (task.status) {
      case 'complete':
        return <CheckCircle color="success" />;
      case 'error':
        return <Error color="error" />;
      case 'running':
        return <PlayArrow color="primary" />;
      default:
        return <HourglassEmpty color="disabled" />;
    }
  };

  const getStatusChip = () => {
    switch (task.status) {
      case 'complete':
        return <Chip label="Complete" color="success" size="small" />;
      case 'error':
        return <Chip label="Error" color="error" size="small" />;
      case 'running':
        return <Chip label="Running" color="primary" size="small" />;
      default:
        return null;
    }
  };

  return (
    <ListItem>
      <ListItemIcon>{getIcon()}</ListItemIcon>
      <ListItemText
        primary={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body1">{task.description}</Typography>
            {getStatusChip()}
          </Box>
        }
        secondary={
          <Box sx={{ mt: 1 }}>
            {task.message && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                {task.message}
              </Typography>
            )}
            {task.error && (
              <Typography variant="body2" color="error" sx={{ mb: 0.5 }}>
                {task.error}
              </Typography>
            )}
            {task.status === 'running' && task.total > 0 && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <LinearProgress
                  variant="determinate"
                  value={progress}
                  sx={{ flexGrow: 1 }}
                />
                <Typography variant="body2" color="text.secondary">
                  {task.current}/{task.total}
                </Typography>
              </Box>
            )}
          </Box>
        }
      />
    </ListItem>
  );
}
