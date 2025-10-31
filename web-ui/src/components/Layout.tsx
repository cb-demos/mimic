/**
 * Main layout component with navigation drawer and app bar
 */

import {
  AppBar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Chip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard,
  PlayArrow,
  Storage,
  Settings,
  CleaningServices,
  Inventory,
} from '@mui/icons-material';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAppStore } from '../store/appStore';
import { EnvironmentSwitcher } from './EnvironmentSwitcher';
import { UpdateBanner } from './UpdateBanner';

const drawerWidth = 240;

interface NavigationItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  badge?: number;
}

export function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { drawerOpen, toggleDrawer } = useAppStore();

  const navigationItems: NavigationItem[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <Dashboard />, path: '/' },
    { id: 'scenarios', label: 'Scenarios', icon: <PlayArrow />, path: '/scenarios' },
    { id: 'environments', label: 'Environments', icon: <Storage />, path: '/environments' },
    { id: 'config', label: 'Configuration', icon: <Settings />, path: '/config' },
    { id: 'instances', label: 'Instances', icon: <CleaningServices />, path: '/cleanup' },
    { id: 'packs', label: 'Scenario Packs', icon: <Inventory />, path: '/packs' },
  ];

  return (
    <Box sx={{ display: 'flex' }}>
      {/* App Bar */}
      <AppBar
        position="fixed"
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            aria-label="toggle drawer"
            edge="start"
            onClick={toggleDrawer}
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div">
            Mimic
          </Typography>

          {/* Environment switcher */}
          <EnvironmentSwitcher />

          {/* Spacer */}
          <Box sx={{ flexGrow: 1 }} />
        </Toolbar>
      </AppBar>

      {/* Navigation Drawer */}
      <Drawer
        variant="persistent"
        open={drawerOpen}
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
          },
        }}
      >
        <Toolbar /> {/* Spacer for app bar */}
        <Box sx={{ overflow: 'auto' }}>
          <List>
            {navigationItems.map((item) => (
              <ListItem key={item.id} disablePadding>
                <ListItemButton
                  selected={location.pathname === item.path}
                  onClick={() => navigate(item.path)}
                >
                  <ListItemIcon>{item.icon}</ListItemIcon>
                  <ListItemText primary={item.label} />
                  {item.badge !== undefined && (
                    <Chip label={item.badge} size="small" color="primary" />
                  )}
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Box>
      </Drawer>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { sm: `calc(100% - ${drawerOpen ? drawerWidth : 0}px)` },
          ml: drawerOpen ? 0 : `-${drawerWidth}px`,
          transition: (theme) =>
            theme.transitions.create(['margin', 'width'], {
              easing: theme.transitions.easing.sharp,
              duration: theme.transitions.duration.leavingScreen,
            }),
        }}
      >
        <Toolbar /> {/* Spacer for app bar */}
        <UpdateBanner />
        <Outlet />
      </Box>
    </Box>
  );
}
