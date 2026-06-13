// Root application component — renders an empty shell so the frontend service
// boots and serves in Phase 0. Real pages/routes arrive in later phases.
export default function App(): JSX.Element {
  return (
    <main>
      <h1>Raseed</h1>
      <p>Phase 0 skeleton — the stack boots empty.</p>
    </main>
  );
}
