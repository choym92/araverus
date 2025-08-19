import { createClient } from '@/lib/supabase-server'
import StockDashboard from './StockDashboard'

export default async function FinancePage() {
  const supabase = await createClient()
  
  // Fetch latest signals
  const { data: signals } = await supabase
    .from('trading_signals')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(20)
  
  // Fetch recent stock prices
  const { data: prices } = await supabase
    .from('stock_prices')
    .select('*')
    .order('date', { ascending: false })
    .limit(100)
  
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Finance Dashboard</h1>
      <StockDashboard signals={signals || []} prices={prices || []} />
    </div>
  )
}