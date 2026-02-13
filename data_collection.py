"""
ELECTROSPRAY DATA COLLECTION PROGRAM

This program is designed to collect and record the live data from electrospray
test set-up. This is also designed to allow the inputting of the desired 
control voltage.

You will need to have the ThorCam software installed for this to work for
the camera connectivity.

Created on Thu Feb 12 14:53:11 2026

@author: euandh
"""
# IMPORT LIBRARIES

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



"""
------------------- DATA LOGGING -------------------
"""

# Start data collection for inputs
ai_task.timing.cfg_samp_clk_timing(sample_rate, sample_mode=AcquisitionType.CONTINUOUS)       # Could use the source input (for the sample clock) to ensure the sample rate clock is using the sample rate clock from my laptop rather than from the device (the DAQ chassis I presume?)




ai_task.stop()
ao_task.stop()