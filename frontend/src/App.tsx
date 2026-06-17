// Root application component — wires the SPA routes and auth guards.
import { Routes, Route, Navigate } from 'react-router-dom';
import RequireAuth from './auth/RequireAuth';
import Login from './pages/Login';
import Register from './pages/Register';
import Upload from './pages/Upload';
import Dashboard from './pages/Dashboard';
import Chat from './pages/Chat';

export default function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/upload"
        element={
          <RequireAuth>
            <Upload />
          </RequireAuth>
        }
      />
      <Route
        path="/dashboard"
        element={
          <RequireAuth>
            <Dashboard />
          </RequireAuth>
        }
      />
      <Route
        path="/chat"
        element={
          <RequireAuth>
            <Chat />
          </RequireAuth>
        }
      />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
