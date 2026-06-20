// Route guard for operator-only pages (e.g. /ops). Assumes RequireAuth has
// already ensured a token exists; this layer fetches /users/me and only renders
// children when is_operator is true. Non-operators are redirected to the
// dashboard instead of hitting a raw 403 from the API.
import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { authApi } from '../api/client';

interface Props {
  children: React.ReactNode;
}

type State = 'loading' | 'operator' | 'denied';

export default function RequireOperator({ children }: Props): JSX.Element {
  const [state, setState] = useState<State>('loading');

  useEffect(() => {
    let active = true;
    void authApi
      .me()
      .then((u) => {
        if (active) setState(u.is_operator ? 'operator' : 'denied');
      })
      .catch(() => {
        if (active) setState('denied');
      });
    return () => {
      active = false;
    };
  }, []);

  if (state === 'loading') {
    return <div className="p-8 text-sm text-faint">Loading…</div>;
  }
  if (state === 'denied') return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}
