// src/hooks/useAuth.ts
'use client';

import { createClient } from '@/lib/supabase';
import { User } from '@supabase/supabase-js';
import { useEffect, useMemo, useState, useCallback } from 'react';

interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: 'user' | 'admin';
  avatar_url?: string;
  created_at: string;
  updated_at: string;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Memoize client to prevent recreation on every render
  const supabase = useMemo(() => createClient(), []);

  useEffect(() => {
    let isMounted = true; // Prevent state updates after unmount

    const getUserAndProfile = async () => {
      // Add timeout to prevent infinite loading  
      const timeoutId = setTimeout(() => {
        if (isMounted) {
          console.warn('Auth check timed out');
          setLoading(false);
          // Don't set this as an error if we have a user - just continue without profile
          if (!user) {
            setError('Authentication check timed out');
          }
        }
      }, 3000); // Reduced to 3 second timeout

      try {
        const { data: { user }, error: authError } = await supabase.auth.getUser();
        
        clearTimeout(timeoutId);
        
        if (!isMounted) return; // Component unmounted, bail out
        
        if (authError) {
          console.error('Auth error:', authError);
          setError('Authentication error occurred');
          setLoading(false);
          return;
        }
        
        setUser(user);
        
        // Fetch user profile if user exists
        if (user) {
          const { data: profileData, error: profileError } = await supabase
            .from('user_profiles')
            .select('*')
            .eq('id', user.id)
            .single();
          
          if (!isMounted) return;
          
          if (profileError) {
            console.error('Profile fetch error:', profileError);
            // Don't set error for profile fetch - user might not have profile yet
          } else {
            setProfile(profileData);
          }
        } else {
          setProfile(null);
        }
        
        setLoading(false);
      } catch (err) {
        clearTimeout(timeoutId);
        if (!isMounted) return;
        console.error('Unexpected auth error:', err);
        setError('An unexpected error occurred');
        setLoading(false);
      }
    };

    getUserAndProfile();

    // Listen for auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (!isMounted) return;
      
      try {
        if (event === 'SIGNED_IN' && session) {
          setError(null);
          setUser(session.user);
          
          // Fetch profile for new user
          const { data: profileData, error: profileError } = await supabase
            .from('user_profiles')
            .select('*')
            .eq('id', session.user.id)
            .single();
          
          if (!isMounted) return;
          
          if (!profileError) {
            setProfile(profileData);
          }
        } else if (event === 'SIGNED_OUT') {
          setUser(null);
          setProfile(null);
          setError(null);
        }
      } catch (err) {
        console.error('Auth state change error:', err);
        setError('Authentication error occurred');
      }
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, [supabase]);

  const signOut = async () => {
    try {
      setError(null);
      const { error } = await supabase.auth.signOut();
      
      if (error) {
        console.error('Sign out error:', error);
        setError('Failed to sign out. Please try again.');
        return false;
      }
      
      return true;
    } catch (err) {
      console.error('Unexpected sign out error:', err);
      setError('An unexpected error occurred during sign out');
      return false;
    }
  };

  // Helper function to check if user is admin
  const isAdmin = profile?.role === 'admin';

  // Function to manually refresh profile data
  const refreshProfile = useCallback(async () => {
    if (!user) {
      console.warn('No user available for profile refresh');
      return;
    }
    
    console.log('Refreshing profile for user:', user.id);
    
    try {
      // Add a timeout to the profile query
      const profilePromise = supabase
        .from('user_profiles')
        .select('*')
        .eq('id', user.id)
        .single();
      
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Profile query timeout')), 3000)
      );
      
      const { data: profileData, error: profileError } = await Promise.race([
        profilePromise,
        timeoutPromise
      ]) as Awaited<typeof profilePromise>;
      
      if (!profileError && profileData) {
        console.log('Profile refreshed successfully:', profileData);
        setProfile(profileData);
        setError(null);
      } else if (profileError) {
        console.error('Profile refresh error:', profileError);
        if (profileError.code === 'PGRST116') {
          setError('Profile not found - please contact admin');
        } else {
          setError(`Database error: ${profileError.message}`);
        }
      }
    } catch (err: unknown) {
      console.error('Profile refresh error:', err);
      if (err instanceof Error && err.message === 'Profile query timeout') {
        setError('Profile query timed out - database may be slow');
      } else {
        setError(`Profile refresh failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
      }
    }
  }, [user, supabase]);

  return {
    user,
    profile,
    loading,
    error,
    isAdmin,
    supabase,
    signOut,
    refreshProfile,
    setError, // Allow manual error clearing
  };
}