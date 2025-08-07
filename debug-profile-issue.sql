-- Debug profile access issue
-- Run this to check what's going wrong

-- 1. Check if profile exists
SELECT 'Profile exists check' as test, * FROM user_profiles 
WHERE id = '181a4c4e-80c8-42a5-9f12-6e10c1ae5d0e';

-- 2. Check if RLS is enabled
SELECT 'RLS status' as test, schemaname, tablename, rowsecurity 
FROM pg_tables 
WHERE tablename = 'user_profiles';

-- 3. Check RLS policies
SELECT 'RLS policies' as test, schemaname, tablename, policyname, permissive, roles, cmd, qual
FROM pg_policies 
WHERE tablename = 'user_profiles';

-- 4. Test direct access (this might be blocked by RLS)
SELECT 'Direct access test' as test, count(*) 
FROM user_profiles;

-- 5. Try the exact query the app would use
SELECT 'App query test' as test, id, email, full_name, role, created_at
FROM user_profiles 
WHERE id = '181a4c4e-80c8-42a5-9f12-6e10c1ae5d0e';

-- 6. Check if the user is properly authenticated in this context
SELECT 'Auth context' as test, 
  current_user as current_user,
  session_user as session_user,
  auth.uid() as auth_uid,
  auth.jwt() as auth_jwt;

-- TEMPORARY FIX: If RLS is blocking, temporarily disable it
-- (Run this only if the above queries show RLS is the issue)
-- ALTER TABLE user_profiles DISABLE ROW LEVEL SECURITY;

-- Then test this query
-- SELECT 'Test after disable RLS' as test, * FROM user_profiles 
-- WHERE id = '181a4c4e-80c8-42a5-9f12-6e10c1ae5d0e';

-- Re-enable RLS after testing (IMPORTANT!)
-- ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;