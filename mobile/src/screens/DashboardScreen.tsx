import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Dimensions,
} from 'react-native';
import {BarChart} from 'react-native-chart-kit';
import {getSavings, getHistory} from '../services/api';
import {formatEur, formatDate} from '../utils/formatting';
import {colors, shadows} from '../utils/theme';
import type {SavingsSummary, ChargingSession} from '../types';

const screenWidth = Dimensions.get('window').width - 56;

export default function DashboardScreen() {
  const [period, setPeriod] = useState<'week' | 'month' | 'year'>('month');
  const [savings, setSavings] = useState<SavingsSummary | null>(null);
  const [history, setHistory] = useState<ChargingSession[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const [savRes, histRes] = await Promise.all([
        getSavings(period),
        getHistory(),
      ]);
      setSavings(savRes.data);
      setHistory(histRes.data);
    } catch {
      // Handle error silently
    }
  };

  useEffect(() => {
    loadData();
  }, [period]);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const now = new Date();
  const monthName = now.toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  });

  // Build bar chart data from daily savings
  const chartLabels =
    savings?.daily.length && savings.daily.length >= 3
      ? savings.daily.slice(-3).map(d => {
          const date = new Date(d.date);
          return date.toLocaleDateString('en-US', {month: 'short', year: 'numeric'});
        })
      : ['Sept 2025', 'Oct 2025', 'Nov 2025'];

  const chartValues =
    savings?.daily.length && savings.daily.length >= 3
      ? savings.daily.slice(-3).map(d => d.optimized_cost)
      : [58, 48, 42];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }>
      {/* Bill Summary Card */}
      <View style={[styles.card, shadows.card]}>
        <View style={styles.billHeader}>
          <View style={styles.billIconBg}>
            <Text style={styles.billIcon}>{'\u26A1'}</Text>
          </View>
          <Text style={styles.billMonth}>{monthName}</Text>
        </View>

        <Text style={styles.billAmount}>
          {formatEur(savings?.total_optimized_cost ?? 48.2)}
        </Text>
        <Text style={styles.billLabel}>Estimated bill</Text>

        <View style={styles.savedBadge}>
          <View style={styles.savedDot} />
          <Text style={styles.savedText}>
            Saved {formatEur(savings?.total_savings ?? 17.8)} this month
          </Text>
        </View>
      </View>

      {/* Monthly Cost Chart */}
      <View style={[styles.card, shadows.card]}>
        <Text style={styles.chartTitle}>Monthly cost (EUR)</Text>
        <BarChart
          data={{
            labels: chartLabels,
            datasets: [{data: chartValues}],
          }}
          width={screenWidth}
          height={180}
          yAxisLabel=""
          yAxisSuffix=""
          chartConfig={{
            backgroundColor: colors.white,
            backgroundGradientFrom: colors.white,
            backgroundGradientTo: colors.white,
            decimalPlaces: 0,
            color: () => colors.purpleMuted,
            labelColor: () => colors.textMuted,
            barPercentage: 0.5,
            propsForBackgroundLines: {stroke: colors.borderLight},
            fillShadowGradientFrom: colors.purpleMuted,
            fillShadowGradientTo: colors.purpleMuted,
          }}
          style={styles.chart}
          showValuesOnTopOfBars={false}
          fromZero
        />
      </View>

      {/* Recent Sessions */}
      <View style={[styles.card, shadows.card]}>
        <View style={styles.sessionsHeader}>
          <Text style={styles.sessionsTitle}>Recent charging sessions</Text>
          <TouchableOpacity>
            <Text style={styles.seeAll}>See all</Text>
          </TouchableOpacity>
        </View>

        {history.length === 0 ? (
          <Text style={styles.emptyText}>No charging sessions yet</Text>
        ) : (
          history.slice(0, 5).map((session, index) => (
            <View
              key={session.id}
              style={[
                styles.sessionRow,
                index < Math.min(history.length, 5) - 1 && styles.sessionBorder,
              ]}>
              <View style={styles.sessionIconBg}>
                <Text style={styles.sessionIcon}>{'\u26A1'}</Text>
              </View>
              <Text style={styles.sessionDate}>
                {formatDate(session.start_time)}
              </Text>
              <Text style={styles.sessionKwh}>
                {session.energy_kwh.toFixed(0)} kWh
              </Text>
              <Text style={styles.sessionCost}>
                {formatEur(session.cost)}
              </Text>
              <Text style={styles.sessionChevron}>{'>'}</Text>
            </View>
          ))
        )}
      </View>

      {/* View Full Statement Button */}
      <TouchableOpacity style={[styles.statementButton, shadows.card]}>
        <Text style={styles.statementText}>View full statement</Text>
        <Text style={styles.statementArrow}>{'>'}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  content: {padding: 16, paddingBottom: 40},
  card: {
    backgroundColor: colors.white,
    borderRadius: 16,
    padding: 20,
    marginBottom: 14,
  },
  billHeader: {flexDirection: 'row', alignItems: 'center', marginBottom: 16},
  billIconBg: {
    width: 40,
    height: 40,
    borderRadius: 10,
    backgroundColor: colors.purpleLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  billIcon: {fontSize: 18},
  billMonth: {fontSize: 15, color: colors.textSecondary},
  billAmount: {fontSize: 40, fontWeight: '700', color: colors.textPrimary},
  billLabel: {fontSize: 14, color: colors.textSecondary, marginTop: 2},
  savedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.greenLight,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    marginTop: 16,
    alignSelf: 'flex-start',
  },
  savedDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.green,
    marginRight: 8,
  },
  savedText: {fontSize: 14, fontWeight: '600', color: colors.green},
  chartTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: 12,
  },
  chart: {borderRadius: 12, marginLeft: -12},
  sessionsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  sessionsTitle: {fontSize: 16, fontWeight: '600', color: colors.textPrimary},
  seeAll: {fontSize: 14, color: colors.purple, fontWeight: '500'},
  emptyText: {fontSize: 14, color: colors.textMuted},
  sessionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
  },
  sessionBorder: {
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  sessionIconBg: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: colors.purpleLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  sessionIcon: {fontSize: 14},
  sessionDate: {flex: 1, fontSize: 15, color: colors.textPrimary},
  sessionKwh: {fontSize: 14, color: colors.textSecondary, marginRight: 16},
  sessionCost: {fontSize: 15, fontWeight: '600', color: colors.textPrimary, marginRight: 8},
  sessionChevron: {fontSize: 16, color: colors.textMuted},
  statementButton: {
    backgroundColor: colors.purple,
    borderRadius: 14,
    padding: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  statementText: {color: '#fff', fontSize: 17, fontWeight: '600'},
  statementArrow: {color: '#fff', fontSize: 18, marginLeft: 8},
});
