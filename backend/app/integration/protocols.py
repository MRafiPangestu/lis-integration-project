from typing import Protocol

class InstrumentTransport(Protocol):
    """Protocol defining the interface for instrument communication."""

    def send_ack(self, control_id: str) -> None:
        """Send ACK^R01. Protocol requirement — always implemented."""
        ...

    def send_command(self, command: bytes) -> None:
        """Send an outbound command to the instrument.
        FUTURE: Request Button capability.
        """
        ...

