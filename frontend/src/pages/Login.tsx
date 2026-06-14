// Minimal login page: posts credentials, stores bearer token in localStorage.
import { FormEvent, useState } from 'react';
import { authApi } from '../api/client';

export default function Login(): JSX.Element {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [token, setToken] = useState('');

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    try {
      const t = await authApi.login(email, password);
      localStorage.setItem('raseed_token', t);
      setToken(t);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed.');
    }
  }

  if (token) return <p>Signed in. <a href="/">Go to app</a></p>;

  return (
    <main>
      <h1>Sign in</h1>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <form onSubmit={handleSubmit}>
        <label>
          Email
          <input type="email" value={email} onChange={e => setEmail(e.target.value)} required />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        </label>
        <button type="submit">Sign in</button>
      </form>
      <p>No account? <a href="/register">Register</a></p>
    </main>
  );
}
