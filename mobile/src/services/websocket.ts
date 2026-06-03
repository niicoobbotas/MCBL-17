import {usePriceStore} from '../store/priceStore';

const WS_BASE = 'ws://localhost:8000';

let ws: WebSocket | null = null;

export function connectPriceStream(area?: string): void {
  const url = `${WS_BASE}/ws/prices${area ? `?area=${area}` : ''}`;

  if (ws) {
    ws.close();
  }

  ws = new WebSocket(url);

  ws.onmessage = event => {
    const data = JSON.parse(event.data);
    usePriceStore.getState().setCurrentPrice(data);
  };

  ws.onerror = () => {
    // Retry after 5 seconds
    setTimeout(() => connectPriceStream(area), 5000);
  };

  ws.onclose = () => {
    // Reconnect
    setTimeout(() => connectPriceStream(area), 5000);
  };
}

export function disconnectPriceStream(): void {
  if (ws) {
    ws.close();
    ws = null;
  }
}
