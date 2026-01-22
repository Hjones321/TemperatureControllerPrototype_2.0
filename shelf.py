import time
from gpiozero import InputDevice, DigitalOutputDevice

from alarm import Alarm

from Logger import get_logger
logger = get_logger()



class Shelf():
    def __init__(self, relays: list, tempSensor:object, channel:int, setTemp = 80) :
        
        #default temperature setpoint
        self.setTemp = setTemp
        self.channel = channel
        self.maxTemp, self.minTemp = 95, 60

        #how much the temperature can go above or below the setpoint
        self.overtempAllowance, self.undertempAllowance = 0, -2

        #how much above or below the setpoint the temperature goes before an alarm gets triggered
        self.overtempAlarm, self.undertempAlarm = 10, -10
        #how much the temperature needs to rise to confirm that the elements are working for the startup checks. 
        self.acceptanceDiff = 5 # °C
        #how long the system waits before it starts to check for alarms (under/overtemp alarms)
        self.rampupTime = 1*60*60 # 1hour

        #activeAlarmHolder
        self.alarmList = {
            "ELEMENT_ERROR": Alarm("ELEMENT_ERROR", "critical", "Heating element did not warmup on startup"),
            "UNDERTEMP_ALARM": Alarm("UNDERTEMP", "error", "Shelf temperature too low"),
            "OVERTEMP_ALARM": Alarm("OVERTEMP", "error", "Shelf temperature too high")
        }
        
        #the actual values produced from the upper and lower allowance above
        self.lowerTempBound = self.setTemp + self.undertempAllowance
        self.upperTempBound = self.setTemp + self.overtempAllowance
        
        #lists to hold the temperature sensors and the relays
        self.tempSensor = tempSensor
        self.startTemp = self.tempSensor.readTemperature(self.channel)

        self.relayList = relays
        
        self.isOn = False

        self.startupChecked = False

        self.startTime = time.time()


        
    def getTime(self):
        return time.time() - self.startTime
        
        
    def relaysOff(self):
        for relay in self.relayList:
            logger.info("[INFO] All relays in shelf{channel}")
            relay.off()

    def setRampupTime(self, newTime):
        #newTime is minutes, it converts it into seconds
        self.rampupTime = newTime * 60 
        logger.info("[INFO] New rampup time has been set")

    def start(self):
        
        logger.info("[INFO] Individual shelf has started")
        for relay in self.relayList:
            relay.on()

        self.isOn = True

    
        
    def elementOff(self):
        for relay in self.relayList:
            if relay.role == "element":
                logger.debug("[DEBUG] Element off")
                relay.off()

    def setStartTemp(self, temp):
        self.startTemp = temp
        logger.debug("[DEBUG] New start temperature has been set")

    

    def alarmChecks(self):
        #checks to see if the sensors are all receiving inputs
        
        #_______________ STARTUP CHECKS _______________ 

        if not self.startupChecked: 
            if self.getTime() < 15*60:
                if self.tempSensor.readTemperature(self.channel) > self.acceptanceDiff + self.startTemp:
                    self.startupChecked = True
                    logger.debug("[DEBUG] Element passed startup check")
                    return True
                else: 
                    pass
            else:
                if self.tempSensor.readTemperature(self.channel) < self.acceptanceDiff + self.startTemp:
                    
                    self.alarmList["ELEMENT_ERROR"].trigger()
                    
                
        #_______________ RUNTIME CHECKS _______________

        if self.getTime() >= self.rampupTime:

            if self.tempSensor.readTemperature(self.channel) < self.setTemp + self.undertempAlarm:
                self.alarmList["UNDERTEMP_ALARM"].trigger()
            else:
                self.alarmList["UNDERTEMP_ALARM"].clear()
                
            if self.tempSensor.readTemperature(self.channel) > self.setTemp + self.overtempAlarm:
                self.alarmList["OVERTEMP_ALARM"].trigger()
            else:
                self.alarmList["OVERTEMP_ALARM"].clear()

                

        


        

        
       
            
        
        
        

        

        
        
    def setNewTemp(self, newTemp: int):
        if newTemp > self.maxTemp:
            newTemp = self.maxTemp
        elif newTemp < self.minTemp:
            newTemp = self.minTemp
        self.setTemp = newTemp
        self.upperTempBound = self.setTemp + self.overtempAllowance
        self.lowerTempBound = self.setTemp + self.undertempAllowance

    def shelfToggle(self):
        if not self.isOn:
            self.isOn = True
            self.start()

        else:
            self.isOn = False
            self.elementOff()
        
    def control(self, temp):
        if self.isOn:    
            #if temperature goes above the upper bound, it turns the heating element off
            if temp > self.upperTempBound:
                for relay in self.relayList:
                    if relay.role == "element":
                        relay.off()

            #if the temperature goes below the lower bound, it turns the heating elements on
            elif temp < self.lowerTempBound:
                for relay in self.relayList:
                    if relay.role == "element":
                        relay.on()