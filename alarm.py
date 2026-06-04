from Logger import get_logger
import time

logger = get_logger()

class Alarm:
    def __init__(self, name, severity: str, description: str, onStateChange=None):
        self.name = name
        self.active = False
        self.timestamp = None
        self.clearedTimestamp = None
        self.severity = severity
        self.description = description
        self.acknowledged = False
        self.overriddenAlarm = False

        #callbackj
        self.onStateChange = onStateChange
    
    def trigger(self, override= False):
        if override:
            self.overriddenAlarm = True
        if not self.isActive():
            self.active= True
            self.timestamp = time.time()

            if self.onStateChange:
                self.onStateChange(self)

            if self.severity == "critical":
                logger.critical(f"Alarm triggered {self.name} ({self.severity}) -> {self.description}")
            else:
                logger.error(f"Alarm triggered {self.name} ({self.severity}) -> {self.description}")

    def clear(self, override= False):
        if override:
            self.overriddenAlarm = False
        if self.isActive() and not self.overriddenAlarm:
            self.active = False
            self.clearedTimestamp = time.time()
            self.acknowledged = False

            if self.onStateChange:
                self.onStateChange(self)
            logger.info(f"Alarm cleared - {self.name}")

    def ack(self):
        if self.isActive():
            self.acknowledged = True
            if self.onStateChange:
                self.onStateChange(self)
        logger.info(f"Alarm acknowledged - {self.name}")
    def isActive(self):
        return self.active