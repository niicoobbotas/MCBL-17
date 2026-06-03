from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChargerStatusInfo:
    status: str  # idle, charging, offline
    current_rate_kw: float
    session_kwh: float
    connected: bool


class ChargerInterface(ABC):
    """Abstract interface for charger communication.

    Implement this for each charger protocol (Raspberry Pi REST, MQTT, OCPP, etc.).
    """

    @abstractmethod
    async def start_charging(self, charger_id: str, rate_kw: float) -> bool:
        """Send start command to charger. Returns True if successful."""
        ...

    @abstractmethod
    async def stop_charging(self, charger_id: str) -> bool:
        """Send stop command to charger. Returns True if successful."""
        ...

    @abstractmethod
    async def get_status(self, charger_id: str) -> ChargerStatusInfo:
        """Get current status from charger."""
        ...


class MockCharger(ChargerInterface):
    """Mock charger for development and testing."""

    def __init__(self):
        self._states: dict[str, ChargerStatusInfo] = {}

    async def start_charging(self, charger_id: str, rate_kw: float) -> bool:
        self._states[charger_id] = ChargerStatusInfo(
            status="charging",
            current_rate_kw=rate_kw,
            session_kwh=0.0,
            connected=True,
        )
        return True

    async def stop_charging(self, charger_id: str) -> bool:
        if charger_id in self._states:
            self._states[charger_id].status = "idle"
            self._states[charger_id].current_rate_kw = 0.0
        return True

    async def get_status(self, charger_id: str) -> ChargerStatusInfo:
        return self._states.get(
            charger_id,
            ChargerStatusInfo(status="idle", current_rate_kw=0.0, session_kwh=0.0, connected=True),
        )


class RaspberryPiCharger(ChargerInterface):
    """Future implementation: communicates with Raspberry Pi controller over REST/MQTT."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def start_charging(self, charger_id: str, rate_kw: float) -> bool:
        # TODO: implement when Pi protocol is decided
        raise NotImplementedError("Raspberry Pi charger protocol not yet implemented")

    async def stop_charging(self, charger_id: str) -> bool:
        raise NotImplementedError("Raspberry Pi charger protocol not yet implemented")

    async def get_status(self, charger_id: str) -> ChargerStatusInfo:
        raise NotImplementedError("Raspberry Pi charger protocol not yet implemented")


# Global charger instance — swap to RaspberryPiCharger when ready
charger = MockCharger()
