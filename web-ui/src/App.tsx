/**
 * Main App component with routing and theme
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { useMemo } from 'react';
import { Layout } from './components/Layout';

// Import pages (will create these next)
import { DashboardPage } from './pages/DashboardPage';
import { ScenariosPage } from './pages/ScenariosPage';
import { RunScenarioPage } from './pages/RunScenarioPage';
import { EnvironmentsPage } from './pages/EnvironmentsPage';
import { ConfigPage } from './pages/ConfigPage';
import { CleanupPage } from './pages/CleanupPage';
import { PacksPage } from './pages/PacksPage';
import { SetupPage } from './pages/SetupPage';

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000, // 30 seconds
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  // Create MUI dark theme
  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode: 'dark',
        },
      }),
    []
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BrowserRouter>
          <Routes>
            {/* Setup wizard (no layout) */}
            <Route path="/setup" element={<SetupPage />} />

            {/* Main app routes (with layout) */}
            <Route element={<Layout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/scenarios" element={<ScenariosPage />} />
              <Route path="/scenarios/:scenarioId/run" element={<RunScenarioPage />} />
              <Route path="/environments" element={<EnvironmentsPage />} />
              <Route path="/config" element={<ConfigPage />} />
              <Route path="/cleanup" element={<CleanupPage />} />
              <Route path="/packs" element={<PacksPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
