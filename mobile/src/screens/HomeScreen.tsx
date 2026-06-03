import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Dimensions,
} from 'react-native';
import {LineChart} from 'react-native-chart-kit';
import {usePriceStore} from '../store/priceStore';
import {useScheduleStore} from '../store/scheduleStore';
import {useAuthStore} from '../store/authStore';
import {getPrices, getSchedules, getVehicles, getChargers} from '../services/api';
import {connectPriceStream} from '../services/websocket';
import {colors, shadows} from '../utils/theme';
import type {PricePoint} from '../types';
import {generateDemoPrices, demoVehicles, demoChargers, demoSchedule} from '../store/demoData';

const screenWidth = Dimensions.get('window').width - 56;

export default function HomeScreen() {
  const {currentPrice, dailyPrices, setDailyPrices, setCurrentPrice} = usePriceStore();
  const {setSchedules, setVehicles, setChargers} = useScheduleStore();
  const {isDemo} = useAuthStore();
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    if (isDemo) {
      const prices = generateDemoPrices();
      setDailyPrices(prices);
      const now = new Date();
      const currentHour = prices.find(
        p => new Date(p.timestamp).getHours() === now.getHours(),
      );
      if (currentHour) {setCurrentPrice(currentHour);}
      setVehicles(demoVehicles);
      setChargers(demoChargers);
      setSchedules([demoSchedule]);
      return;
    }
    try {
      const [priceRes, schedRes, vehRes, chgRes] = await Promise.all([
        getPrices(),
        getSchedules(),
        getVehicles(),
        getChargers(),
      ]);
      setDailyPrices(priceRes.data);
      setSchedules(schedRes.data);
      setVehicles(vehRes.data);
      setChargers(chgRes.data);
    } catch {
      // API may not be available yet
    }
  };

  useEffect(() => {
    loadData();
    if (!isDemo) {connectPriceStream();}
  }, []);

  const onRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  // Calculate stats
  const priceValues = dailyPrices.map(p => p.price_eur_per_mwh);
  const avgPrice = priceValues.length
    ? priceValues.reduce((a, b) => a + b, 0) / priceValues.length
    : 0;
  const peakPrice = priceValues.length ? Math.max(...priceValues) : 0;
  const lowPrice = priceValues.length ? Math.min(...priceValues) : 0;
  const currentEurKwh = currentPrice
    ? currentPrice.price_eur_per_mwh / 1000
    : avgPrice / 1000;
  const vsAvg = avgPrice
    ? Math.round(((currentEurKwh * 1000 - avgPrice) / avgPrice) * 100)
    : 0;

  // Find cheapest window
  const findCheapestWindow = (prices: PricePoint[]): string => {
    if (prices.length < 3) {return '';}
    let minSum = Infinity;
    let startIdx = 0;
    for (let i = 0; i <= prices.length - 3; i++) {
      const sum =
        prices[i].price_eur_per_mwh +
        prices[i + 1].price_eur_per_mwh +
        prices[i + 2].price_eur_per_mwh;
      if (sum < minSum) {
        minSum = sum;
        startIdx = i;
      }
    }
    const sH = new Date(prices[startIdx].timestamp).getHours();
    const eH = new Date(prices[startIdx + 2].timestamp).getHours() + 1;
    return `${sH.toString().padStart(2, '0')}:00 - ${eH.toString().padStart(2, '0')}:00`;
  };

  const cheapestWindow = findCheapestWindow(dailyPrices);

  // Find peak hours
  const findPeakHours = (prices: PricePoint[]): string => {
    if (prices.length === 0) {return '';}
    const maxP = Math.max(...prices.map(p => p.price_eur_per_mwh));
    const peakHours = prices.filter(p => p.price_eur_per_mwh === maxP);
    if (peakHours.length === 0) {return '';}
    const h = new Date(peakHours[0].timestamp).getHours();
    return `${h.toString().padStart(2, '0')}:00 - ${(h + 2).toString().padStart(2, '0')}:00`;
  };

  const findLowHours = (prices: PricePoint[]): string => {
    if (prices.length === 0) {return '';}
    const minP = Math.min(...prices.map(p => p.price_eur_per_mwh));
    const lowHours = prices.filter(p => p.price_eur_per_mwh === minP);
    if (lowHours.length === 0) {return '';}
    const h = new Date(lowHours[0].timestamp).getHours();
    return `${h.toString().padStart(2, '0')}:00 - ${(h + 2).toString().padStart(2, '0')}:00`;
  };

  // Chart data
  const chartLabels = dailyPrices
    .filter((_, i) => i % 4 === 0)
    .map(p => {
      const h = new Date(p.timestamp).getHours();
      return `${h.toString().padStart(2, '0')}:00`;
    });

  const chartValues = dailyPrices.map(p => p.price_eur_per_mwh);

  const peakVsAvg = avgPrice ? Math.round(((peakPrice - avgPrice) / avgPrice) * 100) : 0;
  const lowVsAvg = avgPrice ? Math.round(((lowPrice - avgPrice) / avgPrice) * 100) : 0;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }>
      {/* Current Price */}
      <View style={[styles.card, shadows.card]}>
        <Text style={styles.sectionLabel}>Current price</Text>
        <View style={styles.priceRow}>
          <Text style={styles.priceValue}>
            {'\u20AC'}{currentEurKwh.toFixed(2)}
          </Text>
          <Text style={styles.priceUnit}>/kWh</Text>
        </View>
        <View style={styles.vsAvgRow}>
          <Text
            style={[
              styles.vsAvgText,
              {color: vsAvg <= 0 ? colors.green : colors.red},
            ]}>
            {vsAvg <= 0 ? '\u2193' : '\u2191'} {Math.abs(vsAvg)}% vs avg
          </Text>
        </View>
      </View>

      {/* Price Chart */}
      {chartValues.length > 0 && (
        <View style={[styles.card, shadows.card]}>
          <Text style={styles.chartTitle}>Today - Wholesale electricity price</Text>
          <Text style={styles.chartUnit}>EUR/MWh</Text>

          {cheapestWindow ? (
            <View style={styles.cheapestBadge}>
              <Text style={styles.cheapestText}>Cheapest</Text>
              <Text style={styles.cheapestTime}>{cheapestWindow}</Text>
            </View>
          ) : null}

          <LineChart
            data={{
              labels: chartLabels,
              datasets: [{data: chartValues.length > 0 ? chartValues : [0]}],
            }}
            width={screenWidth}
            height={180}
            chartConfig={{
              backgroundColor: colors.white,
              backgroundGradientFrom: colors.white,
              backgroundGradientTo: colors.white,
              decimalPlaces: 0,
              color: () => colors.green,
              labelColor: () => colors.textMuted,
              fillShadowGradientFrom: colors.greenLight,
              fillShadowGradientTo: colors.white,
              fillShadowGradientFromOpacity: 0.6,
              fillShadowGradientToOpacity: 0,
              propsForDots: {r: '0'},
              propsForBackgroundLines: {stroke: colors.borderLight},
            }}
            bezier
            withDots={false}
            style={styles.chart}
          />
        </View>
      )}

      {/* Stats Row: Peak / Average / Low */}
      <View style={styles.statsRow}>
        <View style={[styles.statCard, shadows.card]}>
          <Text style={styles.statTitle}>Peak</Text>
          <View style={styles.statPriceRow}>
            <Text style={styles.statPrice}>
              {'\u20AC'}{(peakPrice / 1000).toFixed(2)}
            </Text>
            <Text style={styles.statUnit}>/kWh</Text>
          </View>
          <Text style={styles.statHours}>{findPeakHours(dailyPrices)}</Text>
          <Text style={[styles.statVsAvg, {color: colors.red}]}>
            {'\u2191'} {Math.abs(peakVsAvg)}% vs avg
          </Text>
        </View>

        <View style={[styles.statCard, shadows.card]}>
          <Text style={styles.statTitle}>Average</Text>
          <View style={styles.statPriceRow}>
            <Text style={styles.statPrice}>
              {'\u20AC'}{(avgPrice / 1000).toFixed(2)}
            </Text>
            <Text style={styles.statUnit}>/kWh</Text>
          </View>
          <Text style={styles.statHours}>Daily average</Text>
          <Text style={styles.statVsAvgNeutral}>{'--'} 0% vs avg</Text>
        </View>

        <View style={[styles.statCard, shadows.card]}>
          <Text style={styles.statTitle}>Low</Text>
          <View style={styles.statPriceRow}>
            <Text style={styles.statPrice}>
              {'\u20AC'}{(lowPrice / 1000).toFixed(2)}
            </Text>
            <Text style={styles.statUnit}>/kWh</Text>
          </View>
          <Text style={styles.statHours}>{findLowHours(dailyPrices)}</Text>
          <Text style={[styles.statVsAvg, {color: colors.green}]}>
            {'\u2193'} {Math.abs(lowVsAvg)}% vs avg
          </Text>
        </View>
      </View>

      {/* Smart Charging Card */}
      <View style={[styles.card, styles.smartCard, shadows.card]}>
        <View style={styles.smartIconBg}>
          <Text style={styles.smartIcon}>EV</Text>
        </View>
        <View style={{flex: 1, marginLeft: 14}}>
          <Text style={styles.smartTitle}>Smart charging</Text>
          <Text style={styles.smartSubtitle}>
            Charge during the cheapest hours and save money.
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  content: {padding: 16, paddingBottom: 32},
  card: {
    backgroundColor: colors.white,
    borderRadius: 16,
    padding: 20,
    marginBottom: 14,
  },
  sectionLabel: {fontSize: 13, color: colors.textSecondary, marginBottom: 4},
  priceRow: {flexDirection: 'row', alignItems: 'baseline'},
  priceValue: {fontSize: 40, fontWeight: '700', color: colors.green},
  priceUnit: {fontSize: 18, color: colors.textSecondary, marginLeft: 2},
  vsAvgRow: {marginTop: 6},
  vsAvgText: {fontSize: 14, fontWeight: '500'},
  chartTitle: {fontSize: 14, fontWeight: '600', color: colors.textPrimary, marginBottom: 2},
  chartUnit: {fontSize: 12, color: colors.textMuted, marginBottom: 8},
  cheapestBadge: {
    backgroundColor: colors.greenLight,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
    alignSelf: 'flex-start',
    marginBottom: 8,
  },
  cheapestText: {fontSize: 12, fontWeight: '600', color: colors.green},
  cheapestTime: {fontSize: 11, color: colors.greenDark},
  chart: {borderRadius: 12, marginLeft: -8},
  statsRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 14,
  },
  statCard: {
    flex: 1,
    backgroundColor: colors.white,
    borderRadius: 14,
    padding: 14,
  },
  statTitle: {fontSize: 13, fontWeight: '600', color: colors.textPrimary, marginBottom: 6},
  statPriceRow: {flexDirection: 'row', alignItems: 'baseline'},
  statPrice: {fontSize: 17, fontWeight: '700', color: colors.textPrimary},
  statUnit: {fontSize: 11, color: colors.textMuted},
  statHours: {fontSize: 11, color: colors.textMuted, marginTop: 4},
  statVsAvg: {fontSize: 11, fontWeight: '500', marginTop: 4},
  statVsAvgNeutral: {fontSize: 11, color: colors.textMuted, marginTop: 4},
  smartCard: {flexDirection: 'row', alignItems: 'center'},
  smartIconBg: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: colors.borderLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  smartIcon: {fontSize: 14, fontWeight: '700', color: colors.textSecondary},
  smartTitle: {fontSize: 15, fontWeight: '600', color: colors.textPrimary},
  smartSubtitle: {fontSize: 13, color: colors.textSecondary, marginTop: 2},
});
