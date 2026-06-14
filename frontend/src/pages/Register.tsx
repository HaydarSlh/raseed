// Minimal register page: posts email+password to /auth/register then redirects to login.
import React, { FormEvent, useState } from 'react';
import { API_BASE_URL, authApi } from '../api/client';

export default function Register(): JSX.Element {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await authApi.register(email, password);
      setDone(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Registration failed.');
    }
  }

  if (done) return <p>Registered! <a href="/login">Sign in</a></p>;

  return (
    <main>
      <h1>Create account</h1>
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
        <button type="submit">Register</button>
      </form>
    </main>
  );
}
