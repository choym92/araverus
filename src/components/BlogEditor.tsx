'use client';

import { FC } from 'react';
import dynamic from 'next/dynamic';
import '@mdxeditor/editor/style.css';

const Editor = dynamic(() => import('./BlogEditorInner'), {
  ssr: false,
  loading: () => (
    <div className="h-96 flex items-center justify-center bg-gray-50 rounded-lg border border-gray-200">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600">Loading editor...</p>
      </div>
    </div>
  )
});

interface BlogEditorProps {
  markdown: string;
  onChange: (markdown: string) => void;
  onImageUpload?: (file: File) => Promise<string>;
  placeholder?: string;
  postIdForUpload?: number;
}

const BlogEditor: FC<BlogEditorProps> = (props) => {
  return <Editor {...props} />;
};

export default BlogEditor;