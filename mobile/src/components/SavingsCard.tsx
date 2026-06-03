import React from 'react';
import {View, Text, StyleSheet} from 'react-native';
import type {SavingsSummary} from '../types';
import {formatEur} from '../utils/formatting';
import {colors, shadows} from '../utils/theme';

interface Props {
  savings: SavingsSummary;
}

export default function SavingsCard({savings}: Props) {
  return (
    <View style={[styles.card, shadows.card]}>
      <Text style={styles.mainSaving}>{formatEur(savings.total_savings)}</Text>
      <Text style={styles.mainLabel}>Total Saved</Text>

      <View style={styles.row}>
        <View style={styles.stat}>
          <Text style={styles.statValue}>
            {formatEur(savings.total_optimized_cost)}
          </Text>
          <Text style={styles.statLabel}>You Paid</Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statValueRed}>
            {formatEur(savings.total_naive_cost)}
          </Text>
          <Text style={styles.statLabel}>Without Optimization</Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statValueGreen}>
            {savings.savings_percent.toFixed(1)}%
          </Text>
          <Text style={styles.statLabel}>Saved</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderRadius: 16,
    padding: 24,
    marginBottom: 14,
    alignItems: 'center',
  },
  mainSaving: {fontSize: 40, fontWeight: 'bold', color: colors.green},
  mainLabel: {fontSize: 14, color: colors.textSecondary, marginTop: 4, marginBottom: 20},
  row: {flexDirection: 'row', justifyContent: 'space-around', width: '100%'},
  stat: {alignItems: 'center'},
  statValue: {color: colors.textPrimary, fontSize: 17, fontWeight: '600'},
  statValueRed: {color: colors.red, fontSize: 17, fontWeight: '600'},
  statValueGreen: {color: colors.green, fontSize: 17, fontWeight: '600'},
  statLabel: {color: colors.textMuted, fontSize: 11, marginTop: 2, textAlign: 'center'},
});
