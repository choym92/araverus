# Command: New Post Scaffold
# Usage: /new-post <slug>
# Goal: Create a standard MDX post skeleton (content + public assets).

## Ground Rules
- Write minimal standard files; don't overwrite existing posts.
- Paths:
  - content/blog/<slug>/index.mdx
  - public/blog/<slug>/ (create folder + .keep)
- Frontmatter defaults:
  - title = Title Case from slug (e.g., "my-new-post" → "My New Post")
  - date = today (YYYY-MM-DD)
  - tags = []
  - category = "Publication"
  - draft = true
  - coverImage = "/blog/<slug>/cover.jpg"

## Steps
1) Validate $ARGUMENTS is a slug (a-z0-9-hyphen). If missing/invalid → stop with help text.
2) Check existence: `content/blog/<slug>/index.mdx`. If exists → stop (no overwrite).
3) Create folders:
   - `content/blog/<slug>/`
   - `public/blog/<slug>/` (also create an empty `.keep` so Git tracks it)
4) Generate `index.mdx` with the template below (fill slug, date, title).
5) Print next steps and changed files list.

## Template: content/blog/<slug>/index.mdx
```mdx
---
title: "%%TITLE%%"
date: "%%DATE%%"
tags: []
category: "Publication"
draft: true
coverImage: "/blog/%%SLUG%%/cover.jpg"
excerpt: "포스트 설명을 여기에 작성하세요"
---

# %%TITLE%%

여기에 본문을 작성하세요.  
이미지는 `public/blog/%%SLUG%%/` 폴더에 넣고, 본문에서는 `/blog/%%SLUG%%/파일명` 로 참조하세요.

## 섹션 예시

일반 텍스트와 **굵은 글씨**, *기울임* 등을 사용할 수 있습니다.

### 코드 블록
```javascript
function example() {
  console.log("Hello, World!");
}
```

### 이미지 삽입
<Figure 
  src="/blog/%%SLUG%%/example.jpg" 
  alt="예시 이미지" 
  caption="이미지 설명"
/>

## 결론

포스트 내용을 완성하고 frontmatter에서 `draft: false`로 변경하여 발행하세요.
```

## Output Contract
- Print created paths.
- Do NOT dump entire file content; show a short preview (first ~10 lines).
- Stop for Approve if any conflict is detected.

## Rollback
```bash
git restore -SW content/blog/<slug>/ public/blog/<slug>/
```