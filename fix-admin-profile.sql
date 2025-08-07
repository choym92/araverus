-- Fix admin profile for Paul Cho (choym92@gmail.com)
-- User ID: 181a4c4e-80c8-42a5-9f12-6e10c1ae5d0e

-- First, check if the profile already exists
SELECT * FROM user_profiles WHERE id = '181a4c4e-80c8-42a5-9f12-6e10c1ae5d0e';

-- Insert the profile record (this will create the missing profile)
INSERT INTO user_profiles (id, email, full_name, role)
VALUES (
  '181a4c4e-80c8-42a5-9f12-6e10c1ae5d0e',
  'choym92@gmail.com',
  'Paul Cho',
  'admin'
)
ON CONFLICT (id) 
DO UPDATE SET 
  role = 'admin',
  email = 'choym92@gmail.com',
  full_name = 'Paul Cho',
  updated_at = NOW();

-- Verify the profile was created/updated
SELECT 
  id,
  email,
  full_name,
  role,
  created_at,
  updated_at
FROM user_profiles 
WHERE id = '181a4c4e-80c8-42a5-9f12-6e10c1ae5d0e';

-- Also verify from the auth.users perspective
SELECT 
  u.id,
  u.email,
  u.created_at as user_created,
  p.role,
  p.full_name,
  p.created_at as profile_created
FROM auth.users u
LEFT JOIN user_profiles p ON u.id = p.id
WHERE u.id = '181a4c4e-80c8-42a5-9f12-6e10c1ae5d0e';