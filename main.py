import time
from Logger import get_logger
from deviceManager import DeviceManager as deviceManager
import serial
import threading 
from BarcodeManager import handleBarcodeInput


PORT = "/dev/ttyACM0"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=0.1)
time.sleep(2)



logger = get_logger()

logger.info(f"[INFO] Serial link on port - {PORT} - established")

def barcodeReader():
    global barcodeValue
    while True:
        code = input()
        barcodeValue = code
        logger.debug(f"[DEBUG] scanned: {code}")

def send(msg):
    ser.write((msg+ "\n").encode())
    logger.info(f"[INFO] Sent message - {msg}")
    
def read():
    while ser.in_waiting:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            logger.info(f"[INFO] Received data serially - {line}")
            handle(line)
            
def handle(msg):
    if msg.startswith("SET:"):
        setpoint = int(msg.split(":")[1])
        logger.info(f"[INFO] new setpoint: {setpoint}")

running = True




def mainLoop():
    dm = deviceManager()
    dm.addAllShelves(1)
    

    dm.start()

    t = threading.Thread(target=barcodeReader, daemon= True)
    t.start()
    logger.debug("[DEBUG] Barcode input handler thread started")
    while running:

        if barcodeValue:
            handleBarcodeInput(barcodeValue)
            

        read()
        time.sleep(1)
        temps = dm.controlLoop()
        
        
        send(f"LIVE_TEMP:{temps[0]}")
        logger.debug(f"[DEBUG] Sent live temperature - {temps[0]}")

    
def main(args):
    logger.debug("[DEBUG] Main loop started")
    mainLoop()
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))

