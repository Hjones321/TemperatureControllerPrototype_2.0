import time
from gpiozero import InputDevice, DigitalOutputDevice

from alarm import Alarm
import os, json

from Logger import get_logger
logger = get_logger()
import threading


class Shelf():
    def __init__(self, relays: list, tempSensor:object, offset, channel:int, setTemp = 85) :
        
        #default temperature setpoint
        self.setTemp = setTemp
        self.channel = channel
        self.maxTemp, self.minTemp = 95, 60
        self.offset = offset
        #how much the temperature can go above or below the setpoint
        self.overtempAllowance, self.undertempAllowance = 0, -2

        #how much above or below the setpoint the temperature goes before an alarm gets triggered
        self.overtempAlarm, self.undertempAlarm = 10, -10
        #how much the temperature needs to rise to confirm that the elements are working for the startup checks. 
        self.acceptanceDiff = 5 # °C
        #how long the system waits before it starts to check for alarms (under/overtemp alarms)
        self.rampupTime = 1*60*60 # 1hour
        self.clearThreshold = 5

        self._cooldownTimer = None

        self.alarmCallback = None

        #activeAlarmHolder
        self.alarmList = {
            "ELEMENT_ERROR": Alarm("ELEMENT_ERROR", "critical", "Heating element did not warmup on startup", onStateChange=self.onAlarmChange),
            "UNDERTEMP_ALARM": Alarm("UNDERTEMP_ALARM", "error", "Shelf temperature too low", onStateChange=self.onAlarmChange),
            "OVERTEMP_ALARM": Alarm("OVERTEMP_ALARM", "critical", "Shelf temperature too high", onStateChange=self.onAlarmChange),
            "ADS_ALARM": Alarm("ADS_ALARM", "error", "potential problem with ADS, verify function", onStateChange=self.onAlarmChange)
        }
        
        #the actual values produced from the upper and lower allowance above
        self.lowerTempBound = self.setTemp + self.undertempAllowance
        self.upperTempBound = self.setTemp + self.overtempAllowance
        
        #lists to hold the temperature sensors and the relays
        self.tempSensor = tempSensor
        self.startTemp = self.getTemp()
        if self.startTemp is None:
            logger.warning("[ADS] Potential problem with the ADS1115")
            self.startTemp = 20

        self.relayList = relays
        
        self.isOn = False

        self.manualOverride = False
        
        self.elementTurnedOn, self.fanLastOn = None, None
        
        self.lastSetpointChanged = None
        self.tempAtLastSetpointChange = None
        
        self.startupChecked = False

        self.startTime = time.time()
        self.stateFile = "./data/shelfState.json"
        self.loadState()

        



        self.SETPOINT_TIME_ALLOWANCE = 30*60

   

    def onAlarmChange(self, alarm):
        if self.alarmCallback:
            self.alarmCallback(self.channel, alarm)
    
    def setAlarmCallback(self, callback):
        self.alarmCallback = callback

    def getLight(self):
        for relay in self.relayList:
            if relay.role == "light":
                if relay.is_active:
                    return 1
                else:
                    return 0

    def setLight(self, on: bool):
        for relay in self.relayList:
            if relay.role == "light":
                relay.on() if on else relay.off()
                logger.debug(f"Light toggled - {on} - in shelf {self.channel+1}")


    def turnOn(self, manual= False):
        if manual:
            self.manualOverride = True

        if not self.isOn:
            if self._cooldownTimer is not None:
                self._cooldownTimer.cancel()
                self._cooldownTimer = None
                logger.info(f"shelf {self.channel+1} cooldown cancelled - turning back on")
            
            currentTemp = self.getTemp()

            if currentTemp is not None and currentTemp > 40:
                self.startupChecked = True
                logger.info(f"Shelf {self.channel+1} already warm ({currentTemp:.1f}°C) - skipping startup check")
            else:
                self.startupChecked = False

            
            self.startTime = time.time()
            self.setStartTemp(self.getTemp())
            self.start()
            logger.info(f"shelf {self.channel + 1} turned on")

    def turnOff(self, manual= False):
        if manual:
            self.manualOverride = True
            
        if self.isOn:
            self.elementOff()
            self.isOn = False
            self._cooldownTimer = threading.Timer(30, self._finishCooldown)
            self._cooldownTimer.start() 
            
            logger.info(f"shelf {self.channel+1} turned off - fan cooldown started")

    def _finishCooldown(self):
        if not self.isOn:
            self.relaysOff()
            logger.info(f"shelf {self.channel + 1} cooldown complete - all relays off")
        self._cooldownTimer = None


    def getTime(self):
        return time.time() - self.startTime
        
        
    def relaysOff(self):
        logger.info(f"All relays in shelf{self.channel+1} switching off")
        for relay in self.relayList:
            
            

            if relay.role == "element" and self.elementTurnedOn is not None:
                runtime = time.time() - self.elementTurnedOn
                self.elementLife += runtime / 3600
                self.elementTurnedOn = None
                relay.off()

            if relay.role == "fan" and self.fanLastOn is not None:
                runtime = time.time() - self.fanLastOn
                self.fanLife += runtime /3600
                self.fanLastOn = None
                relay.off()
        
            

    def getSetpoints(self):
        return [self.setTemp, self.upperTempBound, self.lowerTempBound]

    def setRampupTime(self, newTime):
        #newTime is minutes, it converts it into seconds
        self.rampupTime = newTime * 60 
        logger.info(f"New rampup time has been set - {newTime}")

    def start(self):
        
        logger.info(f"Individual shelf {self.channel+1} has started")
        for relay in self.relayList:
            if relay.role == "element":
                self.elementTurnedOn = time.time()
                relay.on()

            if relay.role == "fan":
                self.fanLastOn = time.time()
                relay.on()
            
            
            

        self.isOn = True

    def getRelayLife(self):
        fanNow, elementNow = 0,0

        if self.fanLastOn is not None:
            fanNow = (time.time() - self.fanLastOn) /3600
        
        if self.elementTurnedOn is not None:
            elementNow = (time.time() - self.elementTurnedOn) /3600
        return [self.fanLife + fanNow, self.elementLife + elementNow]
    
        
    def elementOff(self):
        for relay in self.relayList:
            if relay.role == "element":
                logger.info(f"Element from shelf {self.channel+1} off")
                if self.elementTurnedOn is not None:
                    runtime = time.time() - self.elementTurnedOn
                    self.elementLife += runtime /3600 
                    self.elementTurnedOn = None
                relay.off()

    def setStartTemp(self, temp):
        if temp is not None:
            self.startTemp = temp
        logger.info(f"New start temperature has been set - {temp}")
    
    def saveState(self):
        logger.debug(f"Relay Life saving for shelf {self.channel +1}")
        now = time.time()

        fanSession = (now - self.fanLastOn)/3600 if self.fanLastOn is not None else 0
        elementSession = (now - self.elementTurnedOn)/3600 if self.elementTurnedOn is not None else 0
  

        os.makedirs(os.path.dirname(self.stateFile), exist_ok=True)

        state = {}
        if os.path.exists(self.stateFile):
            try:
                with open(self.stateFile, 'r') as f:
                    state = json.load(f)
            except:
                state = {}

      
        state[f"shelf_{self.channel}"] = {
            "fanHours": self.fanLife+fanSession,
            "elementHours": self.elementLife + elementSession,
            "lastUpdated": time.time()
        }

        tmpFile = self.stateFile + ".tmp"

        try:
            with open(tmpFile, "w") as f:
                json.dump(state,f, indent=2)
            os.replace(tmpFile, self.stateFile)
        except Exception as e:
            logger.error(f"failed to save state: {e}")
    
    def loadState(self):
        os.makedirs(os.path.dirname(self.stateFile), exist_ok=True)

        if os.path.exists(self.stateFile):
            try:
                with open(self.stateFile, "r") as f:
                    state = json.load(f)
                    shelfData = state.get(f"shelf_{self.channel}", {})
                    self.fanLife = shelfData.get("fanHours", 0.0)  
                    self.elementLife= shelfData.get("elementHours", 0.0)
                    logger.info(f"loaded shelf {self.channel+1} state: Fan={self.fanLife:.2f}h, Element={self.elementLife:.2f}h")
            except Exception as e:
                logger.error(f"Failed to load state {e}")
                self.fanLife = 0.0
                self.elementLife = 0.0
        else:
            self.fanLife =0.0
            self.elementLife = 0.0
    
    def getTemp(self):
        temp = self.tempSensor.readTemperature(self.channel)
        return temp + self.offset if temp is not None else None

    def alarmChecks(self):
        #checks to see if the sensors are all receiving inputs
        temp = self.getTemp()
        if temp is None:
            return
        
        if not self.isOn:
            return
        #_______________ STARTUP CHECKS _______________ 

        if not self.startupChecked: 
            if self.getTime() < 15*60:
                if temp > self.acceptanceDiff + self.startTemp:
                    self.startupChecked = True
                    logger.info(f"Shelf {self.channel+1} passed startup check at {temp:.1f}°C")
                    
                else: 
                    pass
            else:
                if temp < self.acceptanceDiff + self.startTemp:
                    
                    self.alarmList["ELEMENT_ERROR"].trigger()
                    self.startupChecked = True
                    
                
        #_______________ RUNTIME CHECKS _______________

        if self.getTime() >= self.rampupTime:
            if self.lastSetpointChanged is not None:
                if time.time() - self.lastSetpointChanged < self.SETPOINT_TIME_ALLOWANCE : 
                    return 
            if temp < self.setTemp + self.undertempAlarm:
                self.alarmList["UNDERTEMP_ALARM"].trigger()
            elif temp > self.setTemp + self.undertempAlarm + self.clearThreshold:
                self.alarmList["UNDERTEMP_ALARM"].clear()
                
            if temp > self.setTemp + self.overtempAlarm:
                self.alarmList["OVERTEMP_ALARM"].trigger()
            elif temp < self.setTemp + self.overtempAlarm - self.clearThreshold:
                self.alarmList["OVERTEMP_ALARM"].clear()



    def setNewTemp(self, newTemp: int):
        
        if newTemp > self.maxTemp:
            logger.warning(f"Shelf {self.channel+1} setpoint {newTemp} clamped to max {self.maxTemp}")
            newTemp = self.maxTemp
            
        elif newTemp < self.minTemp:
            newTemp = self.minTemp


        
        self.setTemp = newTemp
        self.upperTempBound = self.setTemp + self.overtempAllowance
        self.lowerTempBound = self.setTemp + self.undertempAllowance
        logger.info(f"Shelf {self.channel+1} setpoint updated to {self.setTemp}°C (upper={self.upperTempBound}, lower={self.lowerTempBound})")

        self.lastSetpointChanged = time.time()
        temp = self.getTemp()
        self.tempAtLastSetpointChange = temp if temp is not None else 0


    def shelfToggle(self):
        if not self.isOn:
            self.turnOn()
        else:
            self.turnOff()


        logger.info(f"Shelf {self.channel+1} toggled - now {'ON' if self.isOn else 'OFF'}")
        
    def control(self, temp):
        if self.isOn:   
            logger.debug(f"Shelf {self.channel+1} control() called - temp={temp}, upper={self.upperTempBound}, lower={self.lowerTempBound}, isOn={self.isOn}") 
            #if temperature goes above the upper bound, it turns the heating element off
            if temp > self.upperTempBound:
                for relay in self.relayList:
                    if relay.role == "element" and relay.is_active:
                        logger.info(f"Shelf {self.channel+1} element turning OFF")
                        if self.elementTurnedOn is not None:
                            runtime = time.time() - self.elementTurnedOn
                            self.elementLife += runtime / 3600
                            self.elementTurnedOn = None
                        relay.off()
                    if relay.role == "fan" and not relay.is_active:
                        relay.on()
                        if self.fanLastOn is None:
                            self.fanLastOn = time.time()
                        logger.info("Fan was off, turning fan on")

            #if the temperature goes below the lower bound, it turns the heating elements on
            elif temp < self.lowerTempBound:
                for relay in self.relayList:
                    if relay.role == "fan" and not relay.is_active:
                        logger.warning(f"Shelf {self.channel+1} fan not running - forcing on")
                        self.fanLastOn = time.time() if self.fanLastOn is None else self.fanLastOn
                        relay.on()
                        
                    if relay.role == "element" and not relay.is_active:
                        logger.info(f"Shelf {self.channel+1} element turning ON")
                        if self.elementTurnedOn is None:
                            self.elementTurnedOn = time.time()
                        relay.on()