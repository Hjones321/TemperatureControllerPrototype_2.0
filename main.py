import time
from Logger import get_logger
from deviceManager import DeviceManager as deviceManager
import serial


PORT = "/dev/ttyACM0"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=0.1)
time.sleep(2)

print("[CONNECTION SUCCESS]")

logger = get_logger()

def send(msg):
    ser.write((msg+ "\n").encode())
    
def read():
    while ser.in_waiting:
        line = ser.readline().decode(errors="ignore").strip()
        if line:
            handle(line)
            
def handle(msg):
    if msg.startswith("SET:"):
        setpoint = int(msg.split(":")[1])
        print(f"[SETPOINT UPDATED] new setpoint: {setpoint}")

running = True




def mainLoop():
    dm = deviceManager()
    dm.addAllShelves(1)
    while running:
        read()
        time.sleep(1)
        temp = dm.controlLoop()
        send(f"LIVE_TEMP:{temp}")

    
def main(args):
    
    mainLoop()
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main(sys.argv))

