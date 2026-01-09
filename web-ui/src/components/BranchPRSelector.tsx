/**
 * BranchPRSelector - Component for selecting a branch or PR from GitHub
 */

import { useState } from 'react';
import {
  Box,
  Tabs,
  Tab,
  List,
  ListItemButton,
  ListItemText,
  TextField,
  Alert,
  CircularProgress,
  Typography,
  Chip,
  Button,
} from '@mui/material';
import { Search, AccountTree, CallMerge } from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { packsApi } from '../api/endpoints';
import type { GitHubBranch, GitHubPullRequest } from '../types/api';

interface BranchPRSelectorProps {
  gitUrl: string;
  onSelect: (selection: {
    type: 'branch' | 'pr';
    branch: string;
    prNumber?: number;
    prTitle?: string;
    prAuthor?: string;
  }) => void;
  defaultBranch?: string;
  disabled?: boolean;
}

export function BranchPRSelector({
  gitUrl,
  onSelect,
  defaultBranch,
  disabled = false,
}: BranchPRSelectorProps) {
  const [activeTab, setActiveTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedBranch, setSelectedBranch] = useState<string | null>(null);
  const [selectedPR, setSelectedPR] = useState<number | null>(null);

  // Fetch branches and PRs
  const {
    data: refs,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['discover-refs', gitUrl],
    queryFn: () => packsApi.discoverRefs(gitUrl),
    enabled: !!gitUrl,
  });

  // Filter branches and PRs based on search query
  const filteredBranches =
    refs?.branches?.filter((branch) =>
      branch.name.toLowerCase().includes(searchQuery.toLowerCase())
    ) || [];

  const filteredPRs =
    refs?.pull_requests?.filter(
      (pr) =>
        pr.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        pr.author.toLowerCase().includes(searchQuery.toLowerCase()) ||
        pr.number.toString().includes(searchQuery)
    ) || [];

  // Handle branch selection
  const handleBranchSelect = (branch: GitHubBranch) => {
    setSelectedBranch(branch.name);
    setSelectedPR(null);
    onSelect({
      type: 'branch',
      branch: branch.name,
    });
  };

  // Handle PR selection
  const handlePRSelect = (pr: GitHubPullRequest) => {
    setSelectedPR(pr.number);
    setSelectedBranch(null);
    onSelect({
      type: 'pr',
      branch: pr.head_branch,
      prNumber: pr.number,
      prTitle: pr.title,
      prAuthor: pr.author,
    });
  };

  // Show loading state
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  // Show error state
  if (error || refs?.error) {
    return (
      <Alert
        severity="error"
        sx={{ mb: 2 }}
        action={
          <Button color="inherit" size="small" onClick={() => refetch()}>
            Retry
          </Button>
        }
      >
        {refs?.error || 'Failed to fetch branches and PRs. Please check your GitHub token and try again.'}
      </Alert>
    );
  }

  // Show empty state
  if (!refs || (refs.branches.length === 0 && refs.pull_requests.length === 0)) {
    return (
      <Alert severity="info" sx={{ mb: 2 }}>
        No branches or pull requests found for this repository.
      </Alert>
    );
  }

  return (
    <Box>
      {/* Search field */}
      <TextField
        fullWidth
        size="small"
        placeholder="Search branches or PRs..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        InputProps={{
          startAdornment: <Search sx={{ mr: 1, color: 'text.secondary' }} />,
        }}
        sx={{ mb: 2 }}
      />

      {/* Tabs for Branches and Pull Requests */}
      <Tabs value={activeTab} onChange={(_, value) => setActiveTab(value)} sx={{ mb: 2 }}>
        <Tab label={`Branches (${filteredBranches.length})`} />
        <Tab label={`Pull Requests (${filteredPRs.length})`} />
      </Tabs>

      {/* Branches tab */}
      {activeTab === 0 && (
        <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
          {filteredBranches.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
              No branches found matching "{searchQuery}"
            </Typography>
          ) : (
            <List dense>
              {filteredBranches.map((branch) => (
                <ListItemButton
                  key={branch.name}
                  selected={selectedBranch === branch.name}
                  onClick={() => handleBranchSelect(branch)}
                  disabled={disabled}
                >
                  <AccountTree fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2">{branch.name}</Typography>
                        {branch.name === (defaultBranch || refs.default_branch) && (
                          <Chip label="Default" size="small" color="primary" variant="outlined" />
                        )}
                        {branch.protected && (
                          <Chip label="Protected" size="small" color="warning" variant="outlined" />
                        )}
                      </Box>
                    }
                    secondary={branch.sha.substring(0, 7)}
                  />
                </ListItemButton>
              ))}
            </List>
          )}
        </Box>
      )}

      {/* Pull Requests tab */}
      {activeTab === 1 && (
        <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
          {filteredPRs.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
              {searchQuery
                ? `No pull requests found matching "${searchQuery}"`
                : 'No open pull requests'}
            </Typography>
          ) : (
            <List dense>
              {filteredPRs.map((pr) => (
                <ListItemButton
                  key={pr.number}
                  selected={selectedPR === pr.number}
                  onClick={() => handlePRSelect(pr)}
                  disabled={disabled}
                >
                  <CallMerge fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2">
                          #{pr.number}: {pr.title}
                        </Typography>
                        {pr.state === 'open' && (
                          <Chip label="Open" size="small" color="success" variant="outlined" />
                        )}
                        {pr.state === 'closed' && (
                          <Chip label="Closed" size="small" color="default" variant="outlined" />
                        )}
                      </Box>
                    }
                    secondary={`by ${pr.author} • ${pr.head_branch}`}
                  />
                </ListItemButton>
              ))}
            </List>
          )}
        </Box>
      )}
    </Box>
  );
}
