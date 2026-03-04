import { ArrowDownTrayIcon, ArrowLeftIcon } from '@heroicons/react/24/outline';
import Link from 'next/link';

export const metadata = {
  title: 'Resume | Paul Cho',
  description: 'View and download the resume of Paul Cho',
};

export default function ResumePage() {
  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header bar */}
      <div className="sticky top-0 z-10 border-b border-neutral-200 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm text-neutral-600 transition hover:text-neutral-900"
          >
            <ArrowLeftIcon className="h-4 w-4" />
            Back to Home
          </Link>
          <a
            href="/resume.pdf"
            download
            className="inline-flex items-center gap-2 rounded-full bg-neutral-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-neutral-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900 focus-visible:ring-offset-2"
          >
            <ArrowDownTrayIcon className="h-4 w-4" />
            Download PDF
          </a>
        </div>
      </div>

      {/* PDF Viewer */}
      <div className="mx-auto max-w-5xl px-6 py-8">
        <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-sm">
          <object
            data="/resume.pdf"
            type="application/pdf"
            className="h-[calc(100vh-12rem)] w-full"
          >
            {/* Fallback for browsers that don't support embedded PDF or if PDF is missing */}
            <div className="flex h-[calc(100vh-12rem)] flex-col items-center justify-center p-8 text-center">
              <div className="mb-6 rounded-full bg-neutral-100 p-4">
                <ArrowDownTrayIcon className="h-8 w-8 text-neutral-400" />
              </div>
              <h2 className="mb-2 text-xl font-medium text-neutral-900">
                Resume Preview Unavailable
              </h2>
              <p className="mb-6 max-w-md text-neutral-500">
                Your browser doesn&apos;t support embedded PDFs, or the resume file is being updated.
              </p>
              <a
                href="/resume.pdf"
                download
                className="inline-flex items-center gap-2 rounded-full bg-neutral-900 px-6 py-3 text-sm font-medium text-white transition hover:bg-neutral-800"
              >
                <ArrowDownTrayIcon className="h-4 w-4" />
                Download Resume
              </a>
            </div>
          </object>
        </div>
      </div>
    </div>
  );
}
