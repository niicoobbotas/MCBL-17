import React from 'react';
import {View, Text, StyleSheet} from 'react-native';
import type {ScheduleSlot, PricePoint} from '../types';
import {colors} from '../utils/theme';

interface Props {
  slots: ScheduleSlot[];
  prices: PricePoint[];
  availableFrom: string;
  neededBy: string;
}

export default function ScheduleTimeline({slots, prices, availableFrom, neededBy}: Props) {
  const startHour = new Date(availableFrom).getHours();
  const endHour = new Date(neededBy).getHours() || 24;
  const totalHours = endHour > startHour ? endHour - startHour : 24 - startHour + endHour;

  const hours = Array.from({length: totalHours}, (_, i) => {
    const hour = (startHour + i) % 24;
    const isCharging = slots.some(s => {
      const slotStart = new Date(s.start_time).getHours();
      const slotEnd = new Date(s.end_time).getHours() || 24;
      return hour >= slotStart && hour < slotEnd;
    });

    const pricePoint = prices.find(
      p => new Date(p.timestamp).getHours() === hour,
    );
    const price = pricePoint ? pricePoint.price_eur_per_mwh / 10 : 0;

    return {hour, isCharging, price};
  });

  const maxPrice = Math.max(...hours.map(h => h.price), 1);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Timeline</Text>
      <View style={styles.timeline}>
        {hours.map(h => (
          <View key={h.hour} style={styles.hourBlock}>
            <View
              style={[
                styles.bar,
                {
                  height: (h.price / maxPrice) * 80,
                  backgroundColor: h.isCharging ? colors.green : colors.border,
                },
              ]}
            />
            <Text style={styles.hourLabel}>
              {h.hour.toString().padStart(2, '0')}
            </Text>
          </View>
        ))}
      </View>
      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, {backgroundColor: colors.green}]} />
          <Text style={styles.legendText}>Charging</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, {backgroundColor: colors.border}]} />
          <Text style={styles.legendText}>Idle</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.white,
    borderRadius: 16,
    padding: 16,
    marginBottom: 14,
  },
  title: {color: colors.textSecondary, fontSize: 14, fontWeight: '600', marginBottom: 12},
  timeline: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    height: 100,
    gap: 2,
  },
  hourBlock: {flex: 1, alignItems: 'center', justifyContent: 'flex-end'},
  bar: {width: '100%', borderRadius: 3, minHeight: 4},
  hourLabel: {color: colors.textMuted, fontSize: 9, marginTop: 4},
  legend: {flexDirection: 'row', gap: 16, marginTop: 12},
  legendItem: {flexDirection: 'row', alignItems: 'center', gap: 6},
  legendDot: {width: 10, height: 10, borderRadius: 5},
  legendText: {color: colors.textSecondary, fontSize: 12},
});
