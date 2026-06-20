import { useNavigate } from 'react-router-dom';
import AppLayout from '../components/AppLayout';
import UploadDropzone from '../components/UploadDropzone';
import ManualEntryForm from '../components/ManualEntryForm';

export default function Upload(): JSX.Element {
  const navigate = useNavigate();

  function onSuccess() {
    navigate('/dashboard');
  }

  return (
    <AppLayout>
      <main className="max-w-2xl mx-auto px-4 py-10">
        <h1 className="text-2xl font-bold text-ink mb-8">Upload Statement</h1>

        <UploadDropzone onSuccess={onSuccess} />

        <div className="relative my-8">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-line" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="bg-elevated px-3 text-faint">or add manually</span>
          </div>
        </div>

        <div className="bg-surface rounded-xl border border-line p-6 shadow-sm">
          <h2 className="text-base font-semibold text-ink mb-5">Add a single transaction</h2>
          <ManualEntryForm onSuccess={onSuccess} />
        </div>
      </main>
    </AppLayout>
  );
}
