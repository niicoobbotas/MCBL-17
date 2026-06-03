import React, {useState} from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ScrollView,
  Platform,
} from 'react-native';
import DateTimePicker from '@react-native-community/datetimepicker';
import Slider from '@react-native-community/slider';
import {useScheduleStore} from '../store/scheduleStore';
import {createSchedule} from '../services/api';
import CircularProgress from '../components/CircularProgress';
import OptimizationToggle from '../components/OptimizationToggle';
import {colors, shadows} from '../utils/theme';
import {formatEur} from '../utils/formatting';
import type {OptimizationMode} from '../types';

export default function ScheduleScreen({navigation}: any) {
  const {vehicles, chargers, addSchedule} = useScheduleStore();
  const [selectedVehicle, setSelectedVehicle] = useState(0);
  const [selectedCharger, setSelectedCharger] = useState(0);
  const [neededBy, setNeededBy] = useState(
    new Date(new Date().setHours(7, 0, 0, 0) + (new Date().getHours() >= 7 ? 86400000 : 0)),
  );
  const [targetSoc, setTargetSoc] = useState(80);
  const [mode, setMode] = useState<OptimizationMode>('price');
  const [loading, setLoading] = useState(false);
  const [showTimePicker, setShowTimePicker] = useState(false);

  const vehicle = vehicles[selectedVehicle];
  const charger = chargers[selectedCharger];

  const handleCreate = async () => {
    if (!vehicle || !charger) {
      Alert.alert('Setup Required', 'Please add a vehicle and charger first in the Vehicles tab.');
      return;
    }

    setLoading(true);
    try {
      const now = new Date();
      const res = await createSchedule({
        vehicle_id: vehicle.id,
        charger_id: charger.id,
        available_from: now.toISOString(),
        needed_by: neededBy.toISOString(),
        optimization_mode: mode,
      });
      addSchedule(res.data);
      Alert.alert('Schedule Created', 'Your charging has been optimized!', [
        {text: 'View Timeline', onPress: () => navigation.navigate('Timeline')},
        {text: 'OK'},
      ]);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Failed to create schedule');
    } finally {
      setLoading(false);
    }
  };

  const formatTimeDisplay = (d: Date) =>
    d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', hour12: true}).toUpperCase();

  const estimatedSavings = 4.20; // Placeholder until real calc

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Circular Progress */}
      <View style={styles.progressContainer}>
        <CircularProgress percent={targetSoc} />
      </View>

      {/* Ready By */}
      <View style={[styles.card, shadows.card]}>
        <View style={styles.cardRow}>
          <View style={styles.cardIconCircle}>
            <Text style={styles.cardIcon}>{'clock' === 'clock' ? '\u23F0' : ''}</Text>
          </View>
          <View style={{flex: 1}}>
            <Text style={styles.cardLabel}>Ready by</Text>
            <TouchableOpacity onPress={() => setShowTimePicker(true)}>
              <Text style={styles.timeDisplay}>{formatTimeDisplay(neededBy)}</Text>
            </TouchableOpacity>
          </View>
        </View>
        {showTimePicker && (
          <DateTimePicker
            value={neededBy}
            mode="time"
            display={Platform.OS === 'ios' ? 'spinner' : 'default'}
            onChange={(_, date) => {
              setShowTimePicker(Platform.OS === 'ios');
              if (date) {
                const next = new Date(neededBy);
                next.setHours(date.getHours(), date.getMinutes());
                setNeededBy(next);
              }
            }}
          />
        )}
      </View>

      {/* Target Battery Slider */}
      <View style={[styles.card, shadows.card]}>
        <View style={styles.sliderHeader}>
          <View>
            <Text style={styles.cardTitleBold}>Target Battery</Text>
            <Text style={styles.cardSubtitle}>Set the desired charge level</Text>
          </View>
          <Text style={styles.sliderValue}>{targetSoc}%</Text>
        </View>
        <Slider
          style={styles.slider}
          minimumValue={50}
          maximumValue={100}
          step={5}
          value={targetSoc}
          onValueChange={setTargetSoc}
          minimumTrackTintColor={colors.green}
          maximumTrackTintColor={colors.border}
          thumbTintColor={colors.green}
        />
        <View style={styles.sliderLabels}>
          <Text style={styles.sliderLabel}>50%</Text>
          <Text style={styles.sliderLabel}>100%</Text>
        </View>
      </View>

      {/* Optimization Mode */}
      <View style={styles.modeSection}>
        <Text style={styles.cardTitleBold}>Optimize for</Text>
        <Text style={styles.cardSubtitle}>How should we plan your charging?</Text>
        <View style={{marginTop: 12}}>
          <OptimizationToggle mode={mode} onChange={setMode} />
        </View>
      </View>

      {/* Connected Vehicle */}
      {vehicle ? (
        <View style={[styles.card, shadows.card]}>
          <View style={styles.vehicleRow}>
            <View style={styles.vehicleIconBg}>
              <Text style={styles.vehicleIcon}>EV</Text>
            </View>
            <View style={{flex: 1, marginLeft: 12}}>
              <Text style={styles.vehicleName}>{vehicle.name}</Text>
              <View style={styles.connectedBadge}>
                <View style={styles.greenDot} />
                <Text style={styles.connectedText}>Connected</Text>
              </View>
            </View>
            {vehicles.length > 1 && (
              <TouchableOpacity
                onPress={() =>
                  setSelectedVehicle((selectedVehicle + 1) % vehicles.length)
                }>
                <Text style={styles.switchText}>Switch</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      ) : (
        <View style={[styles.card, shadows.card]}>
          <Text style={styles.cardLabel}>No vehicle added yet</Text>
        </View>
      )}

      {/* Estimated Savings */}
      <View style={[styles.card, styles.savingsCard, shadows.card]}>
        <View style={styles.savingsIconCircle}>
          <Text style={styles.savingsIcon}>{'$'}</Text>
        </View>
        <View style={{flex: 1, marginLeft: 12}}>
          <Text style={styles.savingsLabel}>Estimated Cost Savings</Text>
          <Text style={styles.savingsValue}>
            Save {formatEur(estimatedSavings)} tonight
          </Text>
        </View>
      </View>

      {/* Create Button */}
      <TouchableOpacity
        style={[styles.createButton, loading && styles.buttonDisabled]}
        onPress={handleCreate}
        disabled={loading}>
        <Text style={styles.createButtonText}>
          {loading ? 'Optimizing...' : 'Start Smart Charging'}
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  content: {padding: 20, paddingBottom: 40},
  progressContainer: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  card: {
    backgroundColor: colors.white,
    borderRadius: 16,
    padding: 20,
    marginBottom: 14,
  },
  cardRow: {flexDirection: 'row', alignItems: 'center'},
  cardIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.greenLight,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  cardIcon: {fontSize: 20},
  cardLabel: {fontSize: 13, color: colors.textSecondary},
  timeDisplay: {fontSize: 32, fontWeight: '700', color: colors.textPrimary, marginTop: 2},
  sliderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  cardTitleBold: {fontSize: 16, fontWeight: '600', color: colors.textPrimary},
  cardSubtitle: {fontSize: 13, color: colors.textSecondary, marginTop: 2},
  modeSection: {marginBottom: 14},
  sliderValue: {fontSize: 20, fontWeight: '700', color: colors.green},
  slider: {width: '100%', height: 40},
  sliderLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: -4,
  },
  sliderLabel: {fontSize: 12, color: colors.textMuted},
  vehicleRow: {flexDirection: 'row', alignItems: 'center'},
  vehicleIconBg: {
    width: 50,
    height: 50,
    borderRadius: 12,
    backgroundColor: colors.borderLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  vehicleIcon: {fontSize: 16, fontWeight: '700', color: colors.textSecondary},
  vehicleName: {fontSize: 16, fontWeight: '600', color: colors.textPrimary},
  connectedBadge: {flexDirection: 'row', alignItems: 'center', marginTop: 4},
  greenDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.green,
    marginRight: 6,
  },
  connectedText: {fontSize: 13, color: colors.green},
  switchText: {fontSize: 14, color: colors.green, fontWeight: '600'},
  savingsCard: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  savingsIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.greenLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  savingsIcon: {fontSize: 18, color: colors.green, fontWeight: '700'},
  savingsLabel: {fontSize: 12, color: colors.textSecondary},
  savingsValue: {fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginTop: 2},
  createButton: {
    backgroundColor: colors.green,
    borderRadius: 14,
    padding: 18,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonDisabled: {opacity: 0.6},
  createButtonText: {color: '#fff', fontSize: 17, fontWeight: '600'},
});
