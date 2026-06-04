from gpiozero import InputDevice, DigitalOutputDevice
import time
from Logger import get_logger

logger = get_logger()


class Relay(DigitalOutputDevice):
    def __init__(self, pinNumber: int, name:str):
        super().__init__(pinNumber, active_high=False)
        self.role = name.lower()
        

        logger.debug(f"Relay {name} has been made")
