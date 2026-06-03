import React from 'react';
import {NavigationContainer, DefaultTheme} from '@react-navigation/native';
import {createNativeStackNavigator} from '@react-navigation/native-stack';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {Text} from 'react-native';

import {useAuthStore} from '../store/authStore';
import {colors} from '../utils/theme';
import LoginScreen from '../screens/LoginScreen';
import RegisterScreen from '../screens/RegisterScreen';
import HomeScreen from '../screens/HomeScreen';
import ScheduleScreen from '../screens/ScheduleScreen';
import TimelineScreen from '../screens/TimelineScreen';
import DashboardScreen from '../screens/DashboardScreen';
import VehiclesScreen from '../screens/VehiclesScreen';
import SettingsScreen from '../screens/SettingsScreen';

const navTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: colors.background,
    card: colors.white,
    text: colors.textPrimary,
    border: colors.border,
    primary: colors.green,
  },
};

const AuthStack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();
const ScheduleStack = createNativeStackNavigator();

function ScheduleStackScreen() {
  return (
    <ScheduleStack.Navigator
      screenOptions={{
        headerStyle: {backgroundColor: colors.white},
        headerTintColor: colors.textPrimary,
        headerShadowVisible: false,
      }}>
      <ScheduleStack.Screen
        name="ScheduleMain"
        component={ScheduleScreen}
        options={{title: 'Charging Schedule'}}
      />
      <ScheduleStack.Screen
        name="Timeline"
        component={TimelineScreen}
        options={{title: 'Timeline'}}
      />
    </ScheduleStack.Navigator>
  );
}

function TabIcon({label, focused}: {label: string; focused: boolean}) {
  const icons: Record<string, string> = {
    Market: '\u26A1',
    Schedule: '\u23F0',
    'My Bill': '\u{1F4CA}',
    Vehicles: '\u{1F697}',
    Settings: '\u2699',
  };
  return (
    <Text
      style={{
        color: focused ? colors.green : colors.textMuted,
        fontSize: 20,
      }}>
      {icons[label] || label[0]}
    </Text>
  );
}

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({route}) => ({
        headerStyle: {backgroundColor: colors.white},
        headerTintColor: colors.textPrimary,
        headerShadowVisible: false,
        tabBarStyle: {
          backgroundColor: colors.white,
          borderTopColor: colors.borderLight,
          borderTopWidth: 1,
          height: 60,
          paddingBottom: 8,
        },
        tabBarActiveTintColor: colors.green,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarIcon: ({focused}) => (
          <TabIcon label={route.name} focused={focused} />
        ),
      })}>
      <Tab.Screen
        name="Market"
        component={HomeScreen}
        options={{title: 'Electricity Market'}}
      />
      <Tab.Screen
        name="Schedule"
        component={ScheduleStackScreen}
        options={{headerShown: false, title: 'Schedule'}}
      />
      <Tab.Screen
        name="My Bill"
        component={DashboardScreen}
        options={{title: 'My Energy Bill'}}
      />
      <Tab.Screen
        name="Vehicles"
        component={VehiclesScreen}
        options={{title: 'My Vehicles'}}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
      />
    </Tab.Navigator>
  );
}

export default function AppNavigator() {
  const {isAuthenticated} = useAuthStore();

  return (
    <NavigationContainer theme={navTheme}>
      {isAuthenticated ? (
        <MainTabs />
      ) : (
        <AuthStack.Navigator screenOptions={{headerShown: false}}>
          <AuthStack.Screen name="Login" component={LoginScreen} />
          <AuthStack.Screen name="Register" component={RegisterScreen} />
        </AuthStack.Navigator>
      )}
    </NavigationContainer>
  );
}
