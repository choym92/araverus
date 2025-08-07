-- Set choym92@gmail.com as admin
-- Run this in Supabase SQL Editor after you've logged in at least once

-- First, check if the user exists
SELECT * FROM auth.users WHERE email = 'choym92@gmail.com';

-- If the user exists, update their profile to admin
UPDATE user_profiles 
SET role = 'admin' 
WHERE email = 'choym92@gmail.com';

-- Verify the update
SELECT * FROM user_profiles WHERE email = 'choym92@gmail.com';

-- Alternative: If user_profiles doesn't have the user yet, insert them
-- This will only work if the user has already signed up through Supabase Auth
INSERT INTO user_profiles (id, email, full_name, role)
SELECT 
  id,
  email,
  COALESCE(raw_user_meta_data->>'full_name', 'Paul Cho'),
  'admin'
FROM auth.users 
WHERE email = 'choym92@gmail.com'
ON CONFLICT (id) 
DO UPDATE SET role = 'admin';

-- Final verification
SELECT 
  u.email,
  u.created_at as user_created,
  p.role,
  p.full_name
FROM auth.users u
LEFT JOIN user_profiles p ON u.id = p.id
WHERE u.email = 'choym92@gmail.com';