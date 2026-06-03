import React from 'react';
import {View, Text, TouchableOpacity, StyleSheet} from 'react-native';
import {colors} from '../utils/theme';
import type {OptimizationMode} from '../types';

interface Props {
  mode: OptimizationMode;
  onChange: (mode: OptimizationMode) => void;
}

const OPTIONS: {
  mode: OptimizationMode;
  icon: string;
  label: string;
  hint: string;
}[] = [
  {mode: 'price', icon: '\u20AC', label: 'Cheapest', hint: 'Lowest cost'},
  {mode: 'smart', icon: '\u{1F50C}', label: 'Smart Grid', hint: 'Avoid peak load'},
  {mode: 'battery_life', icon: '\u{1F50B}', label: 'Battery', hint: 'Cap at 80%'},
];

export default function OptimizationToggle({mode, onChange}: Props) {
  return (
    <View style={styles.container}>
      {OPTIONS.map(opt => {
        const active = mode === opt.mode;
        return (
          <TouchableOpacity
            key={opt.mode}
            style={[styles.option, active && styles.optionActive]}
            onPress={() => onChange(opt.mode)}>
            <Text style={[styles.icon, active && styles.iconActive]}>
              {opt.icon}
            </Text>
            <Text style={[styles.label, active && styles.labelActive]}>
              {opt.label}
            </Text>
            <Text style={styles.hint}>{opt.hint}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flexDirection: 'row', gap: 8},
  option: {
    flex: 1,
    backgroundColor: colors.white,
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 8,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: colors.border,
  },
  optionActive: {borderColor: colors.green, backgroundColor: colors.greenLight},
  icon: {fontSize: 24, color: colors.textMuted, marginBottom: 4},
  iconActive: {color: colors.green},
  label: {color: colors.textSecondary, fontSize: 14, fontWeight: '600'},
  labelActive: {color: colors.textPrimary},
  hint: {color: colors.textMuted, fontSize: 11, marginTop: 4, textAlign: 'center'},
});
