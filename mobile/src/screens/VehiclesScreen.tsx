import React, {useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
} from 'react-native';
import {useScheduleStore} from '../store/scheduleStore';
import {
  createVehicle,
  deleteVehicle,
  createCharger,
  deleteCharger,
} from '../services/api';
import {formatPercent} from '../utils/formatting';
import {colors, shadows} from '../utils/theme';
import VehicleCard from '../components/VehicleCard';

export default function VehiclesScreen() {
  const {vehicles, chargers, setVehicles, setChargers} = useScheduleStore();
  const [showAddVehicle, setShowAddVehicle] = useState(false);
  const [showAddCharger, setShowAddCharger] = useState(false);
  const [vName, setVName] = useState('');
  const [vCapacity, setVCapacity] = useState('');
  const [vChargeRate, setVChargeRate] = useState('');
  const [cName, setCName] = useState('');
  const [cPower, setCPower] = useState('');
  const [cPiAddress, setCPiAddress] = useState('');

  const handleAddVehicle = async () => {
    if (!vName || !vCapacity || !vChargeRate) {
      Alert.alert('Error', 'Please fill in all fields');
      return;
    }
    try {
      const res = await createVehicle({
        name: vName,
        battery_capacity_kwh: parseFloat(vCapacity),
        max_charge_rate_kw: parseFloat(vChargeRate),
      });
      setVehicles([...vehicles, res.data]);
      setVName('');
      setVCapacity('');
      setVChargeRate('');
      setShowAddVehicle(false);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Failed to add vehicle');
    }
  };

  const handleDeleteVehicle = async (id: string) => {
    Alert.alert('Delete Vehicle', 'Are you sure?', [
      {text: 'Cancel'},
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          await deleteVehicle(id);
          setVehicles(vehicles.filter(v => v.id !== id));
        },
      },
    ]);
  };

  const handleAddCharger = async () => {
    if (!cName || !cPower) {
      Alert.alert('Error', 'Please fill in name and power');
      return;
    }
    try {
      const res = await createCharger({
        name: cName,
        max_power_kw: parseFloat(cPower),
        pi_address: cPiAddress || undefined,
      });
      setChargers([...chargers, res.data]);
      setCName('');
      setCPower('');
      setCPiAddress('');
      setShowAddCharger(false);
    } catch (err: any) {
      Alert.alert('Error', err.response?.data?.detail || 'Failed to add charger');
    }
  };

  const handleDeleteCharger = async (id: string) => {
    Alert.alert('Delete Charger', 'Are you sure?', [
      {text: 'Cancel'},
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          await deleteCharger(id);
          setChargers(chargers.filter(c => c.id !== id));
        },
      },
    ]);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Vehicles Section */}
      <View style={styles.sectionHeader}>
        <Text style={styles.heading}>My Vehicles</Text>
        <TouchableOpacity onPress={() => setShowAddVehicle(!showAddVehicle)}>
          <Text style={styles.addButton}>
            {showAddVehicle ? 'Cancel' : '+ Add'}
          </Text>
        </TouchableOpacity>
      </View>

      {showAddVehicle && (
        <View style={[styles.formCard, shadows.card]}>
          <TextInput
            style={styles.input}
            placeholder="Vehicle name (e.g. Tesla Model 3)"
            placeholderTextColor={colors.textMuted}
            value={vName}
            onChangeText={setVName}
          />
          <TextInput
            style={styles.input}
            placeholder="Battery capacity (kWh)"
            placeholderTextColor={colors.textMuted}
            value={vCapacity}
            onChangeText={setVCapacity}
            keyboardType="numeric"
          />
          <TextInput
            style={styles.input}
            placeholder="Max charge rate (kW)"
            placeholderTextColor={colors.textMuted}
            value={vChargeRate}
            onChangeText={setVChargeRate}
            keyboardType="numeric"
          />
          <TouchableOpacity style={styles.saveButton} onPress={handleAddVehicle}>
            <Text style={styles.saveButtonText}>Add Vehicle</Text>
          </TouchableOpacity>
        </View>
      )}

      {vehicles.map(v => (
        <VehicleCard key={v.id} vehicle={v} onDelete={handleDeleteVehicle} />
      ))}
      {vehicles.length === 0 && !showAddVehicle && (
        <Text style={styles.emptyText}>No vehicles yet. Tap + Add to get started.</Text>
      )}

      {/* Chargers Section */}
      <View style={[styles.sectionHeader, {marginTop: 28}]}>
        <Text style={styles.heading}>My Chargers</Text>
        <TouchableOpacity onPress={() => setShowAddCharger(!showAddCharger)}>
          <Text style={styles.addButton}>
            {showAddCharger ? 'Cancel' : '+ Add'}
          </Text>
        </TouchableOpacity>
      </View>

      {showAddCharger && (
        <View style={[styles.formCard, shadows.card]}>
          <TextInput
            style={styles.input}
            placeholder="Charger name"
            placeholderTextColor={colors.textMuted}
            value={cName}
            onChangeText={setCName}
          />
          <TextInput
            style={styles.input}
            placeholder="Max power (kW)"
            placeholderTextColor={colors.textMuted}
            value={cPower}
            onChangeText={setCPower}
            keyboardType="numeric"
          />
          <TextInput
            style={styles.input}
            placeholder="Raspberry Pi address (optional)"
            placeholderTextColor={colors.textMuted}
            value={cPiAddress}
            onChangeText={setCPiAddress}
          />
          <TouchableOpacity style={styles.saveButton} onPress={handleAddCharger}>
            <Text style={styles.saveButtonText}>Add Charger</Text>
          </TouchableOpacity>
        </View>
      )}

      {chargers.map(c => (
        <View key={c.id} style={[styles.chargerCard, shadows.card]}>
          <View style={styles.cardRow}>
            <View style={styles.chargerIconBg}>
              <Text style={styles.chargerIcon}>{'\u26A1'}</Text>
            </View>
            <View style={{flex: 1, marginLeft: 12}}>
              <Text style={styles.chargerName}>{c.name}</Text>
              <Text style={styles.chargerDetail}>
                {c.max_power_kw} kW
              </Text>
              <View style={styles.statusRow}>
                <View
                  style={[
                    styles.statusDot,
                    {
                      backgroundColor:
                        c.status === 'charging'
                          ? colors.green
                          : c.status === 'offline'
                          ? colors.red
                          : colors.textMuted,
                    },
                  ]}
                />
                <Text style={styles.statusText}>{c.status}</Text>
              </View>
              {c.pi_address && (
                <Text style={styles.piAddress}>Pi: {c.pi_address}</Text>
              )}
            </View>
            <TouchableOpacity onPress={() => handleDeleteCharger(c.id)}>
              <Text style={styles.deleteText}>Delete</Text>
            </TouchableOpacity>
          </View>
        </View>
      ))}
      {chargers.length === 0 && !showAddCharger && (
        <Text style={styles.emptyText}>No chargers yet. Tap + Add to get started.</Text>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background},
  content: {padding: 16, paddingBottom: 32},
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  heading: {fontSize: 20, fontWeight: '700', color: colors.textPrimary},
  addButton: {color: colors.green, fontSize: 15, fontWeight: '600'},
  formCard: {
    backgroundColor: colors.white,
    borderRadius: 16,
    padding: 16,
    marginBottom: 14,
  },
  input: {
    backgroundColor: colors.background,
    color: colors.textPrimary,
    borderRadius: 10,
    padding: 14,
    fontSize: 15,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  saveButton: {
    backgroundColor: colors.green,
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
    marginTop: 4,
  },
  saveButtonText: {color: '#fff', fontSize: 16, fontWeight: '600'},
  emptyText: {color: colors.textMuted, fontSize: 14, marginBottom: 16},
  chargerCard: {
    backgroundColor: colors.white,
    borderRadius: 14,
    padding: 16,
    marginBottom: 10,
  },
  cardRow: {flexDirection: 'row', alignItems: 'center'},
  chargerIconBg: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: colors.greenLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chargerIcon: {fontSize: 18},
  chargerName: {color: colors.textPrimary, fontSize: 16, fontWeight: '600'},
  chargerDetail: {color: colors.textSecondary, fontSize: 13, marginTop: 1},
  statusRow: {flexDirection: 'row', alignItems: 'center', marginTop: 4},
  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    marginRight: 6,
  },
  statusText: {fontSize: 13, color: colors.textSecondary},
  piAddress: {color: colors.textMuted, fontSize: 12, marginTop: 2},
  deleteText: {color: colors.red, fontSize: 14, fontWeight: '500'},
});
