import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Contact',
  description: 'Get in touch with Araverus.',
};

export default function ContactPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16 text-gray-800 dark:text-gray-200">
      <h1 className="mb-8 text-3xl font-bold">Contact</h1>
      <p className="leading-relaxed">
        For inquiries, feedback, or support, please reach out at{' '}
        <a
          href="mailto:araverus.ai@gmail.com"
          className="text-blue-600 underline dark:text-blue-400"
        >
          araverus.ai@gmail.com
        </a>
        .
      </p>
    </main>
  );
}
