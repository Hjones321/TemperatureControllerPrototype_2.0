from gpiozero import InputDevice, DigitalOutputDevice
from ADSReader import ADSReader
import time
from shelf import Shelf
from relay import Relay
import serial


from Logger import get_logger
logger = get_logger()

class DeviceManager():
    
    def __init__(self):
        self.shelves = []
        self.unitOn = True
        self.adsReader = ADSReader(0x48,1,3.3)
        self.adsReader.addThermistor(0)
        self.relayList= [[Relay(16, "element"), Relay(26, "fan")]]
        


    def addShelves(self, shelf):
        self.shelves.append(shelf)
        logger.info("[INFO] New shelf added")
        

    def alarmChecks(self):
        try:
            for i in range(len(self.relayList)):
                resistance = self.adsReader.readResistance(i)
        except Exception as e:
            logger.critical("[CRITICAL] ADS Error - shutting down")
            self.systemShutdown()
            return 

        for shelf in self.shelves:
            shelf.alarmChecks()
            
            
    def getActiveAlarms(self):
        alarms = {}
        for index, shelf in enumerate(self.shelves):
            if shelf.getActiveAlarms():
                alarms[index] = shelf.getActiveAlarms()

        return alarms
    
    def start(self):
        self.unitOn = True
        logger.info("[INFO] Shelves have been turned on")
        for shelf in self.shelves:
            shelf.start()

    def systemShutdown(self):
        logger.info("[INFO] system shutting down - system cooling")
        fanList = []
        fanCooldownTime = 30 #seconds

        for shelf in self.shelves:
            for relay in shelf.relayList:
                if relay.role == "element":
                    relay.off()
                elif relay.role == "fan":
                    relay.on()
                    fanList.append(relay)

        time.sleep(fanCooldownTime)
        
        logger.info("[INFO] fans shutting down - system cooled")
        for fan in fanList:
            fan.off()

        self.unitOn = False


    def allOff(self):
        logger.info("[INFO] All relays turning off")
        for shelf in self.shelves:
            shelf.relaysOff()
 
    def addAllShelves(self, shelves):
        logger.info(f"[INFO] created {shelves} shelves")
        for i in range(0, shelves):
            self.addShelves(Shelf(self.relayList[i], self.adsReader,i))
    
    def controlLoop(self):
        logger.debug("[DEBUG] Running alarm checks")
        self.alarmChecks()
        
        alarms = self.getActiveAlarms()
        
        if alarms:
            #handle what to do when theres an active alarm, below is an example of what alarms might look like for the sake of coming back to it later. i want it to be like, you have x alarms in shelf 1, x in 2, x in 3 and so on and so forth 
            logger.warning(f"[WARNING] alarms currently active - {alarms}")

            """
            alarms = {
            0: [ELEMENT_ERROR, OVERTEMP_ALARM, UNDERTEMP_ALARM],
            2: [OVERTEMP_ALARM],
            3: [UNDERTEMP_ALARM]
            }
            """
            pass
        
        temps = []
        for channel, shelf in enumerate(self.shelves):
            temp = self.adsReader.readTemperature(channel)
            shelf.control(temp)
            temps.append(temp)

        logger.debug(f"[DEBUG] returned temps - {temps}")    
        return temps



    
