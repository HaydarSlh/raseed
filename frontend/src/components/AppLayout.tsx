// App shell: left sidebar + scrollable main content area. Wrap each authenticated
// page's content in <AppLayout>…</AppLayout> in place of the old top NavBar.
import type { ReactNode } from 'react';
import Sidebar from './Sidebar';

export default function AppLayout({ children }: { children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-screen bg-app text-ink">
      <Sidebar />
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}
