'use client'

import { useState } from 'react'
import Image from 'next/image'

interface ArticleHeroImageProps {
  src: string
  alt: string
}

export default function ArticleHeroImage({ src, alt }: ArticleHeroImageProps) {
  const [error, setError] = useState(false)

  if (error) return null

  return (
    <div className="relative w-full aspect-[2/1] bg-neutral-100 rounded-lg overflow-hidden mb-6">
      <Image
        src={src}
        alt={alt}
        fill
        className="object-cover"
        sizes="(max-width: 768px) 100vw, 800px"
        unoptimized
        onError={() => setError(true)}
      />
    </div>
  )
}
