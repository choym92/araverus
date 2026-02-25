'use client';

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="text-center px-6">
        <h1 className="text-6xl font-light tracking-tight text-neutral-900 mb-4">
          Error
        </h1>
        <p className="text-lg text-neutral-500 mb-8">
          Something went wrong. Please try again.
        </p>
        <button
          onClick={reset}
          className="inline-block px-6 py-3 text-sm font-medium text-white bg-neutral-900 rounded-lg hover:bg-neutral-800 transition-colors"
        >
          Try Again
        </button>
      </div>
    </div>
  );
}
