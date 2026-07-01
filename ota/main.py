#-------------------------------------------------------------------------------
# Print version and set Boot safety flag and get Board serial number
#-------------------------------------------------------------------------------
VERSION = "2.0.1"
print("Hello from main.py - version: ",VERSION)

try:
    with open("update_failed.flag", "w") as f:
        f.write("1")
except Exception:
    pass

#-------------------------------------------------------------------------------
# Imports
#-------------------------------------------------------------------------------
from fidl_esp32 import *
from fidl_lte import *
from fidl_gps import *
from fidl_comms import *
from fidl_ota import *
import os
import time

#-------------------------------------------------------------------------------
# Define TimeoutError if it's not built-in (MicroPython quirk)
#-------------------------------------------------------------------------------
try:
    TimeoutError
except NameError:
    class TimeoutError(Exception):
        pass

#-------------------------------------------------------------------------------
# Global variables and Main functionality
#-------------------------------------------------------------------------------
BASE = "https://bitflow92.co.za:38649"
SSID = 'Study'
PASSWORD = 'w00dh1ll'
    
phone_number = "+27829029275"
api_key = "5222964"
apn = "internet"
SMS_center = "+2781191"
    
FROM_DEBUG = True
                
wifi_on = False
rst_modem  = False
init_modem = False
init_gps = False
gps_hot_start = False
send_sms = False
send_whatsapp_message = False
post_battery_data_lte = False
post_battery_data_wifi = False

#--------------------------------------------------------
# Wake-up source : DEBUG Flag set
#--------------------------------------------------------
if FROM_DEBUG:
    print("DEBUG")
    if power_on(): print("OK") # Power-on LTE module
    flash_led(3,0.25) # Flash LED 3 times at 1/4 second speed
   
    # Actions to be executed in Debug mode  
    wifi_on = True
        
    count = 1
    print("Count = ", count)
    led.on()     # Switch-on test LED
    wake_mpu()   # Wake-up MPU

#--------------------------------------------------------
# Wake-up source : From Deep Sleep
#--------------------------------------------------------
elif FROM_DEEPSLEEP:
    print("FROM DEEP SLEEP")
    if power_on(): print("OK") # Power-on LTE module
    flash_led(3,0.5) # Flash LED 3 times at 1/2 second speed
            
    # Actions to be executed from Deep Sleep
    post_battery_data_lte = True
        
    state = load_state()
    count = int(state.get("count", 0))
    count += 1
    print("Count = ", count)
    state["count"] = count
    save_state(state)
    gps_pwr.value(1)  # Enable GPS power
    led.on()          # Switch-on test LED
    wake_mpu()        # Wake-up MPU

#--------------------------------------------------------
# Wake-up source : From Power On
#--------------------------------------------------------
else:
    print("FROM POWER ON")
    if power_on(): print("OK") # Power-on LTE module
    flash_led(3,1) # Flash LED 3 times at 1 second speed
            
    # Actions to be executed from Power On
    rst_modem  = True
    init_modem = True
    init_gps = True
    send_sms = True
    send_whatsapp_message = True
    post_battery_data_lte = True
        
    state = load_state()
    count = 1
    print("Count = ", count)
    state["count"] = count
    save_state(state)
    gps_pwr.value(1)  # Enable GPS power
    led.on()          # Switch-on test LED
    wake_mpu()        # Wake-up MPU

#-------------------------------------------------------------------------------
# Boot successful up to this point: clear rollback flag and print board ID
#-------------------------------------------------------------------------------
try:
    os.remove("update_failed.flag")
except Exception:
    pass

print("Board serial number : ",read_board_serial_number())

#-------------------------------------------------------------------------------
# Execute Actions
#-------------------------------------------------------------------------------
if wifi_on: connect_wifi(SSID, PASSWORD)     
if rst_modem: print(reset_modem())
if init_modem: initialize_modem(apn, SMS_center)
if init_gps: initialize_gps(gps_hot_start)
if init_modem: read_modem_info()
if send_sms: send_SMS(phone_number, "FIDL Reset and Initialise OK")
if send_whatsapp_message: send_whatsapp(phone_number, api_key, "FIDL Reset and Initialise OK")
    
if post_battery_data_wifi:
    time_string = get_time_from_ntp_sa()
    voltage = str(read_voltage())
    temperature = str(read_temperature())
    # Pack into JSON string
    payload = ujson.dumps({
        "count": count,
        "time": time_string,
        "battery": voltage,
        "temperature": temperature,
        "version": VERSION})
    print("=================================================================================")
    print("JSON payload:", payload)
    print("=================================================================================")
    send_https_wifi(payload) # Send JSON payload via WiFi
            
    led.value(0) # 1=high and 0=low
            
    print("\nPutting MPU-6050 into sleep...")
    sleep_mpu()

    # How long to sleep (in milliseconds)
    #SLEEP_MS = 1800000  # 30 minutes
    SLEEP_MS = 10000  # 10 seconds

    print("Going into hibernation for", SLEEP_MS/1000, "seconds...")

    # Configure a timer wake-up
    machine.deepsleep(SLEEP_MS)
    
if post_battery_data_lte:
    time_string = get_time_from_modem()
    voltage = str(read_voltage())
    temperature = str(read_temperature())
    # Pack into JSON string
    payload = ujson.dumps({
        "count": count,
        "time": time_string,
        "battery": voltage,
        "temperature": temperature,
        "version": VERSION})
    print("=================================================================================")
    print("JSON payload:", payload)
    print("=================================================================================")
    send_https(payload) # Send JSON payload via A7670e
            
    if power_off(): led.value(0) # 1=high and 0=low
    led.value(0) # 1=high and 0=low
    
    print("\nPutting MPU-6050 into sleep...")
    sleep_mpu()

    # How long to sleep (in milliseconds)
    #SLEEP_MS = 1800000  # 30 minutes
    SLEEP_MS = 10000  # 10 seconds

    print("Going into hibernation for", SLEEP_MS/1000, "seconds...")

    # Configure a timer wake-up
    machine.deepsleep(SLEEP_MS)
        
#-------------------------------------------------------------------------------
# Debug Loop
#-------------------------------------------------------------------------------

print("🔍 Checking for firmware update...")
try:
    #updated, info = check_and_update_lte(BASE, VERSION, "main.py") # OTA via LTE
    updated, info = check_and_update_wifi(BASE, VERSION, "main.py") # OTA via wifi
    print("OTA:", info)
    # if update happens, ESP32 resets automatically
except Exception as e:
    print("⚠️ OTA periodic check failed:", e)
 