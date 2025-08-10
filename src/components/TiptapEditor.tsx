'use client';

import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Image from '@tiptap/extension-image';
import Link from '@tiptap/extension-link';
import { 
  Bold, 
  Italic, 
  List, 
  ListOrdered, 
  Quote, 
  Redo, 
  Undo, 
  Code,
  Link as LinkIcon,
  Image as ImageIcon,
} from 'lucide-react';
import { useCallback } from 'react';

interface TiptapEditorProps {
  content: string;
  onChange: (content: string) => void;
  onImageUpload?: (file: File) => Promise<string>;
}

export default function TiptapEditor({ content, onChange, onImageUpload }: TiptapEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3]
        },
        code: {
          HTMLAttributes: {
            class: 'bg-gray-100 px-1 py-0.5 rounded text-sm font-mono'
          }
        },
        codeBlock: {
          HTMLAttributes: {
            class: 'bg-gray-100 rounded-lg p-4 my-4 font-mono text-sm'
          }
        },
        blockquote: {
          HTMLAttributes: {
            class: 'border-l-4 border-gray-300 pl-4 my-4 italic text-gray-600'
          }
        }
      }),
      Image.configure({
        HTMLAttributes: {
          class: 'max-w-full h-auto rounded-lg my-4'
        }
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-blue-600 hover:text-blue-700 underline cursor-pointer'
        }
      })
    ],
    content,
    editorProps: {
      attributes: {
        class: 'prose prose-lg max-w-none focus:outline-none min-h-[400px] px-6 py-4 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0'
      }
    },
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML());
    }
  });

  const addImage = useCallback(() => {
    const url = window.prompt('Enter image URL:');
    if (url && editor) {
      editor.chain().focus().setImage({ src: url }).run();
    }
  }, [editor]);

  const handleImageUpload = useCallback(async () => {
    if (!onImageUpload || !editor) return;

    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        try {
          const url = await onImageUpload(file);
          editor.chain().focus().setImage({ src: url }).run();
        } catch (error) {
          console.error('Failed to upload image:', error);
        }
      }
    };
    input.click();
  }, [editor, onImageUpload]);

  const setLink = useCallback(() => {
    if (!editor) return;
    
    const previousUrl = editor.getAttributes('link').href;
    const url = window.prompt('Enter URL:', previousUrl);

    if (url === null) return;

    if (url === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }

    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
  }, [editor]);

  if (!editor) {
    return (
      <div className="flex items-center justify-center h-[400px] bg-white rounded-lg border border-gray-200">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-400"></div>
      </div>
    );
  }

  const ToolButton = ({ 
    onClick, 
    isActive = false, 
    disabled = false, 
    children, 
    title 
  }: { 
    onClick: () => void; 
    isActive?: boolean; 
    disabled?: boolean; 
    children: React.ReactNode; 
    title: string;
  }) => (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        p-2 rounded-md transition-all
        ${isActive 
          ? 'bg-gray-100 text-gray-900' 
          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
        }
        ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
      `}
      title={title}
    >
      {children}
    </button>
  );

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      {/* Minimal Toolbar */}
      <div className="border-b border-gray-200 bg-white px-4 py-2">
        <div className="flex items-center gap-1">
          {/* Headings Dropdown */}
          <select
            onChange={(e) => {
              const level = e.target.value;
              if (level === 'p') {
                editor.chain().focus().setParagraph().run();
              } else {
                editor.chain().focus().toggleHeading({ level: parseInt(level) as 1 | 2 | 3 }).run();
              }
            }}
            value={
              editor.isActive('heading', { level: 1 }) ? '1' :
              editor.isActive('heading', { level: 2 }) ? '2' :
              editor.isActive('heading', { level: 3 }) ? '3' : 'p'
            }
            className="px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="p">Normal</option>
            <option value="1">Heading 1</option>
            <option value="2">Heading 2</option>
            <option value="3">Heading 3</option>
          </select>

          <div className="w-px h-6 bg-gray-200 mx-1" />

          {/* Text Formatting */}
          <ToolButton
            onClick={() => editor.chain().focus().toggleBold().run()}
            isActive={editor.isActive('bold')}
            title="Bold (Cmd+B)"
          >
            <Bold size={18} strokeWidth={2} />
          </ToolButton>

          <ToolButton
            onClick={() => editor.chain().focus().toggleItalic().run()}
            isActive={editor.isActive('italic')}
            title="Italic (Cmd+I)"
          >
            <Italic size={18} strokeWidth={2} />
          </ToolButton>

          <ToolButton
            onClick={() => editor.chain().focus().toggleCode().run()}
            isActive={editor.isActive('code')}
            title="Code"
          >
            <Code size={18} strokeWidth={2} />
          </ToolButton>

          <div className="w-px h-6 bg-gray-200 mx-1" />

          {/* Lists */}
          <ToolButton
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            isActive={editor.isActive('bulletList')}
            title="Bullet List"
          >
            <List size={18} strokeWidth={2} />
          </ToolButton>

          <ToolButton
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            isActive={editor.isActive('orderedList')}
            title="Numbered List"
          >
            <ListOrdered size={18} strokeWidth={2} />
          </ToolButton>

          <ToolButton
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            isActive={editor.isActive('blockquote')}
            title="Quote"
          >
            <Quote size={18} strokeWidth={2} />
          </ToolButton>

          <div className="w-px h-6 bg-gray-200 mx-1" />

          {/* Links & Images */}
          <ToolButton
            onClick={setLink}
            isActive={editor.isActive('link')}
            title="Add Link"
          >
            <LinkIcon size={18} strokeWidth={2} />
          </ToolButton>

          {onImageUpload ? (
            <ToolButton
              onClick={handleImageUpload}
              title="Upload Image"
            >
              <ImageIcon size={18} strokeWidth={2} />
            </ToolButton>
          ) : (
            <ToolButton
              onClick={addImage}
              title="Add Image URL"
            >
              <ImageIcon size={18} strokeWidth={2} />
            </ToolButton>
          )}

          <div className="ml-auto flex items-center gap-1">
            <div className="w-px h-6 bg-gray-200 mx-1" />
            
            {/* History */}
            <ToolButton
              onClick={() => editor.chain().focus().undo().run()}
              disabled={!editor.can().undo()}
              title="Undo (Cmd+Z)"
            >
              <Undo size={18} strokeWidth={2} />
            </ToolButton>

            <ToolButton
              onClick={() => editor.chain().focus().redo().run()}
              disabled={!editor.can().redo()}
              title="Redo (Cmd+Shift+Z)"
            >
              <Redo size={18} strokeWidth={2} />
            </ToolButton>
          </div>
        </div>
      </div>

      {/* Editor Content */}
      <div className="bg-white min-h-[400px] cursor-text" onClick={() => editor?.chain().focus().run()}>
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}