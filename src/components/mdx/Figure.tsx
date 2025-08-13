import Image from 'next/image';

interface FigureProps {
  src: string;
  alt?: string;
  caption?: string;
  width?: number;
  height?: number;
}

export function Figure({ 
  src, 
  alt = '', 
  caption, 
  width = 800, 
  height = 400 
}: FigureProps) {
  return (
    <figure className="my-8">
      <div className="relative overflow-hidden rounded-lg">
        <Image
          src={src}
          alt={alt || caption || ''}
          width={width}
          height={height}
          className="w-full h-auto"
          style={{ objectFit: 'cover' }}
        />
      </div>
      {caption && (
        <figcaption className="mt-2 text-center text-sm text-gray-600 dark:text-gray-400">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}