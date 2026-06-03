import React from 'react';
import {View, Text, StyleSheet, TouchableOpacity} from 'react-native';
import type {Vehicle} from '../types';
import {formatPercent} from '../utils/formatting';
import {colors, shadows} from '../utils/theme';

interface Props {
  vehicle: Vehicle;
  onDelete: (id: string) => void;
}

export default function VehicleCard({vehicle, onDelete}: Props) {
  const socColor =
    vehicle.current_soc_percent > 60
      ? colors.green
      : vehicle.current_soc_percent > 20
      ? colors.orange
      : colors.red;

  return (
    <View style={[styles.card, shadows.card]}>
      <View style={styles.row}>
        <View style={styles.iconBg}>
          <Text style={styles.icon}>EV</Text>
        </View>
        <View style={{flex: 1, marginLeft: 12}}>
          <Text style={styles.name}>{vehicle.name}</Text>
          <Text style={styles.detail}>
            {vehicle.battery_capacity_kwh} kWh | Max {vehicle.max_charge_rate_kw} kW
          </Text>
          <View style={styles.socRow}>
            <View style={styles.socBarBg}>
              <View
                style={[
                  styles.socBarFill,
                  {
                    width: `${vehicle.current_soc_percent}%`,
                    backgroundColor: socColor,
                  },
                ]}
              />
            </View>
            <Text style={[styles.socText, {color: socColor}]}>
              {formatPercent(vehicle.current_soc_percent)}
            </Text>
          </View>
          <Text style={styles.target}>
            Target: {formatPercent(vehicle.target_soc_percent)}
          </Text>
        </View>
        <TouchableOpacity onPress={() => onDelete(vehicle.id)}>
          <Text style={styles.deleteText}>Delete</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderRadius: 14,
    padding: 16,
    marginBottom: 10,
  },
  row: {flexDirection: 'row', alignItems: 'center'},
  iconBg: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: colors.borderLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  icon: {fontSize: 15, fontWeight: '700', color: colors.textSecondary},
  name: {color: colors.textPrimary, fontSize: 16, fontWeight: '600'},
  detail: {color: colors.textSecondary, fontSize: 13, marginTop: 2},
  socRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 8,
  },
  socBarBg: {
    flex: 1,
    height: 8,
    backgroundColor: colors.borderLight,
    borderRadius: 4,
    overflow: 'hidden',
  },
  socBarFill: {height: '100%', borderRadius: 4},
  socText: {fontSize: 13, fontWeight: '600', width: 36},
  target: {color: colors.textMuted, fontSize: 12, marginTop: 3},
  deleteText: {color: colors.red, fontSize: 14, fontWeight: '500'},
});
