import React from 'react';
import {Dimensions} from 'react-native';
import {LineChart} from 'react-native-chart-kit';
import type {PricePoint} from '../types';
import {colors} from '../utils/theme';

const screenWidth = Dimensions.get('window').width - 64;

interface Props {
  prices: PricePoint[];
}

export default function PriceChart({prices}: Props) {
  if (prices.length === 0) {return null;}

  const labels = prices
    .filter((_, i) => i % 4 === 0)
    .map(p =>
      new Date(p.timestamp).getHours().toString().padStart(2, '0') + ':00',
    );

  const data = prices.map(p => p.price_eur_per_mwh / 10); // ct/kWh

  return (
    <LineChart
      data={{
        labels,
        datasets: [{data}],
      }}
      width={screenWidth}
      height={180}
      yAxisSuffix=" ct"
      chartConfig={{
        backgroundColor: colors.white,
        backgroundGradientFrom: colors.white,
        backgroundGradientTo: colors.white,
        decimalPlaces: 1,
        color: () => colors.green,
        labelColor: () => colors.textMuted,
        fillShadowGradientFrom: colors.greenLight,
        fillShadowGradientTo: colors.white,
        fillShadowGradientFromOpacity: 0.5,
        fillShadowGradientToOpacity: 0,
        propsForDots: {r: '0'},
        propsForBackgroundLines: {stroke: colors.borderLight},
      }}
      bezier
      withDots={false}
      style={{borderRadius: 12}}
    />
  );
}
