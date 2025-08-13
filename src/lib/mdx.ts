import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';

const BLOG_DIR = path.join(process.cwd(), 'content', 'blog');

export interface PostFrontmatter {
  title: string;
  date: string;
  category: 'Publication' | 'Insight' | 'Release' | 'Tutorial';
  tags?: string[];
  draft?: boolean;
  coverImage?: string;
  excerpt?: string;
}

export interface Post {
  slug: string;
  frontmatter: PostFrontmatter;
  content: string;
}

// Get all posts, optionally filtered by category
export async function getAllPosts(category?: string): Promise<Post[]> {
  // Create blog directory if it doesn't exist
  if (!fs.existsSync(BLOG_DIR)) {
    fs.mkdirSync(BLOG_DIR, { recursive: true });
    return [];
  }

  const slugs = fs.readdirSync(BLOG_DIR);
  const posts = slugs
    .map((slug) => {
      const postPath = path.join(BLOG_DIR, slug, 'index.mdx');
      
      // Skip if index.mdx doesn't exist
      if (!fs.existsSync(postPath)) {
        return null;
      }

      const fileContents = fs.readFileSync(postPath, 'utf8');
      const { data, content } = matter(fileContents);

      return {
        slug,
        frontmatter: data as PostFrontmatter,
        content,
      };
    })
    .filter((post): post is Post => post !== null)
    // Filter out drafts in production
    .filter((post) => {
      if (process.env.NODE_ENV === 'production' && post.frontmatter.draft) {
        return false;
      }
      return true;
    })
    // Filter by category if specified
    .filter((post) => {
      if (category && post.frontmatter.category !== category) {
        return false;
      }
      return true;
    })
    // Sort by date descending
    .sort((a, b) => {
      return new Date(b.frontmatter.date).getTime() - new Date(a.frontmatter.date).getTime();
    });

  return posts;
}

// Get a single post by slug
export async function getPostBySlug(slug: string): Promise<Post | null> {
  const postPath = path.join(BLOG_DIR, slug, 'index.mdx');

  if (!fs.existsSync(postPath)) {
    return null;
  }

  const fileContents = fs.readFileSync(postPath, 'utf8');
  const { data, content } = matter(fileContents);

  const post: Post = {
    slug,
    frontmatter: data as PostFrontmatter,
    content,
  };

  // Return null for drafts in production
  if (process.env.NODE_ENV === 'production' && post.frontmatter.draft) {
    return null;
  }

  return post;
}

// Get all unique categories from posts
export async function getCategories(): Promise<string[]> {
  const posts = await getAllPosts();
  const categories = new Set(posts.map((post) => post.frontmatter.category));
  return Array.from(categories).sort();
}

// Get all post slugs for static generation
export async function getAllPostSlugs(): Promise<string[]> {
  if (!fs.existsSync(BLOG_DIR)) {
    return [];
  }

  const slugs = fs.readdirSync(BLOG_DIR);
  return slugs.filter((slug) => {
    const postPath = path.join(BLOG_DIR, slug, 'index.mdx');
    return fs.existsSync(postPath);
  });
}