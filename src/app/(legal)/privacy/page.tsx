import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description: 'Privacy policy for Araverus — how we collect, use, and protect your data.',
};

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16 text-gray-800 dark:text-gray-200">
      <h1 className="mb-8 text-3xl font-bold">Privacy Policy</h1>
      <p className="mb-6 text-sm text-gray-500">Last updated: March 4, 2026</p>

      <section className="space-y-6 leading-relaxed">
        <div>
          <h2 className="mb-2 text-xl font-semibold">1. Information We Collect</h2>
          <p>
            When you visit Araverus, we automatically collect certain information through cookies
            and similar technologies, including your IP address, browser type, pages visited, and
            time spent on our site.
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold">2. Google Analytics</h2>
          <p>
            We use Google Analytics 4 (GA4) to understand how visitors interact with our site. GA4
            collects data such as page views, session duration, and approximate geographic location.
            This data is processed by Google LLC. You can opt out by installing the{' '}
            <a
              href="https://tools.google.com/dlpage/gaoptout"
              className="text-blue-600 underline dark:text-blue-400"
              target="_blank"
              rel="noopener noreferrer"
            >
              Google Analytics Opt-out Browser Add-on
            </a>
            .
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold">3. Google AdSense &amp; Advertising Cookies</h2>
          <p>
            We may use Google AdSense to display advertisements. Google and its partners may use
            cookies to serve ads based on your prior visits to this site or other websites. You can
            opt out of personalized advertising by visiting{' '}
            <a
              href="https://www.google.com/settings/ads"
              className="text-blue-600 underline dark:text-blue-400"
              target="_blank"
              rel="noopener noreferrer"
            >
              Google Ads Settings
            </a>
            .
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold">4. Third-Party Vendors</h2>
          <p>
            We may partner with third-party ad networks and vendors who use cookies, web beacons,
            and similar technologies to collect information for ad personalization and measurement.
            These third parties are governed by their own privacy policies.
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold">5. Your Rights</h2>
          <p>
            You have the right to access, correct, or delete your personal data. You may also
            disable cookies through your browser settings. For requests, contact us at{' '}
            <a href="mailto:araverus.ai@gmail.com" className="text-blue-600 underline dark:text-blue-400">
              araverus.ai@gmail.com
            </a>
            .
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold">6. Data Retention</h2>
          <p>
            Analytics data is retained for up to 14 months in Google Analytics. We do not store
            personally identifiable information on our servers beyond what is necessary for site
            operation.
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-xl font-semibold">7. Changes to This Policy</h2>
          <p>
            We may update this Privacy Policy from time to time. Changes will be posted on this page
            with an updated date.
          </p>
        </div>
      </section>
    </main>
  );
}
