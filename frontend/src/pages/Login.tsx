// Login page: posts credentials, stores bearer token, navigates to dashboard.
import { FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';

export default function Login(): JSX.Element {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [logoOk, setLogoOk] = useState(true);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    try {
      const t = await authApi.login(email, password);
      localStorage.setItem('raseed_token', t);
      navigate('/dashboard', { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed.');
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-app px-4">
      <div className="w-full max-w-sm card p-8">
        <div className="flex flex-col items-center mb-6">
          {logoOk && (
            <img
              src="/raseed-logo.png"
              alt="Raseed"
              className="w-14 h-14 rounded-xl object-contain mb-3"
              onError={() => setLogoOk(false)}
            />
          )}
          <h1 className="text-2xl font-bold text-ink">Sign in to Raseed</h1>
        </div>
        {error && (
          <p className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700 dark:bg-red-500/10 dark:border-red-500/30 dark:text-red-300">
            {error}
          </p>
        )}
        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-faint mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-faint mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="input"
            />
          </div>
          <button type="submit" className="btn-primary w-full">
            Sign in
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-faint">
          No account?{' '}
          <Link to="/register" className="text-indigo-600 dark:text-indigo-400 hover:underline">
            Register
          </Link>
        </p>
      </div>
    </main>
  );
}
