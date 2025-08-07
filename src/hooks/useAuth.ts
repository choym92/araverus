// src/hooks/useAuth.ts
'use client';

import { createClient } from '@/lib/supabase';
import { User } from '@supabase/supabase-js';
import { useEffect, useMemo, useState } from 'react';

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Memoize client to prevent recreation on every render
  const supabase = useMemo(() => createClient(), []);

  useEffect(() => {
    let isMounted = true; // Prevent state updates after unmount

    const getUser = async () => {
      try {
        const { data: { user }, error } = await supabase.auth.getUser();
        
        if (!isMounted) return; // Component unmounted, bail out
        
        if (error) {
          console.error('Auth error:', error);
          setError('Authentication error occurred');
          setLoading(false);
          return;
        }
        
        setUser(user);
        setLoading(false);
      } catch (err) {
        if (!isMounted) return;
        console.error('Unexpected auth error:', err);
        setError('An unexpected error occurred');
        setLoading(false);
      }
    };

    getUser();

    // Listen for auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (!isMounted) return;
      
      try {
        if (event === 'SIGNED_IN' && session) {
          setError(null);
          setUser(session.user);
        } else if (event === 'SIGNED_OUT') {
          setUser(null);
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

  return {
    user,
    loading,
    error,
    supabase,
    signOut,
    setError, // Allow manual error clearing
  };
}