import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase';

// POST /api/admin/setup - Set up admin profile
export async function POST(request: NextRequest) {
  try {
    const supabase = createClient();
    
    // Get current user
    const { data: { user }, error: userError } = await supabase.auth.getUser();
    
    if (userError || !user) {
      return NextResponse.json(
        { error: 'Not authenticated' },
        { status: 401 }
      );
    }
    
    // Only allow specific admin email
    if (user.email !== 'choym92@gmail.com') {
      return NextResponse.json(
        { error: 'Not authorized' },
        { status: 403 }
      );
    }
    
    // Create or update admin profile
    const { error: profileError } = await supabase
      .from('user_profiles')
      .upsert({
        id: user.id,
        email: user.email,
        role: 'admin',
        full_name: user.user_metadata?.full_name || user.email?.split('@')[0] || 'Admin',
        avatar_url: user.user_metadata?.avatar_url || user.user_metadata?.picture,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }, {
        onConflict: 'id'
      });
    
    if (profileError) {
      console.error('Profile error:', profileError);
      
      // Try update only if insert failed
      const { error: updateError } = await supabase
        .from('user_profiles')
        .update({
          role: 'admin',
          updated_at: new Date().toISOString()
        })
        .eq('id', user.id);
      
      if (updateError) {
        return NextResponse.json(
          { error: 'Failed to set up admin profile', details: updateError },
          { status: 500 }
        );
      }
    }
    
    return NextResponse.json({ 
      success: true,
      message: 'Admin profile set up successfully'
    });
  } catch (error) {
    console.error('Setup error:', error);
    return NextResponse.json(
      { error: 'Failed to set up admin' },
      { status: 500 }
    );
  }
}