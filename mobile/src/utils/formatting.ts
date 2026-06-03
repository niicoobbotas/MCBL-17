export function formatPrice(eurPerMwh: number): string {
  const centsPerKwh = eurPerMwh / 10;
  return `${centsPerKwh.toFixed(1)} ct/kWh`;
}

export function formatEur(amount: number): string {
  return `€${amount.toFixed(2)}`;
}

export function formatKwh(kwh: number): string {
  return `${kwh.toFixed(1)} kWh`;
}

export function formatTime(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
}

export function formatDate(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
  });
}

export function formatDateTime(isoString: string): string {
  return `${formatDate(isoString)} ${formatTime(isoString)}`;
}

export function formatPercent(value: number): string {
  return `${value.toFixed(0)}%`;
}
