import RelatedSection from './RelatedSection'
import type { RelatedArticle } from '@/lib/news-service'

interface MoreLikeThisSectionProps {
  articles: RelatedArticle[]
}

export default function MoreLikeThisSection({ articles }: MoreLikeThisSectionProps) {
  return <RelatedSection title="More Like This" articles={articles} />
}
