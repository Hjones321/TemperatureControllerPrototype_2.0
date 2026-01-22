from Logger import get_logger
import time

logger = get_logger()

class Alarm:
    def __init__(self, name, severity: str, description: str):
        self.name = name
        self.active = True
        self.timestamp = None
        self.clearedTimestamp = None
        self.severity = severity
        self.description = description
        self.acknowledged = False
        self.notified = False
    
    def trigger(self):
        if not self.active():
            self.active= True
            self.timestamp = time.time()
            self.notified = False

            if self.severity == "critical":
                logger.critical(f"[CRITICAL] Alarm triggered {self.name} ({self.severity}) -> {self.description}")
            else:
                logger.error(f"[ERROR] Alarm triggered {self.name} ({self.severity}) -> {self.description}")

    def clear(self):
        if self.active:
            self.active = False
            self.clearedTimestamp = time.time()
            logger.info(f"[INFO] Alarm cleared - {self.name}")


    def isActive(self):
        return self.active