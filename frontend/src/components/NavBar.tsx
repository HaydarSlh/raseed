import { Link, useNavigate } from 'react-router-dom';

export default function NavBar(): JSX.Element {
  const navigate = useNavigate();

  function handleSignOut() {
    localStorage.removeItem('raseed_token');
    navigate('/login', { replace: true });
  }

  return (
    <nav className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200 shadow-sm">
      <span className="text-xl font-bold text-indigo-600">Raseed</span>
      <div className="flex items-center gap-4">
        <Link
          to="/chat"
          className="text-sm font-medium text-gray-700 hover:text-indigo-600 transition-colors"
        >
          Chat
        </Link>
        <Link
          to="/upload"
          className="text-sm font-medium text-gray-700 hover:text-indigo-600 transition-colors"
        >
          Upload
        </Link>
        <Link
          to="/review"
          className="text-sm font-medium text-gray-700 hover:text-indigo-600 transition-colors"
        >
          Review
        </Link>
        <Link
          to="/ops"
          className="text-sm font-medium text-gray-700 hover:text-indigo-600 transition-colors"
        >
          Ops
        </Link>
        <Link
          to="/account"
          className="text-sm font-medium text-gray-700 hover:text-indigo-600 transition-colors"
        >
          Account
        </Link>
        <button
          onClick={handleSignOut}
          className="text-sm font-medium text-gray-500 hover:text-red-600 transition-colors"
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
