/**
 * Update banner component - displays when updates are available
 */

import { useState, useEffect } from 'react';
import {
  Alert,
  Button,
  Box,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Typography,
  Link,
} from '@mui/material';
import { Download, Close } from '@mui/icons-material';
import { useUpdateCheck } from '../hooks/useUpdateCheck';
import { versionApi } from '../api/endpoints';

const DISMISSED_KEY = 'mimic-update-dismissed';

export function UpdateBanner() {
  const { updateAvailable, updateInfo } = useUpdateCheck();
  const [dismissed, setDismissed] = useState(false);
  const [upgradeDialogOpen, setUpgradeDialogOpen] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const [upgradeOutput, setUpgradeOutput] = useState<string | null>(null);
  const [upgradeComplete, setUpgradeComplete] = useState(false);

  // Check if this version was already dismissed
  useEffect(() => {
    if (updateInfo?.latest_version) {
      const dismissedVersion = localStorage.getItem(DISMISSED_KEY);
      if (dismissedVersion === updateInfo.latest_version) {
        setDismissed(true);
      }
    }
  }, [updateInfo]);

  const handleDismiss = () => {
    if (updateInfo?.latest_version) {
      localStorage.setItem(DISMISSED_KEY, updateInfo.latest_version);
    }
    setDismissed(true);
  };

  const handleUpgradeClick = () => {
    setUpgradeDialogOpen(true);
    setUpgradeComplete(false);
    setUpgradeOutput(null);
  };

  const handleUpgrade = async () => {
    setUpgrading(true);
    setUpgradeOutput(null);

    try {
      const response = await versionApi.upgrade();
      setUpgradeOutput(response.output || response.message);
      setUpgradeComplete(true);
    } catch (error: any) {
      setUpgradeOutput(
        `Error during upgrade:\n${error.message}`
      );
      setUpgradeComplete(false);
    } finally {
      setUpgrading(false);
    }
  };

  const handleCloseDialog = () => {
    setUpgradeDialogOpen(false);
    if (upgradeComplete) {
      // Clear dismissal so user sees the banner again after restart
      localStorage.removeItem(DISMISSED_KEY);
    }
  };

  // Don't show banner if no update available, dismissed, or checking
  if (!updateAvailable || dismissed) {
    return null;
  }

  return (
    <>
      <Alert
        severity="info"
        sx={{
          mb: 2,
          '& .MuiAlert-message': {
            width: '100%',
          },
        }}
        action={
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Button
              color="inherit"
              size="small"
              startIcon={<Download />}
              onClick={handleUpgradeClick}
            >
              Upgrade Now
            </Button>
            <Button
              color="inherit"
              size="small"
              startIcon={<Close />}
              onClick={handleDismiss}
            >
              Dismiss
            </Button>
          </Box>
        }
      >
        <Box>
          <Typography variant="body2" component="div">
            <strong>Update Available</strong> — Your version: {updateInfo?.current_version}{' '}
            → Latest: {updateInfo?.latest_version}
          </Typography>
          <Typography variant="caption" component="div" sx={{ mt: 0.5 }}>
            <Link
              href={`https://github.com/cb-demos/mimic`}
              target="_blank"
              rel="noopener noreferrer"
              color="inherit"
            >
              View on GitHub
            </Link>
          </Typography>
        </Box>
      </Alert>

      {/* Upgrade Dialog */}
      <Dialog
        open={upgradeDialogOpen}
        onClose={upgrading ? undefined : handleCloseDialog}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {upgradeComplete ? 'Upgrade Complete' : 'Upgrade Mimic'}
        </DialogTitle>
        <DialogContent>
          {!upgrading && !upgradeOutput && (
            <Typography>
              This will upgrade Mimic to the latest version and update all scenario packs.
              The process may take a minute or two.
            </Typography>
          )}

          {upgrading && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <CircularProgress size={24} />
              <Typography>Upgrading Mimic and scenario packs...</Typography>
            </Box>
          )}

          {upgradeOutput && (
            <Box
              sx={{
                mt: 2,
                p: 2,
                backgroundColor: 'background.default',
                border: 1,
                borderColor: 'divider',
                borderRadius: 1,
                fontFamily: 'monospace',
                fontSize: '0.875rem',
                whiteSpace: 'pre-wrap',
                maxHeight: 400,
                overflow: 'auto',
              }}
            >
              {upgradeOutput}
            </Box>
          )}

          {upgradeComplete && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              Please restart the <code>mimic ui</code> server to use the new version. Stop the
              server with Ctrl+C and run <code>mimic ui</code> again.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          {!upgrading && !upgradeOutput && (
            <>
              <Button onClick={handleCloseDialog}>Cancel</Button>
              <Button
                onClick={handleUpgrade}
                variant="contained"
                startIcon={<Download />}
              >
                Start Upgrade
              </Button>
            </>
          )}
          {(upgrading || upgradeOutput) && (
            <Button
              onClick={handleCloseDialog}
              disabled={upgrading}
              variant={upgradeComplete ? 'contained' : 'text'}
            >
              Close
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </>
  );
}
