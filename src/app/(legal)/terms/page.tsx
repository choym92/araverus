import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Terms of Service',
  description: 'Terms of service for using Araverus.',
};

export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16 text-gray-800 dark:text-gray-200">
      <h1 className="mb-8 text-3xl font-bold">Terms of Service</h1>
      <p className="mb-6 text-sm text-gray-500">Last updated: March 4, 2026</p>

      <section className="space-y-6 leading-relaxed">
        <div>
          <h2 className="mb-2 text-xl font-semibold">1. Acceptance of Terms</h2>
          <p>
            By accessing and using Araverus (&quot;the Site&quot;), you agree to be bound by these
            Terms of Service. If you do not agree, please do not use the Site.
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold">2. Financial Disclaimer</h2>
          <p>
            <strong>
              The content on this site does not constitute financial, investment, or trading advice.
            </strong>{' '}
            All news, analysis, and briefings are provided for informational purposes only. You
            should not make any investment decisions based solely on the information presented here.
            Always consult a qualified financial advisor before making investment decisions. Use of
            this site is at your own risk.
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold">3. AI-Powered Content Disclaimer</h2>
          <p>
            News briefings and summaries on Araverus are curated and generated using artificial
            intelligence. While we use deterministic settings to maximize accuracy, AI-powered
            content may still contain errors or inaccuracies. We do not guarantee the completeness
            or reliability of any content on this site.
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold">4. Intellectual Property</h2>
          <p>
            All original content, branding, and design on this site are the property of Araverus.
            You may not reproduce, distribute, or create derivative works without prior written
            consent.
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold">5. Limitation of Liability</h2>
          <p>
            Araverus and its operators shall not be liable for any direct, indirect, incidental, or
            consequential damages arising from your use of the Site, including but not limited to
            financial losses from investment decisions.
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold">6. Changes to Terms</h2>
          <p>
            We reserve the right to modify these Terms at any time. Continued use of the Site after
            changes constitutes acceptance of the updated Terms.
          </p>
        </div>
      </section>
    </main>
  );
}
