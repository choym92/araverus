-- Make choym92@gmail.com an admin RIGHT NOW
-- Run this in Supabase SQL Editor

-- Create or update your profile with admin role
INSERT INTO user_profiles (id, email, role, full_name) 
VALUES (
  '181a4c4e-80c8-42a5-9f12-6e10c1ae5d0e',  -- Your actual user ID
  'choym92@gmail.com',
  'admin',
  'Paul Cho'
) 
ON CONFLICT (id) DO UPDATE SET 
  role = 'admin',
  email = 'choym92@gmail.com',
  full_name = 'Paul Cho';

-- Verify it worked
SELECT * FROM user_profiles WHERE id = '181a4c4e-80c8-42a5-9f12-6e10c1ae5d0e';