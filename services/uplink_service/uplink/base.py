from abc import ABC, abstractmethod

class UplinkBase(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def send(self, payload: dict) -> None:
        """Raise exception on failure."""
        ...
