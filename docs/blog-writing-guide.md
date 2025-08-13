# 블로그 글쓰기 가이드 (MDX)

이 가이드는 araverus 웹사이트의 새로운 MDX 기반 블로그 시스템 사용법을 설명합니다.

## 📁 파일 구조

```
content/blog/
├── my-post-slug/
│   └── index.mdx          # 블로그 포스트 내용
└── another-post/
    └── index.mdx

public/blog/
├── my-post-slug/
│   ├── cover.jpg          # 커버 이미지
│   ├── image1.jpg         # 본문 이미지들
│   └── diagram.png
└── another-post/
    └── cover.jpg
```

## ✍️ 새 포스트 작성하기

### 1. 폴더 생성
```bash
mkdir -p content/blog/my-new-post
mkdir -p public/blog/my-new-post
```

### 2. MDX 파일 작성
`content/blog/my-new-post/index.mdx` 파일을 생성하고 다음과 같이 시작:

```markdown
---
title: "포스트 제목"
date: "2025-08-13"
category: "Tutorial"
tags: ["react", "nextjs", "tutorial"]
draft: false
coverImage: "/blog/my-new-post/cover.jpg"
excerpt: "포스트 요약 설명 (최대 2-3줄)"
---

# 포스트 내용 시작

여기서부터 마크다운으로 작성합니다.
```

## 🏷️ Frontmatter 필드 설명

| 필드 | 필수 | 설명 | 예시 |
|------|------|------|------|
| `title` | ✅ | 포스트 제목 | "React 18 시작하기" |
| `date` | ✅ | 발행 날짜 (YYYY-MM-DD) | "2025-08-13" |
| `category` | ✅ | 카테고리 (아래 4개 중 선택) | "Tutorial" |
| `tags` | ❌ | 태그 배열 | ["react", "tutorial"] |
| `draft` | ❌ | 초안 여부 (기본값: false) | true |
| `coverImage` | ❌ | 커버 이미지 경로 | "/blog/post/cover.jpg" |
| `excerpt` | ❌ | 요약 (없으면 자동 생성) | "포스트 설명..." |

### 카테고리 옵션 (정확히 입력해야 함)
- `"Publication"` - 연구/논문/공식 발표
- `"Tutorial"` - 튜토리얼/가이드
- `"Insight"` - 인사이트/분석/경험
- `"Release"` - 릴리즈/업데이트 소식

## 🖼️ 이미지 사용법

### 커버 이미지
```markdown
# frontmatter에서
coverImage: "/blog/my-post/cover.jpg"
```

### 본문 이미지

**1. 기본 마크다운 (간단한 이미지)**
```markdown
![이미지 설명](/blog/my-post/image.jpg)
```

**2. Figure 컴포넌트 (추천)**
```markdown
<Figure 
  src="/blog/my-post/image.jpg" 
  alt="이미지 설명" 
  caption="이미지 캡션"
  width={800}
  height={400}
/>
```

**3. HTML 태그 (세밀한 제어)**
```markdown
<img src="/blog/my-post/image.jpg" alt="설명" width="600" style={{borderRadius: '8px'}} />
```

## 📝 마크다운 문법

### 헤딩
```markdown
# H1 제목
## H2 소제목
### H3 소소제목
```

### 텍스트 스타일
```markdown
**굵게** *기울임* `인라인 코드` ~~취소선~~
```

### 링크
```markdown
[외부 링크](https://example.com)
[내부 링크](/blog/other-post)
```

### 리스트
```markdown
- 순서 없는 리스트
- 항목 2

1. 순서 있는 리스트
2. 항목 2

- [ ] 체크리스트
- [x] 완료된 항목
```

### 인용문
```markdown
> "The best way to predict the future is to invent it."
> — Alan Kay
```

### 코드 블록
````markdown
```javascript
function hello(name) {
  return `Hello, ${name}!`;
}
```
````

