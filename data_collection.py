"""
ELECTROSPRAY DATA COLLECTION PROGRAM

┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│███████╗██╗     ███████╗ ██████╗████████╗██████╗  ██████╗ ███████╗██████╗ ██████╗  █████╗ ██╗   ██╗│
│██╔════╝██║     ██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔═══██╗██╔════╝██╔══██╗██╔══██╗██╔══██╗╚██╗ ██╔╝│
│█████╗  ██║     █████╗  ██║        ██║   ██████╔╝██║   ██║███████╗██████╔╝██████╔╝███████║ ╚████╔╝ │
│██╔══╝  ██║     ██╔══╝  ██║        ██║   ██╔══██╗██║   ██║╚════██║██╔═══╝ ██╔══██╗██╔══██║  ╚██╔╝  │
│███████╗███████╗███████╗╚██████╗   ██║   ██║  ██║╚██████╔╝███████║██║     ██║  ██║██║  ██║   ██║   │
│╚══════╝╚══════╝╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   │
│                                                                                                   │
│██████╗  █████╗ ████████╗ █████╗     ██╗      ██████╗  ██████╗  ██████╗ ███████╗██████╗            │
│██╔══██╗██╔══██╗╚══██╔══╝██╔══██╗    ██║     ██╔═══██╗██╔════╝ ██╔════╝ ██╔════╝██╔══██╗           │
│██║  ██║███████║   ██║   ███████║    ██║     ██║   ██║██║  ███╗██║  ███╗█████╗  ██████╔╝           │
│██║  ██║██╔══██║   ██║   ██╔══██║    ██║     ██║   ██║██║   ██║██║   ██║██╔══╝  ██╔══██╗           │
│██████╔╝██║  ██║   ██║   ██║  ██║    ███████╗╚██████╔╝╚██████╔╝╚██████╔╝███████╗██║  ██║           │
│╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝    ╚══════╝ ╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝╚═╝  ╚═╝           │
└───────────────────────────────────────────────────────────────────────────────────────────────────┘

This program is designed to collect and record the live data from electrospray
test set-up. This is also designed to allow the inputting of the desired 
control voltage.

You will need to have the ThorCam software installed for this to work for
the camera connectivity.

Created on Thu Feb 12 14:53:11 2026

@author: euandh
"""

"""
------------------- IMPORTING LIBRARIES -------------------
"""

# Generic Python Libraries
import numpy as np

# National Instruments Libraries
import nidaqmx
from nidaqmx.constants import AcquisitionType, READ_ALL_AVAILABLE
from nidaqmx import stream_readers
from nidaqmx import stream_writers
from nidaqmx import constants

# ThorLabs Libraries
import windows_setup   # This is Thorlabs windows set-up code    
import tifffile
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
from thorlabs_tsi_sdk.tl_mono_to_color_processor import MonoToColorProcessorSDK
from thorlabs_tsi_sdk.tl_camera_enums import SENSOR_TYPE
import time
import imagecodecs

"""
------------------- FILE PATHS AND NAMES -------------------
"""
# Where to save data to
output_dr = "C:/Users/edh1g18/localfiles/test files"

# Image filename for tiff stack.
filename = "test.tiff"

"""
------------------- CONTROL VARIABLES -------------------
"""
cam_fps = 10



"""
------------------- NATIONAL INSTRUMENTS INITALISATION -------------------
"""

# Module initialisation for NI
sample_rate = 1         # Samples per channel per second (Hz)

ai_channel_name = "cDAQ9185-2023AF4Mod1"
ao_channel_name = "cDAQ9185-2023AF4Mod2"

ai_channels_to_use = [0, 1]
ao_channels_to_use = [0, 1]

ai_lims = [-10, 10]
ao_lims = [-10, 10]

# Create tasks for NI
ai_task, ao_task = nidaqmx.Task(), nidaqmx.Task()

# Add requested channels
for i in ai_channels_to_use:
    ai_task.ai_channels.add_ai_voltage_chan(ai_channel_name+f"/ai{i}", min_val= ai_lims[0], max_val = ai_lims[1])

for i in ao_channels_to_use:
    ao_task.ao_channels.add_ao_voltage_chan(ao_channel_name+f"/ao{i}", min_val= ao_lims[0], max_val = ao_lims[1])

"""
------------------- THORLABS INITALISATION -------------------
"""
DLL_dr = "C:\Program Files\Thorlabs\Scientific Imaging\ThorCam"

try:
    # if on Windows, use the provided setup script to add the DLLs folder to the PATH
    from windows_setup import configure_path
    configure_path(DLL_dr)
except ImportError:
    configure_path = None


# Custom tiff tags
tags = {
        "bitdepth": 32768,
        "exposure": 32769,
        "hardware_timestamp": 32770
        }

# Open camera
# (assuming the only available camera is the one you want to record from)
sdk = TLCameraSDK()
cameras = sdk.discover_available_cameras()
camera = sdk.open_camera(cameras[0])

# Initalise camera
camera.frame_rate_control_value = cam_fps #fps

# Camera conditions
camera.frames_per_trigger_zero_for_unlimited = 0
camera.operation_mode = 0           # 0 for software triggered, 1 for hardware triggered.
camera.image_poll_timeout_ms = 2000 # Camera will timeout error after 2 s
camera.arm(10)

# save these values to place in our custom TIFF tags later
bit_depth = camera.bit_depth
exposure = camera.exposure_time_us


"""
------------------- DATA LOGGING -------------------
"""

# Start data collection for inputs
ai_task.timing.cfg_samp_clk_timing(sample_rate, sample_mode=AcquisitionType.CONTINUOUS)       # Could use the source input (for the sample clock) to ensure the sample rate clock is using the sample rate clock from my laptop rather than from the device (the DAQ chassis I presume?)

# Start voltage outputting

# Start camera data logging
frames = 0
camera.issue_software_trigger()

# Acquisition loop
with tifffile.TiffWriter(output_dr+"/"+filename, append = True, bigtiff = True) as tiff:
    while frames < 100:
        frame = camera.get_pending_frame_or_null()
        if frame is None:
            raise TimeoutError("Timeout was reaching while polling for a frame.")
        
        hw_timestamp = frame.time_stamp_relative_ns_or_null//1000 # µs timestamp instead of ns.
        image_data = frame.image_buffer.copy()
        
        tiff.save(data = image_data,
                  compress = 'lzw',
                  extratags = [(tags["hardware_timestamp"], "Q", 1, hw_timestamp),
                               (tags["bitdepth"], "I", 1, bit_depth),
                               (tags["exposure"], "I", 1, exposure)])
        
        frames += 1
        

"""
------------------- TEAR DOWN -------------------
"""
print("-------------------------------\nStarting tear down...")

# Stop NI tasks
ai_task.stop()
ao_task.stop()

print("All National Instruments tasks closed succesfully.")

# Stop Thorlabs tasks
if 'image_data' in locals():
    del image_data
    
camera.disarm()
camera.dispose()
sdk.dispose()

print("All ThorLabs resources closed successfully.")

print("Tear down complete.\n-------------------------------")