import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
} from 'react-native';
import {useAuthStore} from '../store/authStore';
import {colors, shadows} from '../utils/theme';

export default function SettingsScreen() {
  const {user, logout} = useAuthStore();

  const handleLogout = () => {
    Alert.alert('Log Out', 'Are you sure?', [
      {text: 'Cancel'},
      {text: 'Log Out', style: 'destructive', onPress: logout},
    ]);
  };

  return (
    <View style={styles.container}>
      {/* Profile Card */}
      <View style={[styles.card, shadows.card]}>
        <View style={styles.avatarRow}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {(user?.name || 'U')[0].toUpperCase()}
            </Text>
          </View>
          <View style={{marginLeft: 14}}>
            <Text style={styles.userName}>{user?.name || '-'}</Text>
            <Text style={styles.userEmail}>{user?.email || '-'}</Text>
          </View>
        </View>
      </View>

      {/* Preferences */}
      <View style={[styles.card, shadows.card]}>
        <Text style={styles.cardTitle}>Preferences</Text>
        <View style={styles.prefRow}>
          <Text style={styles.prefLabel}>Price Area</Text>
          <Text style={styles.prefValue}>NL</Text>
        </View>
        <View style={[styles.prefRow, {borderBottomWidth: 0}]}>
          <Text style={styles.prefLabel}>Notifications</Text>
          <Text style={[styles.prefValue, {color: colors.green}]}>Enabled</Text>
        </View>
      </View>

      {/* About */}
      <View style={[styles.card, shadows.card]}>
        <Text style={styles.cardTitle}>About</Text>
        <View style={styles.prefRow}>
          <Text style={styles.prefLabel}>Version</Text>
          <Text style={styles.prefValue}>0.1.0</Text>
        </View>
        <View style={[styles.prefRow, {borderBottomWidth: 0}]}>
          <Text style={styles.prefLabel}>Charger Protocol</Text>
          <Text style={styles.prefValue}>Mock (dev)</Text>
        </View>
      </View>

      {/* Logout */}
      <TouchableOpacity
        style={[styles.logoutButton, shadows.card]}
        onPress={handleLogout}>
        <Text style={styles.logoutText}>Log Out</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: colors.background, padding: 16},
  card: {
    backgroundColor: colors.white,
    borderRadius: 16,
    padding: 20,
    marginBottom: 14,
  },
  avatarRow: {flexDirection: 'row', alignItems: 'center'},
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: colors.greenLight,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {fontSize: 22, fontWeight: '700', color: colors.green},
  userName: {fontSize: 18, fontWeight: '600', color: colors.textPrimary},
  userEmail: {fontSize: 14, color: colors.textSecondary, marginTop: 2},
  cardTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: 12,
  },
  prefRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.borderLight,
  },
  prefLabel: {fontSize: 15, color: colors.textPrimary},
  prefValue: {fontSize: 15, color: colors.textSecondary},
  logoutButton: {
    backgroundColor: colors.white,
    borderRadius: 14,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.red,
  },
  logoutText: {color: colors.red, fontSize: 16, fontWeight: '600'},
});
