import { Navigate } from 'react-router-dom';

interface Props {
  children: React.ReactNode;
}

export default function RequireAuth({ children }: Props): JSX.Element {
  const token = localStorage.getItem('raseed_token');
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
