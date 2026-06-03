import {create} from 'zustand';
import type {PricePoint} from '../types';

interface PriceState {
  currentPrice: PricePoint | null;
  dailyPrices: PricePoint[];
  setCurrentPrice: (price: PricePoint) => void;
  setDailyPrices: (prices: PricePoint[]) => void;
}

export const usePriceStore = create<PriceState>(set => ({
  currentPrice: null,
  dailyPrices: [],
  setCurrentPrice: (price) => set({currentPrice: price}),
  setDailyPrices: (prices) => set({dailyPrices: prices}),
}));
