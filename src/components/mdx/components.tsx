import { Figure } from './Figure';
import Link from 'next/link';
import { ReactNode } from 'react';

// Custom components for MDX rendering
export const mdxComponents = {
  // Custom components
  Figure,
  
  // Override default HTML elements
  a: ({ href, children, ...props }: { href?: string; children?: ReactNode }) => {
    // Handle internal links
    if (href && href.startsWith('/')) {
      return (
        <Link href={href} className="text-blue-600 hover:text-blue-800 underline" {...props}>
          {children}
        </Link>
      );
    }
    // External links
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 hover:text-blue-800 underline"
        {...props}
      >
        {children}
      </a>
    );
  },
  
  h1: ({ children, ...props }: { children?: ReactNode }) => (
    <h1 className="text-4xl font-bold mt-8 mb-4" {...props}>
      {children}
    </h1>
  ),
  
  h2: ({ children, ...props }: { children?: ReactNode }) => (
    <h2 className="text-3xl font-semibold mt-6 mb-3" {...props}>
      {children}
    </h2>
  ),
  
  h3: ({ children, ...props }: { children?: ReactNode }) => (
    <h3 className="text-2xl font-semibold mt-4 mb-2" {...props}>
      {children}
    </h3>
  ),
  
  p: ({ children, ...props }: { children?: ReactNode }) => (
    <p className="my-4 leading-relaxed" {...props}>
      {children}
    </p>
  ),
  
  ul: ({ children, ...props }: { children?: ReactNode }) => (
    <ul className="list-disc list-inside my-4 space-y-2" {...props}>
      {children}
    </ul>
  ),
  
  ol: ({ children, ...props }: { children?: ReactNode }) => (
    <ol className="list-decimal list-inside my-4 space-y-2" {...props}>
      {children}
    </ol>
  ),
  
  li: ({ children, ...props }: { children?: ReactNode }) => (
    <li className="ml-4" {...props}>
      {children}
    </li>
  ),
  
  blockquote: ({ children, ...props }: { children?: ReactNode }) => (
    <blockquote 
      className="border-l-4 border-gray-300 pl-4 my-4 italic text-gray-700 dark:text-gray-300"
      {...props}
    >
      {children}
    </blockquote>
  ),
  
  code: ({ children, ...props }: { children?: ReactNode }) => (
    <code 
      className="bg-gray-100 dark:bg-gray-800 rounded px-1 py-0.5 font-mono text-sm"
      {...props}
    >
      {children}
    </code>
  ),
  
  pre: ({ children, ...props }: { children?: ReactNode }) => (
    <pre 
      className="bg-gray-100 dark:bg-gray-900 rounded-lg p-4 overflow-x-auto my-4"
      {...props}
    >
      {children}
    </pre>
  ),
  
  table: ({ children, ...props }: { children?: ReactNode }) => (
    <div className="overflow-x-auto my-4">
      <table className="min-w-full divide-y divide-gray-200" {...props}>
        {children}
      </table>
    </div>
  ),
  
  th: ({ children, ...props }: { children?: ReactNode }) => (
    <th 
      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
      {...props}
    >
      {children}
    </th>
  ),
  
  td: ({ children, ...props }: { children?: ReactNode }) => (
    <td className="px-6 py-4 whitespace-nowrap text-sm" {...props}>
      {children}
    </td>
  ),
  
  hr: (props: React.HTMLAttributes<HTMLHRElement>) => (
    <hr className="my-8 border-gray-200 dark:border-gray-700" {...props} />
  ),
};