### 표
```markdown
| 헤더1 | 헤더2 | 헤더3 |
|-------|-------|-------|
| 내용1 | 내용2 | 내용3 |
| 내용4 | 내용5 | 내용6 |
```

## 🎨 고급 기능

### 커스텀 React 컴포넌트
MDX에서는 React 컴포넌트를 직접 사용할 수 있습니다:

```markdown
<div className="bg-blue-50 p-4 rounded-lg">
  <h3 className="text-blue-900">주의사항</h3>
  <p>이것은 커스텀 스타일링된 박스입니다.</p>
</div>
```

### 구분선
```markdown
---
```

## 🔄 작성 워크플로우

### 1. 로컬 개발
```bash
# 개발 서버 시작
npm run dev

# 브라우저에서 확인
http://localhost:3000/blog/my-post-slug
```

### 2. 초안 작성
```markdown
---
draft: true  # 초안으로 설정
---
```
- 개발 환경에서는 보임
- 프로덕션에서는 숨겨짐

### 3. 발행
```markdown
---
draft: false  # 또는 필드 제거
---
```

### 4. Git 커밋
```bash
git add content/blog/my-post/ public/blog/my-post/
git commit -m "feat(blog): add new post about React"
git push
```

## 🏃‍♂️ 빠른 시작 템플릿

새 포스트를 위한 템플릿:

```bash
# 폴더 생성
mkdir -p content/blog/react-hooks-guide
mkdir -p public/blog/react-hooks-guide

# 기본 템플릿 복사
cat > content/blog/react-hooks-guide/index.mdx << 'EOF'
---
title: "React Hooks 완전 가이드"
date: "2025-08-13"
category: "Tutorial"
tags: ["react", "hooks", "frontend"]
draft: true
coverImage: "/blog/react-hooks-guide/cover.jpg"
excerpt: "React Hooks를 처음부터 마스터하는 완전 가이드"
---

# React Hooks 완전 가이드

React Hooks에 대해 알아보겠습니다.

## useState 사용법

기본적인 상태 관리:

```javascript
import { useState } from 'react';

function Counter() {
  const [count, setCount] = useState(0);
  
  return (
    <div>
      <p>Count: {count}</p>
      <button onClick={() => setCount(count + 1)}>
        증가
      </button>
    </div>
  );
}
```

<Figure 
  src="/blog/react-hooks-guide/useState-example.png" 
  caption="useState 예시 스크린샷"
/>

## 결론

React Hooks는 함수형 컴포넌트에서 상태와 생명주기를 관리할 수 있게 해주는 강력한 기능입니다.
EOF
```

## 🎯 SEO 최적화 팁

1. **제목**: 명확하고 검색 친화적으로
2. **excerpt**: 2-3줄로 핵심 내용 요약
3. **tags**: 관련 키워드 3-5개
4. **이미지**: alt 텍스트 필수 입력
5. **내부 링크**: 다른 포스트 연결

## ⚠️ 주의사항

1. **파일명**: 영문, 소문자, 하이픈 사용 (예: `my-blog-post`)
2. **이미지**: WebP, JPEG, PNG 권장 (최대 1MB)
3. **카테고리**: 정확한 대소문자 입력 필수
4. **날짜 형식**: YYYY-MM-DD 형식 엄수
5. **draft**: 발행 전 false로 변경 필수

## 🔧 문제 해결

### 포스트가 보이지 않을 때
1. frontmatter 형식 확인
2. draft가 false인지 확인
3. 날짜 형식 확인
4. 브라우저 새로고침

### 이미지가 보이지 않을 때
1. 파일 경로 확인 (`/blog/slug/image.jpg`)
2. 이미지 파일 존재 여부 확인
3. 파일명 대소문자 확인

### 개발 서버 재시작
```bash
# 캐시 삭제 후 재시작
rm -rf .next
npm run dev
```

## 📞 도움이 필요하면

- 기술 이슈: GitHub Issues
- 가이드 업데이트 요청: 개발팀 문의

---

**Happy Writing! ✨**