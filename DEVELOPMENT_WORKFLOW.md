# Development Workflow Guide

## 🏗️ Environment Setup

### Current Setup (Temporary - Single Supabase Project)
We're currently using ONE Supabase project for all environments. This guide will help you work more efficiently until we set up separate projects.

### Environment Files
- `.env.local` - Your local development (git-ignored)
- `.env.development` - Shared development settings
- `.env.production` - Production settings (for chopaul.com)
- `.env.example` - Template for other developers

## 🔄 Recommended Workflow

### 1. Feature Development (Local)
```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Work locally
npm run dev

# Test with local Supabase
# Auth callbacks will redirect to http://localhost:3000
```

### 2. Preview Deployment (Automatic)
```bash
# Push your branch
git push origin feature/your-feature-name

# Vercel automatically creates a preview deployment
# URL: https://araverus-[branch-name]-[project].vercel.app
```

### 3. Testing on Preview
- Vercel preview deployments use the development Supabase project
- Auth callbacks work with dynamic URLs (no configuration needed)
- Share preview URL with team for feedback

### 4. Merge to Main
```bash
# After approval, merge via GitHub PR
git checkout main
git pull origin main
git merge feature/your-feature-name
git push origin main

# Vercel automatically deploys to chopaul.com
```

## 🚀 Branch Strategy

### Branches
- `main` → Production (chopaul.com)
- `develop` → Staging (optional)
- `feature/*` → Feature branches
- `hotfix/*` → Emergency fixes

### Never Do This
❌ Don't commit directly to main
❌ Don't test Supabase features directly in production
❌ Don't use production credentials locally

### Always Do This
✅ Create feature branches for new work
✅ Test on preview deployments before merging
✅ Use pull requests for code review

## 🔐 Supabase Configuration

### Current Redirect URLs (in your Supabase dashboard)
Keep these for now (until we separate projects):
- `http://localhost:3000/**`
- `https://localhost:3000/**`
- `https://araverus-*.vercel.app/**`
- `https://www.chopaul.com/**`
- `https://chopaul.com/**`

### Future Setup (Recommended)
1. **Development Supabase Project**
   - Redirect URLs: localhost + Vercel previews
   - Test data only

2. **Production Supabase Project**
   - Redirect URLs: chopaul.com only
   - Real user data

## 🛠️ Useful Commands

```bash
# Local development
npm run dev

# Build check (before pushing)
npm run build
npm run lint

# Preview deployment (automatic on push)
git push origin your-branch

# Check which environment you're in
# Add this to any page for debugging:
console.log('Environment:', process.env.NODE_ENV)
console.log('Base URL:', process.env.NEXT_PUBLIC_BASE_URL)
```

## 📝 Environment Variables in Vercel

### For Preview Deployments
In Vercel dashboard → Settings → Environment Variables:
- Set variables for "Preview" environment
- Use development Supabase credentials

### For Production
In Vercel dashboard → Settings → Environment Variables:
- Set variables for "Production" environment only
- Use production Supabase credentials (when you create them)

## 🔍 Debugging Tips

1. **Check current environment:**
   ```javascript
   import { getEnvironment } from '@/lib/config/environment';
   console.log('Current env:', getEnvironment());
   ```

2. **Auth redirect issues:**
   - Check Supabase dashboard → Authentication → Redirect URLs
   - Ensure your current URL is whitelisted

3. **Preview deployment not working:**
   - Check Vercel dashboard for build logs
   - Ensure environment variables are set for "Preview"

## 📅 Migration Timeline

### Phase 1 (Current) ✅
- Single Supabase project
- Manual environment management
- Basic branch protection

### Phase 2 (Next Week)
- [ ] Create production Supabase project
- [ ] Migrate production data
- [ ] Update production env vars in Vercel

### Phase 3 (Future)
- [ ] Add staging environment
- [ ] Implement database migrations
- [ ] Add CI/CD pipeline with testing

## ⚠️ Important Notes

1. **Until we separate Supabase projects**, be careful with:
   - Deleting data (affects all environments)
   - Schema changes (affects production)
   - User management (real users mixed with test users)

2. **Always test auth flows on preview deployments** before merging to main

3. **For database changes**, create migration scripts don't modify directly in Supabase dashboard

---

Last Updated: 2025-08-11
Next Review: When production Supabase project is created