# -*- coding: utf-8 -*-
"""
Created on Fri Feb 13 13:05:07 2026

@author: edh1g18
"""

import os
import tifffile
import windows_setup
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
from thorlabs_tsi_sdk.tl_mono_to_color_processor import MonoToColorProcessorSDK
from thorlabs_tsi_sdk.tl_camera_enums import SENSOR_TYPE
import time
import imagecodecs

DLL_dr = "C:/Program Files/Thorlabs/Scientific Imaging/ThorCam"
output_dr = "C:/Users/edh1g18/localfiles/test files"
filename = "test.tiff"
#output_dr = "C:/Users/edh1g18/OneDrive - University of Southampton/Visualisation Work/Data Logging Software/test_outputs"

# Custom TIFF tags
tags = {
    "bitdepth": 32768,
    "exposure": 32769,
    "hardware_timestamp": 32770
    }

try:
    # if on Windows, use the provided setup script to add the DLLs folder to the PATH
    from windows_setup import configure_path
    configure_path(DLL_dr)
except ImportError:
    configure_path = None
    
# Open camera
sdk = TLCameraSDK()
cameras = sdk.discover_available_cameras()
camera = sdk.open_camera(cameras[0])

# Camera Initialisation
camera.frame_rate_control_value = 10

# Camera conditions
camera.frames_per_trigger_zero_for_unlimited = 0
camera.operation_mode = 0           # 0 for software triggered, 1 for hardware triggered.
camera.image_poll_timeout_ms = 2000 # Camera will timeout error after 2 s
camera.arm(10)

# save these values to place in our custom TIFF tags later
bit_depth = camera.bit_depth
exposure = camera.exposure_time_us

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
        
        
# Tear down - close all relevant instances
if 'image_data' in locals():
    del image_data
    
print("Manually closing camera...")
camera.disarm()
print("Camera Disarmed")
camera.dispose() # Explicitly tell the SDK to free camera resources
del camera

print("Manually closing SDK...")
sdk.dispose() # Explicitly tell the SDK to shut down its threads
del sdk