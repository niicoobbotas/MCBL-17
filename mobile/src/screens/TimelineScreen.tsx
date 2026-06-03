import React from 'react';
import {View, Text, StyleSheet, ScrollView} from 'react-native';
import {useScheduleStore} from '../store/scheduleStore';
import {usePriceStore} from '../store/priceStore';
import {formatTime, formatEur, formatKwh} from '../utils/formatting';
import {colors, shadows} from '../utils/theme';
import ScheduleTimeline from '../components/ScheduleTimeline';

export default function TimelineScreen() {
  const {schedules} = useScheduleStore();
  const {dailyPrices} = usePriceStore();

  const activeSchedules = schedules.filter(
    s => s.status === 'pending' || s.status === 'active',
  );
  const latestSchedule = activeSchedules[0];

  if (!latestSchedule) {
    return (
      <View style={styles.emptyContainer}>
        <View style={styles.emptyIconBg}>
          <Text style={styles.emptyIcon}>{'?'}</Text>
        </View>
        <Text style={styles.emptyText}>No active schedules</Text>
        <Text style={styles.emptyHint}>
          Create a schedule in the Schedule tab
        </Text>
      </View>
    );
  }

  const totalCost = latestSchedule.slots.reduce(
    (sum, s) => sum + s.estimated_cost,
    0,
  );
  const totalKwh = latestSchedule.slots.reduce(
    (sum, s) => sum + s.estimated_kwh,
    0,
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Summary Card */}
      <View style={[styles.card, shadows.card]}>
        <View style={styles.summaryRow}>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryLabel}>Total Energy</Text>
            <Text style={styles.summaryValue}>{formatKwh(totalKwh)}</Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryLabel}>Est. Cost</Text>
            <Text style={styles.summaryValueGreen}>{formatEur(totalCost)}</Text>
          </View>
          <View style={styles.summaryItem}>
            <Text style={styles.summaryLabel}>Slots</Text>
            <Text style={styles.summaryValue}>
              {latestSchedule.slots.length}
            </Text>
          </View>
        </View>
        <View style={styles.modeBadge}>
          <Text style={styles.modeText}>
            {latestSchedule.optimization_mode === 'price'
              ? 'Cheapest Price'
              : latestSchedule.optimization_mode === 'smart'
              ? 'Smart Grid'
              : 'Battery Life'}
          </Text>
        </View>
      </View>

      {/* Visual Timeline */}
      <ScheduleTimeline
        slots={latestSchedule.slots}
        prices={dailyPrices}
        availableFrom={latestSchedule.available_from}
        neededBy={latestSchedule.needed_by}
      />

      {/* Slot Details */}
      <Text style={styles.sectionTitle}>Charging Slots</Text>
      {latestSchedule.slots.map((slot, i) => (
        <View key={slot.id} style={[styles.slotCard, shadows.card]}>
          <View style={styles.slotHeader}>
            <View style={styles.slotNumberBg}>
              <Text style={styles.slotNumberText}>{i + 1}</Text>
            </View>
            <Text style={styles.slotCost}>{formatEur(slot.estimated_cost)}</Text>
          </View>
          <Text style={styles.slotTime}>
            {formatTime(slot.start_time)} - {formatTime(slot.end_time)}
          </Text>
          <Text style={styles.slotDetail}>
            {formatKwh(slot.estimated_kwh)} @ {slot.charge_rate_kw} kW
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  content: {padding: 16, paddingBottom: 32},
  emptyContainer: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  emptyIconBg: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: colors.greenLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  emptyIcon: {fontSize: 28, color: colors.green},
  emptyText: {color: colors.textPrimary, fontSize: 18, fontWeight: '600'},
  emptyHint: {color: colors.textSecondary, fontSize: 14, marginTop: 6},
  card: {
    backgroundColor: colors.white,
    borderRadius: 16,
    padding: 20,
    marginBottom: 14,
  },
  summaryRow: {flexDirection: 'row', justifyContent: 'space-between'},
  summaryItem: {alignItems: 'center'},
  summaryLabel: {color: colors.textSecondary, fontSize: 12, marginBottom: 4},
  summaryValue: {color: colors.textPrimary, fontSize: 20, fontWeight: 'bold'},
  summaryValueGreen: {color: colors.green, fontSize: 20, fontWeight: 'bold'},
  modeBadge: {
    backgroundColor: colors.greenLight,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 6,
    alignSelf: 'center',
    marginTop: 14,
  },
  modeText: {color: colors.green, fontSize: 13, fontWeight: '600'},
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginTop: 8,
    marginBottom: 12,
  },
  slotCard: {
    backgroundColor: colors.white,
    borderRadius: 14,
    padding: 16,
    marginBottom: 10,
    borderLeftWidth: 4,
    borderLeftColor: colors.green,
  },
  slotHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  slotNumberBg: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.greenLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  slotNumberText: {color: colors.green, fontSize: 13, fontWeight: '700'},
  slotCost: {color: colors.green, fontSize: 16, fontWeight: '600'},
  slotTime: {color: colors.textPrimary, fontSize: 16, fontWeight: '500'},
  slotDetail: {color: colors.textSecondary, fontSize: 13, marginTop: 2},
});
