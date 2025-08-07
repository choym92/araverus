-- Verify the profile exists and has admin role
-- Run this to double-check everything is set up correctly

-- Check if user exists in auth.users
SELECT 
  'User in auth.users' as check_type,
  id,
  email,
  created_at
FROM auth.users 
WHERE email = 'choym92@gmail.com';

-- Check if profile exists in user_profiles
SELECT 
  'Profile in user_profiles' as check_type,
  id,
  email,
  full_name,
  role,
  created_at
FROM user_profiles 
WHERE email = 'choym92@gmail.com';

-- Check the specific user ID profile
SELECT 
  'Profile by user ID' as check_type,
  id,
  email,
  full_name,
  role,
  created_at
FROM user_profiles 
WHERE id = '181a4c4e-80c8-42a5-9f12-6e10c1ae5d0e';

-- Join query to see both tables together
SELECT 
  u.id as user_id,
  u.email as user_email,
  u.created_at as user_created,
  p.id as profile_id,
  p.email as profile_email,
  p.full_name,
  p.role,
  p.created_at as profile_created,
  CASE 
    WHEN p.id IS NULL THEN 'NO PROFILE FOUND' 
    WHEN p.role = 'admin' THEN 'ADMIN ACCESS OK'
    ELSE 'NOT ADMIN'
  END as status
FROM auth.users u
LEFT JOIN user_profiles p ON u.id = p.id
WHERE u.email = 'choym92@gmail.com';