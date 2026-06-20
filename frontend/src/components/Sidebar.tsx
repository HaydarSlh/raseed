// Left sidebar navigation. Shows the Raseed logo + wordmark, the signed-in user's
// name (from /users/me), the nav links, a theme toggle, and a sign-out action.
import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';
import ThemeToggle from './ThemeToggle';

// `operatorOnly` links are hidden unless the signed-in user is an operator.
const LINKS: { to: string; label: string; operatorOnly?: boolean }[] = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/chat', label: 'Chat' },
  { to: '/upload', label: 'Upload' },
  { to: '/review', label: 'Review' },
  { to: '/ops', label: 'Ops', operatorOnly: true },
  { to: '/account', label: 'Account' },
];

export default function Sidebar(): JSX.Element {
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [isOperator, setIsOperator] = useState(false);
  const [logoOk, setLogoOk] = useState(true);

  useEffect(() => {
    let active = true;
    void authApi
      .me()
      .then((u) => {
        if (active) {
          setDisplayName(u.username ?? u.email);
          setIsOperator(u.is_operator);
        }
      })
      .catch(() => {
        /* not signed in / transient — leave name blank */
      });
    return () => {
      active = false;
    };
  }, []);

  const links = LINKS.filter((l) => !l.operatorOnly || isOperator);

  function handleSignOut() {
    localStorage.removeItem('raseed_token');
    navigate('/login', { replace: true });
  }

  const initial = (displayName ?? '?').charAt(0).toUpperCase();

  return (
    <aside className="w-60 shrink-0 h-screen sticky top-0 flex flex-col bg-surface border-r border-line">
      {/* Brand */}
      <div className="px-5 py-4 flex items-center gap-2.5 border-b border-line">
        {logoOk && (
          <img
            src="/raseed-logo.png"
            alt="Raseed"
            className="w-8 h-8 rounded-md object-contain"
            onError={() => setLogoOk(false)}
          />
        )}
        <span className="text-xl font-bold tracking-tight text-indigo-600 dark:text-indigo-400">
          Raseed
        </span>
      </div>

      {/* User */}
      {displayName && (
        <div className="px-5 py-3 flex items-center gap-3 border-b border-line">
          <div className="w-9 h-9 rounded-full bg-indigo-600 text-white flex items-center justify-center text-sm font-semibold shrink-0">
            {initial}
          </div>
          <div className="min-w-0">
            <p className="text-xs text-faint">Signed in as</p>
            <p className="text-sm font-medium text-ink truncate" title={displayName}>
              {displayName}
            </p>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {links.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300'
                  : 'text-faint hover:bg-elevated hover:text-ink'
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-line flex items-center gap-2">
        <button
          onClick={handleSignOut}
          className="flex-1 text-left px-3 py-2 rounded-lg text-sm font-medium text-faint hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-500/10 dark:hover:text-red-400 transition-colors"
        >
          Sign out
        </button>
        <ThemeToggle />
      </div>
    </aside>
  );
}
