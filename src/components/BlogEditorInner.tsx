'use client';

import { FC } from 'react';
import {
  MDXEditor,
  headingsPlugin,
  listsPlugin,
  quotePlugin,
  thematicBreakPlugin,
  markdownShortcutPlugin,
  linkPlugin,
  linkDialogPlugin,
  imagePlugin,
  tablePlugin,
  codeBlockPlugin,
  codeMirrorPlugin,
  diffSourcePlugin,
  toolbarPlugin,
  UndoRedo,
  BoldItalicUnderlineToggles,
  BlockTypeSelect,
  CreateLink,
  InsertImage,
  InsertTable,
  InsertCodeBlock,
  ListsToggle,
  DiffSourceToggleWrapper
} from '@mdxeditor/editor';

interface BlogEditorProps {
  markdown: string;
  onChange: (markdown: string) => void;
  onImageUpload?: (file: File) => Promise<string>;
  placeholder?: string;
  postIdForUpload?: number;
}

const BlogEditorInner: FC<BlogEditorProps> = ({
  markdown,
  onChange,
  onImageUpload,
  placeholder = 'Write your post in Markdown…',
  postIdForUpload
}) => {
  // Default image upload handler
  const defaultUpload = async (file: File): Promise<string> => {
    if (!postIdForUpload) throw new Error('postIdForUpload is required for default upload handler');
    const fd = new FormData();
    fd.set('file', file);
    fd.set('postId', String(postIdForUpload));
    fd.set('type', 'content');

    const res = await fetch('/api/blog/upload', { method: 'POST', body: fd });
    if (!res.ok) throw new Error('Upload failed');
    const { url } = await res.json();
    return url as string;
  };

  return (
    <div className="blog-editor rounded-lg border border-gray-200 bg-white">
      <MDXEditor
        markdown={markdown}
        onChange={onChange}
        placeholder={placeholder}
        contentEditableClassName="prose prose-lg max-w-none min-h-[500px] p-4 focus:outline-none"
        plugins={[
          headingsPlugin(),
          listsPlugin(),
          quotePlugin(),
          thematicBreakPlugin(),
          markdownShortcutPlugin(),
          linkPlugin(),
          linkDialogPlugin(),
          imagePlugin({
            imageUploadHandler: onImageUpload ?? defaultUpload,
            imageAutocompleteSuggestions: []
          }),
          tablePlugin(),
          codeBlockPlugin({ defaultCodeBlockLanguage: 'js' }),
          codeMirrorPlugin({
            codeBlockLanguages: {
              js: 'JavaScript',
              jsx: 'JSX',
              ts: 'TypeScript',
              tsx: 'TSX',
              css: 'CSS',
              html: 'HTML',
              python: 'Python',
              bash: 'Bash',
              json: 'JSON',
              sql: 'SQL'
            }
          }),
          diffSourcePlugin({ viewMode: 'rich-text' }),
          toolbarPlugin({
            toolbarContents: () => (
              <DiffSourceToggleWrapper>
                <UndoRedo />
                <BlockTypeSelect />
                <BoldItalicUnderlineToggles />
                <ListsToggle />
                <CreateLink />
                <InsertImage />
                <InsertTable />
                <InsertCodeBlock />
              </DiffSourceToggleWrapper>
            )
          })
        ]}
      />
    </div>
  );
};

export default BlogEditorInner;