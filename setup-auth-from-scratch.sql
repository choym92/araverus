-- Complete Auth Setup from Scratch
-- Run this in your Supabase SQL Editor

-- 1. Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Create user_profiles table
CREATE TABLE IF NOT EXISTS user_profiles (
  id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  email TEXT,
  full_name TEXT,
  role TEXT DEFAULT 'user' CHECK (role IN ('user', 'admin')),
  avatar_url TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Enable RLS
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- 4. Simple RLS policy - users can see their own profile
DROP POLICY IF EXISTS "Users can view their own profile" ON user_profiles;
CREATE POLICY "Users can view their own profile" ON user_profiles
  FOR SELECT USING (auth.uid() = id);

-- 5. Allow profile creation
DROP POLICY IF EXISTS "Allow profile creation" ON user_profiles;
CREATE POLICY "Allow profile creation" ON user_profiles
  FOR INSERT WITH CHECK (auth.uid() = id);

-- 6. Allow profile updates
DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
CREATE POLICY "Users can update own profile" ON user_profiles
  FOR UPDATE USING (auth.uid() = id);

-- 7. Create trigger function for new users
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.user_profiles (id, email, full_name)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1))
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 8. Create trigger
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 9. Check current auth users (run this to see if you already have a user)
SELECT id, email, created_at FROM auth.users WHERE email = 'choym92@gmail.com';

-- 10. If the above query returns a user ID, run this to make them admin:
-- INSERT INTO user_profiles (id, email, role, full_name) 
-- SELECT id, 'choym92@gmail.com', 'admin', 'Paul Cho'
-- FROM auth.users 
-- WHERE email = 'choym92@gmail.com'
-- ON CONFLICT (id) DO UPDATE SET role = 'admin';