/**
 * Credential Validation Status - Shows validation status for CloudBees and GitHub credentials
 */

import { Box, Alert, Chip, CircularProgress, Typography } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import type { ValidateAllCredentialsResponse } from '../types/api';

interface CredentialValidationStatusProps {
  isValidating: boolean;
  validationResult: ValidateAllCredentialsResponse | null;
  error: string | null;
}

export function CredentialValidationStatus({
  isValidating,
  validationResult,
  error,
}: CredentialValidationStatusProps) {
  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (isValidating) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, p: 2, border: '1px solid #e0e0e0', borderRadius: 1 }}>
        <CircularProgress size={24} />
        <Typography variant="body2">Validating credentials...</Typography>
      </Box>
    );
  }

  if (!validationResult) {
    return null;
  }

  const allValid = validationResult.cloudbees_valid && validationResult.github_valid;

  return (
    <Box sx={{ mb: 2 }}>
      <Alert severity={allValid ? 'success' : 'error'} sx={{ mb: 2 }}>
        <Typography variant="body2" fontWeight="medium" gutterBottom>
          Credential Validation {allValid ? 'Successful' : 'Failed'}
        </Typography>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 1 }}>
          {/* CloudBees status */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {validationResult.cloudbees_valid ? (
              <>
                <CheckCircleIcon color="success" fontSize="small" />
                <Typography variant="body2">CloudBees API</Typography>
                <Chip label="Valid" color="success" size="small" />
              </>
            ) : (
              <>
                <ErrorIcon color="error" fontSize="small" />
                <Typography variant="body2">CloudBees API</Typography>
                <Chip label="Invalid" color="error" size="small" />
                {validationResult.cloudbees_error && (
                  <Typography variant="caption" color="error">
                    {validationResult.cloudbees_error}
                  </Typography>
                )}
              </>
            )}
          </Box>

          {/* GitHub status */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {validationResult.github_valid ? (
              <>
                <CheckCircleIcon color="success" fontSize="small" />
                <Typography variant="body2">GitHub API</Typography>
                <Chip label="Valid" color="success" size="small" />
              </>
            ) : (
              <>
                <ErrorIcon color="error" fontSize="small" />
                <Typography variant="body2">GitHub API</Typography>
                <Chip label="Invalid" color="error" size="small" />
                {validationResult.github_error && (
                  <Typography variant="caption" color="error">
                    {validationResult.github_error}
                  </Typography>
                )}
              </>
            )}
          </Box>
        </Box>
      </Alert>

      {!allValid && (
        <Alert severity="info">
          Please check your credentials configuration in the Config page before proceeding.
        </Alert>
      )}
    </Box>
  );
}
