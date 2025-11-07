/**
 * Enhanced error alert with details expansion and recovery actions
 */

import { useState } from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  Button,
  Collapse,
  Typography,
  IconButton,
  Stack,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  ContentCopy as CopyIcon,
  Refresh as RetryIcon,
} from '@mui/icons-material';

export interface ErrorDetail {
  message: string;
  field?: string;
  code?: string;
}

export interface ErrorInfo {
  message: string;
  code?: string;
  suggestion?: string;
  details?: ErrorDetail[];
  requestId?: string;
  technical_details?: string;
}

interface ErrorAlertProps {
  error: ErrorInfo;
  onRetry?: () => void;
  severity?: 'error' | 'warning';
  onClose?: () => void;
}

export function ErrorAlert({ error, onRetry, severity = 'error', onClose }: ErrorAlertProps) {
  const [expanded, setExpanded] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  const hasDetails =
    error.details && error.details.length > 0 || error.technical_details || error.requestId;

  const handleCopyError = async () => {
    const errorText = JSON.stringify(
      {
        message: error.message,
        code: error.code,
        suggestion: error.suggestion,
        details: error.details,
        technical_details: error.technical_details,
        requestId: error.requestId,
      },
      null,
      2
    );

    try {
      await navigator.clipboard.writeText(errorText);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (err) {
      console.error('Failed to copy error:', err);
    }
  };

  return (
    <Alert
      severity={severity}
      onClose={onClose}
      action={
        <Stack direction="row" spacing={1} alignItems="center">
          {onRetry && (
            <Button size="small" onClick={onRetry} startIcon={<RetryIcon />}>
              Retry
            </Button>
          )}
          {hasDetails && (
            <IconButton
              size="small"
              onClick={() => setExpanded(!expanded)}
              sx={{
                transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 0.3s',
              }}
            >
              <ExpandMoreIcon />
            </IconButton>
          )}
        </Stack>
      }
    >
      <AlertTitle>{error.message}</AlertTitle>

      {error.suggestion && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          <strong>Suggestion:</strong> {error.suggestion}
        </Typography>
      )}

      {error.code && (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          Error Code: {error.code}
        </Typography>
      )}

      {hasDetails && (
        <Collapse in={expanded}>
          <Box
            sx={{
              mt: 2,
              p: 2,
              bgcolor: 'background.paper',
              borderRadius: 1,
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="subtitle2">Technical Details</Typography>
              <Button
                size="small"
                startIcon={<CopyIcon />}
                onClick={handleCopyError}
                disabled={copySuccess}
              >
                {copySuccess ? 'Copied!' : 'Copy'}
              </Button>
            </Box>

            {error.technical_details && (
              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="body2"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {error.technical_details}
                </Typography>
              </Box>
            )}

            {error.details && error.details.map((detail, index) => (
              <Box key={index} sx={{ mb: 1 }}>
                {detail.field && (
                  <Typography variant="caption" color="text.secondary">
                    Field: {detail.field}
                  </Typography>
                )}
                <Typography
                  variant="body2"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                    mt: 0.5,
                  }}
                >
                  {detail.message}
                </Typography>
                {detail.code && (
                  <Typography variant="caption" color="text.secondary">
                    Code: {detail.code}
                  </Typography>
                )}
              </Box>
            ))}

            {error.requestId && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mt: 2, display: 'block' }}
              >
                Request ID: {error.requestId}
              </Typography>
            )}
          </Box>
        </Collapse>
      )}
    </Alert>
  );
}
