'use client'

import { useState } from 'react'
import { TrendingUp, TrendingDown, AlertCircle } from 'lucide-react'

interface Signal {
  id: number
  symbol: string
  signal_type: string
  indicator: string
  value: number
  price: number
  timestamp: string
  created_at: string
}

interface StockPrice {
  id: number
  symbol: string
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface StockDashboardProps {
  signals: Signal[]
  prices: StockPrice[]
}

export default function StockDashboard({ signals, prices }: StockDashboardProps) {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)
  
  // Group prices by symbol
  const pricesBySymbol = prices.reduce((acc, price) => {
    if (!acc[price.symbol]) acc[price.symbol] = []
    acc[price.symbol].push(price)
    return acc
  }, {} as Record<string, StockPrice[]>)
  
  // Get unique symbols
  const symbols = Array.from(new Set([...signals.map(s => s.symbol), ...prices.map(p => p.symbol)]))
  
  const getSignalIcon = (type: string) => {
    switch(type) {
      case 'BUY':
        return <TrendingUp className="w-5 h-5 text-green-500" />
      case 'SELL':
        return <TrendingDown className="w-5 h-5 text-red-500" />
      default:
        return <AlertCircle className="w-5 h-5 text-yellow-500" />
    }
  }
  
  const getSignalColor = (type: string) => {
    switch(type) {
      case 'BUY':
        return 'bg-green-50 border-green-200'
      case 'SELL':
        return 'bg-red-50 border-red-200'
      default:
        return 'bg-yellow-50 border-yellow-200'
    }
  }
  
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Watchlist */}
      <div className="lg:col-span-1">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Watchlist</h2>
          <div className="space-y-2">
            {symbols.map(symbol => {
              const latestPrice = pricesBySymbol[symbol]?.[0]
              const previousPrice = pricesBySymbol[symbol]?.[1]
              const change = latestPrice && previousPrice 
                ? ((latestPrice.close - previousPrice.close) / previousPrice.close * 100)
                : 0
              
              return (
                <button
                  key={symbol}
                  onClick={() => setSelectedSymbol(symbol)}
                  className={`w-full p-3 rounded-lg border transition-colors ${
                    selectedSymbol === symbol 
                      ? 'bg-blue-50 border-blue-300' 
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <span className="font-medium">{symbol}</span>
                    <div className="text-right">
                      <div className="font-medium">${latestPrice?.close.toFixed(2)}</div>
                      <div className={`text-sm ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </div>
      
      {/* Signals */}
      <div className="lg:col-span-2">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4">Recent Signals</h2>
          <div className="space-y-3">
            {signals.length === 0 ? (
              <p className="text-gray-500">No signals generated yet. Run the Python batch job to generate signals.</p>
            ) : (
              signals.map(signal => (
                <div 
                  key={signal.id}
                  className={`p-4 rounded-lg border ${getSignalColor(signal.signal_type)}`}
                >
                  <div className="flex items-start gap-3">
                    {getSignalIcon(signal.signal_type)}
                    <div className="flex-1">
                      <div className="flex justify-between items-start">
                        <div>
                          <span className="font-semibold">{signal.symbol}</span>
                          <span className="ml-2 px-2 py-1 text-xs font-medium rounded-full bg-white">
                            {signal.indicator}
                          </span>
                        </div>
                        <span className="text-sm text-gray-500">
                          {new Date(signal.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="mt-2 text-sm text-gray-600">
                        <span className="font-medium">{signal.signal_type}</span> signal at 
                        <span className="font-medium"> ${signal.price.toFixed(2)}</span>
                        {signal.value && (
                          <span> (Value: {signal.value.toFixed(2)})</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}