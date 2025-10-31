/**
 * Hook for checking for updates on app mount
 */

import { useEffect, useState } from 'react';
import { versionApi } from '../api/endpoints';
import type { UpdateCheckResponse } from '../api/endpoints/version';

interface UseUpdateCheckResult {
  updateAvailable: boolean;
  updateInfo: UpdateCheckResponse | null;
  isChecking: boolean;
  error: string | null;
}

/**
 * Check for updates once on mount
 */
export const useUpdateCheck = (): UseUpdateCheckResult => {
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [updateInfo, setUpdateInfo] = useState<UpdateCheckResponse | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const checkForUpdates = async () => {
      setIsChecking(true);
      setError(null);

      try {
        const response = await versionApi.checkForUpdates();
        setUpdateInfo(response);
        setUpdateAvailable(response.update_available);
      } catch (err: any) {
        // Silently fail - don't bother the user if update check fails
        console.warn('Failed to check for updates:', err);
        setError(err.message || 'Failed to check for updates');
      } finally {
        setIsChecking(false);
      }
    };

    checkForUpdates();
  }, []); // Run once on mount

  return {
    updateAvailable,
    updateInfo,
    isChecking,
    error,
  };
};
