-- Fix Profile RLS Policy to Allow Self-Access
-- Run this in your Supabase SQL Editor

-- Drop existing problematic policies
DROP POLICY IF EXISTS "Users can view all profiles" ON user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;

-- Create new policy that allows users to see their own profile
CREATE POLICY "Users can view their own profile" ON user_profiles
  FOR SELECT USING (auth.uid() = id);

-- Allow users to update their own profile
CREATE POLICY "Users can update own profile" ON user_profiles
  FOR UPDATE USING (auth.uid() = id);

-- Allow admins to view all profiles (but this won't block self-access)
CREATE POLICY "Admins can view all profiles" ON user_profiles
  FOR SELECT USING (
    role = 'admin' AND auth.uid() = id
  );

-- Critical: Allow profile creation on signup (for the trigger)
CREATE POLICY "Allow profile creation on signup" ON user_profiles
  FOR INSERT WITH CHECK (auth.uid() = id);

-- Ensure your admin profile exists
-- Replace YOUR_USER_ID with your actual auth.users.id from Google OAuth
INSERT INTO user_profiles (id, email, role, full_name) 
VALUES (
  'YOUR_USER_ID_HERE',  -- You'll need to get this from auth.users table
  'choym92@gmail.com',
  'admin',
  'Paul Cho'
) 
ON CONFLICT (id) DO UPDATE SET 
  role = 'admin',
  email = 'choym92@gmail.com';