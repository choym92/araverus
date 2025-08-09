'use client';

import { createClient } from '@/lib/supabase';
import { User } from '@supabase/supabase-js';
import { useEffect, useMemo, useState, useCallback } from 'react';

// Create client singleton to prevent unnecessary recreations
let supabaseClientInstance: ReturnType<typeof createClient> | null = null;

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const supabase = useMemo(() => {
    if (!supabaseClientInstance) {
      supabaseClientInstance = createClient();
    }
    return supabaseClientInstance;
  }, []);

  useEffect(() => {
    let mounted = true;

    const getUser = async () => {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (mounted) {
          setUser(user);
          setLoading(false);
        }
      } catch (error) {
        console.error('Auth error:', error);
        if (mounted) {
          setLoading(false);
        }
      }
    };

    getUser();

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, session) => {
        if (mounted) {
          setUser(session?.user ?? null);
          setLoading(false);
        }
      }
    );

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, [supabase]);

  const signOut = useCallback(async () => {
    try {
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
      return true;
    } catch (error) {
      console.error('Sign out error:', error);
      return false;
    }
  }, [supabase]);

  return useMemo(() => ({
    user,
    loading,
    supabase,
    signOut,
  }), [user, loading, supabase, signOut]);
}