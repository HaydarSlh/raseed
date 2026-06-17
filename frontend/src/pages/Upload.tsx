import { useNavigate } from 'react-router-dom';
import NavBar from '../components/NavBar';
import UploadDropzone from '../components/UploadDropzone';
import ManualEntryForm from '../components/ManualEntryForm';

export default function Upload(): JSX.Element {
  const navigate = useNavigate();

  function onSuccess() {
    navigate('/dashboard');
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar />
      <main className="max-w-2xl mx-auto px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900 mb-8">Upload Statement</h1>

        <UploadDropzone onSuccess={onSuccess} />

        <div className="relative my-8">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-200" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="bg-gray-50 px-3 text-gray-400">or add manually</span>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
          <h2 className="text-base font-semibold text-gray-800 mb-5">Add a single transaction</h2>
          <ManualEntryForm onSuccess={onSuccess} />
        </div>
      </main>
    </div>
  );
}
