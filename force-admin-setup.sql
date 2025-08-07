-- Force Admin Setup - Run this in Supabase SQL Editor
-- This will work regardless of OAuth flow issues

-- First, let's see what users exist
SELECT id, email, created_at FROM auth.users WHERE email = 'choym92@gmail.com';

-- Create/update your profile as admin (this will work even if profile doesn't exist)
INSERT INTO user_profiles (id, email, role, full_name) 
SELECT 
  au.id,
  'choym92@gmail.com',
  'admin',
  'Paul Cho'
FROM auth.users au 
WHERE au.email = 'choym92@gmail.com'
ON CONFLICT (id) DO UPDATE SET 
  role = 'admin',
  email = 'choym92@gmail.com',
  full_name = 'Paul Cho';

-- Verify the admin was created
SELECT * FROM user_profiles WHERE email = 'choym92@gmail.com';