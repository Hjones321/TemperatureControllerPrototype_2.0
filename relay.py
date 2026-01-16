from gpiozero import InputDevice, DigitalOutputDevice
import time
import logging
logger= logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Relay(DigitalOutputDevice):
    def __init__(self, pinNumber: int, name:str):
        super().__init__(pinNumber)
        self.name = name.lower()
        

        logger.debug(f"Relay {name} has been made")
