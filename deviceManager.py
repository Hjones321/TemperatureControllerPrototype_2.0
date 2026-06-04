from gpiozero import InputDevice, DigitalOutputDevice
from ADSReader import ADSReader
import time
from shelf import Shelf
from relay import Relay
import threading


from Logger import get_logger
logger = get_logger()

class DeviceManager():
    
    def __init__(self):
        self.offset = 5
        self.shelves = []
        self.unitOn = True
        self.adsReader = ADSReader(0x48,1,3.3)
        self.adsReader.addThermistor(0)
        self.adsReader.addThermistor(1)
        self.relayList= [[Relay(26, "element"), Relay(16, "fan"), Relay(6, "light")],[Relay(17, "element"), Relay(5, "fan"), Relay(27, "light")]]

        self._shutdownLock = threading.Lock()
        self._overrideCooldown = False
        self._cooldownCancelled = False 
        self.latestTemps = []
        
        
    def getShelfStates(self):
        return [shelf.isOn for shelf in self.shelves]

    def setSetpointCallback(self, setpointFunc):
        self.publishSetpoint = setpointFunc    
        
    def saveShelfStates(self):
        for shelf in self.shelves:
            shelf.saveState()

    def addShelves(self, shelf):
        self.shelves.append(shelf)
        logger.info("[SHELF] New shelf added")
        

    def alarmChecks(self):
        logger.debug("Running alarm checks")
        try:
            for i in range(len(self.shelves)):
                resistance = self.adsReader.readResistance(i)
                if resistance is None:
                    self.shelves[i].alarmList["ADS_ALARM"].trigger()
        except Exception as e:
            logger.warning(f"ADS exception - {e}")
            return 

        for shelf in self.shelves:
            shelf.alarmChecks()
            

    def getTemp(self, shelfIndex):
        temp = self.adsReader.readTemperature(shelfIndex)
        return temp + self.offset if temp is not None else None

    def getActiveAlarms(self):
        alarms = {}
        for index, shelf in enumerate(self.shelves):
            active = []
            for alarm in shelf.alarmList.values():
                if alarm.isActive():
                    active.append(alarm)
            if active:
                alarms[index] = active
        return alarms
    
    def getSetpoints(self):
        setpoints = {}
        for index, shelf in enumerate(self.shelves):
            a,b,c = shelf.getSetpoints()
            setpoints[index] = [a,b,c] # setpoint, upper alarm, lower alarm
            
        return setpoints

    def getActives(self):
        actives = []
        for shelf in self.shelves:
            actives.append(shelf.isOn)  
        return actives      
    
    def acknowledgeAlarm(self, shelfIndex, alarmName):
        shelf = self.shelves[shelfIndex]
        if alarmName in shelf.alarmList:
            shelf.alarmList[alarmName].ack()
            return True
        return False  
    
    def start(self):
        self.unitOn = True
        self._overrideCooldown= True
        logger.info("Unit turned on, waiting for shelves to be turned on")

    def systemShutdown(self):
        if not self._shutdownLock.acquire(blocking=False):
            logger.warning("[SHUTDOWN] Already shutting down - ignoring duplicate call")
            return
        try:
            self.unitOn = False
            self._cooldownCancelled = False  
            logger.info("system shutting down - system cooling")
            fanCooldownTime = 30

            for shelf in self.shelves:
                shelf.elementOff()
                shelf.isOn = False
                if shelf._cooldownTimer is not None:
                    shelf._cooldownTimer.cancel()
                    shelf._cooldownTimer = None
                for relay in shelf.relayList:
                    if relay.role == "fan":
                        relay.on()

            def cooldown():
                logger.info("[SHUTDOWN] Starting fan cooldown")
                time.sleep(fanCooldownTime)

                if self._cooldownCancelled:
                    logger.info("[SHUTDOWN] Cooldown cancelled - system restarted, skipping fan off")
                    self._shutdownLock.release()
                    return

                for shelf in self.shelves:
                    for relay in shelf.relayList:
                        if relay.role == "fan" and shelf.fanLastOn is not None:
                            shelf.fanLife += (time.time() - shelf.fanLastOn) / 3600
                            shelf.fanLastOn = None
                        relay.off()

                logger.info("[SHUTDOWN] Cooldown complete - fans off")
                self._shutdownLock.release()

            threading.Thread(target=cooldown, daemon=True).start()

        except Exception as e:
            logger.error(f"[SHUTDOWN] Exception during shutdown - {e}")
            self._shutdownLock.release()

        


    def allOff(self):
        logger.info("[RELAYS] All relays turning off")
        for shelf in self.shelves:
            shelf.relaysOff()
 
    def addAllShelves(self, shelves):
        logger.info(f"[SHELF] created {shelves} shelves")
        self.latestTemps = [None]*shelves
        for i in range(0, shelves):
            
            self.addShelves(Shelf(self.relayList[i], self.adsReader,self.offset, i))
    
    def controlLoop(self):
        
        self.alarmChecks()
        
        alarms = self.getActiveAlarms()

        if not self.unitOn:
            return

        for shelfIndex, alarmList in alarms.items():
            for alarm in alarmList:
                if alarm.severity == "critical":
                    logger.critical("[CRITICAL ALARM] Shutting down...")
                    self.systemShutdown()
                    return
        
        
        
        for channel, shelf in enumerate(self.shelves):
            temp = self.getTemp(channel)
            logger.debug(f"[TEMP] Shelf {channel} temp read: {temp}")
            if temp is not None:
                shelf.control(temp)
                self.latestTemps[channel] = temp
            else:
                logger.warning(f"Shelf {channel} temp read returned None - skipping control this cycle")


            
            
        



    
