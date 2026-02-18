"""
ELECTROSPRAY CONTROL AND DATA COLLECTION PROGRAM

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

# Generic Python Libraries
import numpy as np
import time
import sys
import csv
import datetime

# GUI Libaries
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, QLineEdit,
                             QDoubleSpinBox, QSpinBox, QTextEdit, QFileDialog,
                             QGroupBox, QGridLayout, QDialog, QFormLayout,
                             QDialogButtonBox)
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot, Qt, QSettings
import pyqtgraph as pg
from collections import deque

# National Instruments Libraries
import nidaqmx
from nidaqmx.constants import AcquisitionType, READ_ALL_AVAILABLE
from nidaqmx import stream_readers
from nidaqmx import stream_writers
from nidaqmx import constants

# ThorLabs and Camera/Image Libraries
import windows_setup   # This is Thorlabs windows set-up code    
import tifffile
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK
from thorlabs_tsi_sdk.tl_mono_to_color_processor import MonoToColorProcessorSDK
from thorlabs_tsi_sdk.tl_camera_enums import SENSOR_TYPE
import imagecodecs

# --- WORKER THREAD 1: CAMERA CONTROL ---
class CameraWorker(QThread):
    image_ready = pyqtSignal(object)  # Sends numpy array
    log_message = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.is_running = False
        self.camera = None
        self.sdk = None
        
        # Settings
        self.exposure_time_us = 2000 # 2ms default timeout
        self.trigger_mode = "Hardware"
        self.ROI = [4096, 3000] # Full sensor
        self.filepath = ""

    def run(self):
        self.is_running = True
        self.log_message.emit("Camera: Initializing SDK...")
        
        try:
            # 1. Initialize SDK & Camera
            self.DLL_dr = "C:\Program Files\Thorlabs\Scientific Imaging\ThorCam"

            try:
                windows_setup.configure_path(self.DLL_dr)
            except ImportError:
                configure_path = None
            
            self.sdk = TLCameraSDK()
            available_cameras = self.sdk.discover_available_cameras()
            
            if not available_cameras:
                self.log_message.emit("Camera: No cameras found!")
                return
            
            self.camera = self.sdk.open_camera(available_cameras[0])
            
            # 2. Configure Camera
            self.camera.exposure_time_us = self.exposure_time_us
            self.camera.image_poll_timeout_ms = 1000 # Wait 1s for a frame
            
            if self.trigger_mode == "Hardware":
                self.camera.operation_mode = 1
                self.camera.frames_per_trigger_zero_for_unlimited = 1
            else:
                self.camera.operation_mode = 0
                self.camera.frames_per_trigger_zero_for_unlimited = 0
            
            self.camera.arm(2) # 2 frames buffer
            
            self.log_message.emit(f"Camera: Armed ({self.camera.name} in {self.trigger_mode} mode.)")

            # 3. Continuous Loop
            # Trigger first frame if in Software mode
            if self.trigger_mode == "Software":
                self.camera.issue_software_trigger()

            while self.is_running:
                frame = self.camera.get_pending_frame_or_null()
                
                if frame:
                    # 1. RESHAPE (CRITICAL STEP)
                    # The SDK gives a flat list. We must force it into a 2D rectangle.
                    image_data = frame.image_buffer.reshape(
                        self.camera.image_height_pixels, 
                        self.camera.image_width_pixels
                    )
                    
                    # 2. Make a copy (Safety for threading)
                    final_image = np.copy(image_data)
                    
                    # 3. Emit
                    self.image_ready.emit(final_image)
                    
                    # Saving logic...
                    if self.filepath:
                        # tifffile handles the shape automatically
                        tifffile.imwrite(self.filepath, final_image, append=True)

                    if self.trigger_mode == "Software":
                        self.camera.issue_software_trigger()

        except Exception as e:
            self.log_message.emit(f"Camera Error: {e}")
            
        finally:
            if self.camera:
                self.camera.disarm()
                self.camera.dispose()
            if self.sdk:
                self.sdk.dispose()
            self.log_message.emit("Camera: Closed.")

    def stop(self):
        self.is_running = False
        self.wait()

# --- WORKER THREAD 2: NI DAQ CONTROL ---
class DAQWorker(QThread):
    data_ready = pyqtSignal(float, float) # Sends (Voltage, Current)
    log_message = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.is_running = False
        
        # Initialise set-up variables
        self.filepath = "data.csv"
        self.sample_rate = 4e-3 
        
        # Initialise control variables
        self.target_voltage = 0.0
        self.polarity_mode = 0
        self.high_time = 1 
        
        # Initialise modules
        self.ai_channel_name = "cDAQ9185-2023AF4Mod1"
        self.ao_channel_name = "cDAQ9185-2023AF4Mod2"
        self.ai_channels_to_use = [0, 1]
        self.ao_channels_to_use = [0]
        self.ai_lims = [-10, 10]
        self.ao_lims = [-10, 10]
        
        # Define channels for purposes
        self.ao_map = {}
        self.ai_map = {}

    def set_voltage(self, val):
        self.target_voltage = val
        
    def set_hightime(self, val):
        self.high_time = val
        
    def set_polarity_mode(self, val):
        self.polarity_mode = val

    def run(self):
        self.is_running = True
        
        # 1. Create Tasks
        self.ai_task = nidaqmx.Task()
        self.ao_task = nidaqmx.Task()

        try:
            # --- SETUP PHASE: Build the Channel Maps ---
            
            # Lists to ensure we write/read in the exact order NI expects
            self.ai_ordered_functions = [] 
            self.ao_ordered_functions = []
            
            # CSV Headers start with Timestamp
            csv_headers = ["Timestamp"]

            # --- A. Setup AI Channels (Sorted Order) ---
            sorted_ai = sorted(self.ai_channels_to_use)
            for chan_idx in sorted_ai:
                # Add physical channel
                self.ai_task.ai_channels.add_ai_voltage_chan(
                    f"{self.ai_channel_name}/ai{chan_idx}", 
                    min_val=self.ai_lims[0], max_val=self.ai_lims[1]
                )
                
                # Identify function (e.g. "Matsusada read in")
                func_name = "Unknown"
                # Look for this index in the map values
                for name, mapped_idx in self.ai_map.items():
                    if int(mapped_idx) == chan_idx:
                        func_name = name
                        break
                
                self.ai_ordered_functions.append(func_name)
                csv_headers.append(f"{func_name} (AI{chan_idx})")
                
            self.log_message.emit(f"AI Configured: {self.ai_ordered_functions}")

            # --- B. Setup AO Channels (Sorted Order) ---
            sorted_ao = sorted(self.ao_channels_to_use)
            for chan_idx in sorted_ao:
                # Add physical channel
                self.ao_task.ao_channels.add_ao_voltage_chan(
                    f"{self.ao_channel_name}/ao{chan_idx}", 
                    min_val=self.ao_lims[0], max_val=self.ao_lims[1]
                )
                
                # Identify function (e.g. "Matsusada control")
                func_name = "Unknown"
                for name, mapped_idx in self.ao_map.items():
                    if int(mapped_idx) == chan_idx:
                        func_name = name
                        break
                        
                self.ao_ordered_functions.append(func_name)
                csv_headers.append(f"{func_name} (AO{chan_idx})")
                
            self.log_message.emit(f"AO Configured: {self.ao_ordered_functions}")

            # --- C. Initialize CSV ---
            # Create file with the dynamic headers
            with open(self.filepath, mode='w', newline='') as f:
                csv.writer(f).writerow(csv_headers)
            
            self.log_message.emit("DAQ Started. Logging data...")

            # --- D. Initialize Timing Variables ---
            last_switch_time = time.time()
            is_high_state = True

            # --- E. MAIN LOOP ---
            with open(self.filepath, mode='a', newline='') as f:
                writer = csv.writer(f)
                
                while self.is_running:
                    now = time.time()
                    
                    # --------------------------------------
                    # 1. CALCULATE OUTPUTS (Logic Block)
                    # --------------------------------------
                    
                    # Check if in a switching mode
                    if self.polarity_mode != "Unipolar constant":
                        # Check if it's time to switch
                        if (now - last_switch_time) >= self.high_time:
                            is_high_state = not is_high_state # toggle state
                            last_switch_time = now
                    else:
                        is_high_state = True # Always "high" if constant
                        
                    ao_data_out = []
                    
                    for func in self.ao_ordered_functions:
                        val_to_write = 0.0
                        
                        if func == "Matsusada control":
                            # Apply positive voltage if in high state
                            if is_high_state:
                                val_to_write = self.target_voltage/1000 # Convert to scaled control voltage
                            else:
                                # Apply the negative voltage if in low state in bipolar
                                if self.polarity_mode == "Bipolar switching":
                                    val_to_write = -1 * self.target_voltage/1000
                                # Apply zero if in unipolar switching
                                elif self.polarity_mode == "Unipolar switching":
                                    val_to_write = 0.0
                                else:
                                    val_to_write = 0.0
                                    self.log_message.emit(f"NO MATCHING POLARITY MODE: {self.polarity_mode}")
                        elif func == "Camera control":
                            trigger_period = 0.1 # 100ms
                            if (now % trigger_period) < (trigger_period / 2):
                                val_to_write = 5.0 # High (Trigger)
                            else:
                                val_to_write = 0.0 # Low (Reset)
                         
                        
                        #self.log_message.emit(f"AO Voltage: {val_to_write}")
                        ao_data_out.append(val_to_write)

                    # WRITE AO (if channels exist)
                    if ao_data_out:
                        self.ao_task.write(ao_data_out)

                    # --------------------------------------
                    # 2. READ INPUTS
                    # --------------------------------------
                    
                    # Read all AI channels at once
                    # Returns a list of floats, e.g. [0.004, 2.5]
                    if self.ai_channels_to_use:
                        ai_data_in = self.ai_task.read()
                        
                        # Handle single channel case (nidaq returns float, not list)
                        if not isinstance(ai_data_in, list):
                            ai_data_in = [ai_data_in]
                    else:
                        ai_data_in = []

                    # --------------------------------------
                    # 3. LOGGING & UPDATE
                    # --------------------------------------
                    
                    # Construct CSV Row: Timestamp + Inputs + Outputs
                    row_data = [datetime.datetime.now()] + ai_data_in + ao_data_out
                    writer.writerow(row_data)
                    
                    # Update GUI Display
                    # We need to find the "Meaningful" values to send to the UI
                    # (e.g. Find which channel is Voltage and which is Current)
                    display_volts = 0.0
                    display_current = 0.0
                    
                    for i, func in enumerate(self.ai_ordered_functions):
                        if func == "Matsusada read in":
                            # Convert 5V back to 5000V for display
                            display_volts = ai_data_in[i] * 1000 
                        elif "current" in func.lower():
                            display_current = ai_data_in[i]

                    # Emit signal to GUI
                    self.data_ready.emit(display_volts, display_current)
                    
                    # Pace the loop
                    time.sleep(self.sample_rate)

        except Exception as e:
            self.log_message.emit(f"DAQ Runtime Error: {e}")
            print(e) # Print to console for debugging

        finally:
            # CLEANUP
            self.log_message.emit("Stopping DAQ tasks...")
            
            try:
                # Zero the outputs for safety
                if self.ao_channels_to_use:
                    zero_list = [0.0] * len(self.ao_channels_to_use)
                    self.ao_task.write(zero_list)
                
                self.ao_task.stop()
                self.ao_task.close()
                self.ai_task.stop()
                self.ai_task.close()
            except Exception as e:
                print(f"Cleanup error: {e}")
                
            self.log_message.emit("DAQ resources released.")

    def stop(self):
        self.is_running = False
        self.wait()

# --- HARDWARE CONFIGURATION DIALOGUE ---
class HardwareConfigDialog(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hardware and Channel Settings")
        self.resize(600, 300) # Made it wider to fit side-by-side
        
        self.config = current_config
        
        # Main Layout (Vertical)
        self.main_layout = QVBoxLayout(self)
        self.intro_text = QLabel("Input the module names (as listed in NI MAX), and then select what each channel is connected to from the dropdowns. If nothing is connected, then leave the channel as 'None'.")
        self.intro_text.setWordWrap(True)
        self.main_layout.addWidget(self.intro_text)
        
            # Columns Layout (Horizontal)
            # This sits inside the main layout and puts AI and AO side-by-side
        self.columns_layout = QHBoxLayout()
        self.main_layout.addLayout(self.columns_layout)
        
                # LEFT COLUMN: AI Settings
        self.group_AI = QGroupBox("Analogue Inputs")
        self.layout_AI = QGridLayout()
        self.group_AI.setLayout(self.layout_AI)
        
                    # Device Name Input (CRITICAL: You need this for the NI DAQ to work)
        self.input_device_ai = QLineEdit(self.config.get("ai_device", "cDAQ9185-2023AF4Mod1"))
        self.layout_AI.addWidget(QLabel("Device Name:"), 0, 0)
        self.layout_AI.addWidget(self.input_device_ai, 0, 1)

                    # Channel Dropdowns
        self.AI_options = ["None", "Matsusada read in", "Current collector", "Extractor current"]
                    # Store these in a list so we can access them easily later
        self.ai_combos = []
        
                    # Load in saved options
        saved_ai_map = self.config.get("ai_map", {})
        
        for i in range(4): # Cycle through the saved map and update the combo box with aligned values
            lbl = QLabel(f"AI {i}")
            combo = QComboBox()
            combo.addItems(self.AI_options)
            
            for name, channel_idx in saved_ai_map.items():
                if int(channel_idx) == i:
                    combo.setCurrentText(name)
                    break
            
            self.ai_combos.append(combo)
            self.layout_AI.addWidget(lbl, i+1, 0)
            self.layout_AI.addWidget(combo, i+1, 1)

                    # Add the GROUP BOX to the layout (not the inner layout)
        self.columns_layout.addWidget(self.group_AI)

        # RIGHT COLUMN: AO Settings
        self.group_AO = QGroupBox("Analogue Outputs")
        self.layout_AO = QGridLayout()
        self.group_AO.setLayout(self.layout_AO)

            # Device Name Input
        self.input_device_ao = QLineEdit(self.config.get("ao_device", "cDAQ9185-2023AF4Mod2"))
        self.layout_AO.addWidget(QLabel("Device Name:"), 0, 0)
        self.layout_AO.addWidget(self.input_device_ao, 0, 1)

            # Channel Dropdowns
        self.AO_options = ["None", "Matsusada control", "Camera control"]
        self.ao_combos = []
        
        saved_ao_map = self.config.get("ao_map", {})

        for i in range(4): # Cycle through and pre-fill from saved options
            lbl = QLabel(f"AO {i}")
            combo = QComboBox()
            combo.addItems(self.AO_options)
            
            for name, channel_idx in saved_ao_map.items():
                if int(channel_idx) == i:
                    combo.setCurrentText(name)
                    break

            self.ao_combos.append(combo)
            self.layout_AO.addWidget(lbl, i+1, 0)
            self.layout_AO.addWidget(combo, i+1, 1)

            # Add the GROUP BOX to the layout
        self.columns_layout.addWidget(self.group_AO)

        # BOTTOM: OK / Cancel Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.save_and_close)
        self.buttons.rejected.connect(self.reject)
        
        self.main_layout.addWidget(self.buttons)

    def save_and_close(self):
        # 1. Save Device Names
        self.config["ai_device"] = self.input_device_ai.text()
        self.config["ao_device"] = self.input_device_ao.text()
        
        # 2. Build the Channel Lists AND the Name Mapping
        active_ao_channels = []
        ao_map = {} # New Dictionary: {"Matsusada": 0, "Camera": 1}
        
        for i, combo in enumerate(self.ao_combos):
            name = combo.currentText()
            if name != "None":
                active_ao_channels.append(str(i))
                # Map the functional name to the channel index
                ao_map[name] = i 
                
        # Save simple list for the DAQ setup
        self.config["ao_channels"] = ", ".join(active_ao_channels)
        
        # Save the map for the Worker logic
        self.config["ao_map"] = ao_map 
        
        # (Do the same for AI if you need to read specific inputs by name)
        active_ai_channels = []
        ai_map = {}
        for i, combo in enumerate(self.ai_combos):
            name = combo.currentText()
            if name != "None":
                active_ai_channels.append(str(i))
                ai_map[name] = i
                
        self.config["ai_channels"] = ", ".join(active_ai_channels)
        self.config["ai_map"] = ai_map

        self.accept()

# --- MAIN GUI WINDOW ---
class ElectrosprayUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Electrospray Control and Data Acquisition")
        self.resize(1200, 800)

        # PyQtGraph Settings
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        # Start set-up of layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.centralWidget())

        # Row 1: Control box
        self.top_controls_group = QGroupBox("Global Controls")
        self.top_controls_group.setFixedHeight(80)
        self.controls_layout = QHBoxLayout()
        self.top_controls_group.setLayout(self.controls_layout)
        
            # Boxes
        self.btn_start = QPushButton("Start Acquisition")
        self.btn_start.clicked.connect(self.start_system)
        
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_system)

        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Current Collection Only",\
                                  "Camera and Current Collection"])

        self.controls_layout.addWidget(self.btn_start)
        self.controls_layout.addWidget(self.btn_stop)
        self.controls_layout.addWidget(self.combo_mode)
        self.controls_layout.addStretch()        # Push everything left
        
        self.main_layout.addWidget(self.top_controls_group)
        
        
        # Row 2: Settings (Static Settings | Live Control)
        self.settings_layout = QHBoxLayout()
        
            # LEFT: Static Settings
        self.group_static_settings = QGroupBox("Data Collection Settings")
        self.static_set_layout = QGridLayout()
        self.group_static_settings.setLayout(self.static_set_layout)
        
                # FPS
        self.input_fps = QDoubleSpinBox()
        self.input_fps.setValue(10)
        self.input_fps.setRange(0, 914.4)
        self.input_fps.setSuffix(" FPS")
                # ROI
        self.input_ROI_width = QSpinBox()
        self.input_ROI_width.setMaximum(4096)        
        self.input_ROI_width.setValue(4096)        
        self.input_ROI_width.setSuffix(" px")  
        self.input_ROI_height = QSpinBox()
        self.input_ROI_height.setMaximum(3000)
        self.input_ROI_height.setValue(3000)
        self.input_ROI_height.setSuffix(" px")
                # Filepath
        self.input_filepath = QLineEdit()
        self.input_filepath.setPlaceholderText("Enter filepath to folder for data logging here...")
                # Sample rate
        self.input_sample_rate = QDoubleSpinBox()
        self.input_sample_rate.setValue(40)
        self.input_sample_rate.setSuffix(" ms")
        self.input_sample_rate.setMinimum(0)
        self.input_sample_rate.setSingleStep(10)

                # Add all widgets
        self.static_set_layout.addWidget(QLabel("Frame rate:"), 0, 0)
        self.static_set_layout.addWidget(self.input_fps, 0, 1, 1, 4)
        
        self.static_set_layout.addWidget(QLabel("Region of interest:"), 1, 0)
        self.static_set_layout.addWidget(QLabel("Width:"), 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
        self.static_set_layout.addWidget(self.input_ROI_width, 1, 2)
        self.static_set_layout.addWidget(QLabel("Height:"), 1, 3, alignment=Qt.AlignmentFlag.AlignRight)
        self.static_set_layout.addWidget(self.input_ROI_height, 1, 4, )
        
        self.static_set_layout.addWidget(QLabel("Save directory:"), 2, 0)
        self.static_set_layout.addWidget(self.input_filepath, 2, 1, 1, 4)
        
        self.static_set_layout.addWidget(QLabel("Sample rate:"), 3, 0)
        self.static_set_layout.addWidget(self.input_sample_rate, 3, 1, 1, 4)

            # RIGHT: Rolling/live inputs
        self.group_live_settings = QGroupBox("Live Settings")
        self.live_set_layout = QGridLayout()
        self.group_live_settings.setLayout(self.live_set_layout)
        
                # Voltage Control Spinner
        self.input_voltage = QDoubleSpinBox()
        self.input_voltage.setSuffix(" V")
        self.input_voltage.setRange(-5000, 5000)
        self.input_voltage.setSingleStep(10)
        self.input_voltage.valueChanged.connect(self.update_DAQ_voltage)
                # High time
        self.input_high_time = QDoubleSpinBox()
        self.input_high_time.setSuffix(" s")
        self.input_high_time.setMinimum(0)
        self.input_high_time.valueChanged.connect(self.update_DAQ_hightime)
                # Polarity mode
        self.input_polarity_mode = QComboBox()
        self.input_polarity_mode.addItems(["Bipolar switching", "Unipolar switching", "Unipolar constant"])
        self.input_polarity_mode.currentIndexChanged.connect(self.update_DAQ_polarity_mode)

                # Add all widgets
        self.live_set_layout.addWidget(QLabel("Emitter voltage: "), 0, 0)
        self.live_set_layout.addWidget(self.input_voltage, 0, 1)
        
        self.live_set_layout.addWidget(QLabel("High time:"), 1, 0)
        self.live_set_layout.addWidget(self.input_high_time, 1, 1)
        
        self.live_set_layout.addWidget(QLabel("Polarity mode:"), 2, 0)
        self.live_set_layout.addWidget(self.input_polarity_mode, 2, 1)
        
            # MAKE WHOLE ROW: Add both groups to the layout
        self.settings_layout.addWidget(self.group_static_settings)
        self.settings_layout.addWidget(self.group_live_settings)
        
        self.main_layout.addLayout(self.settings_layout)

        # Row 3: Live feeds (Camera Feed | Plot Feed)
        self.feeds_layout = QHBoxLayout()
        
            # LEFT: Camera Feed (placeholder)
        self.group_cam_feed = QGroupBox("Camera Feed")
        self.cam_feed_layout = QVBoxLayout()
        self.group_cam_feed.setLayout(self.cam_feed_layout)
        
            # Create imageview
        # view=pg.PlotItem() hides the histogram/ROI tools by default for a cleaner look
        self.cam_view = pg.ImageView(view=pg.PlotItem()) 
        self.cam_view.ui.roiBtn.hide()        # Hide the "ROI" button
        self.cam_view.ui.menuBtn.hide()       # Hide the "Menu" button
        self.cam_view.ui.histogram.hide()     # Hide Histogram (CPU heavy, enable if needed)
        self.cam_view.getView().getAxis('left').hide()
        self.cam_view.getView().getAxis('bottom').hide()
        self.cam_view.getView().setAspectLocked(True)
        #self.cam_view.getView().setMenuEnabled(False) # Disable right-click menu
        #self.cam_view.getView().setMouseEnabled(x=True, y=True) # Keep zoom/pan
        
        self.cam_feed_layout.addWidget(self.cam_view)

            # RIGHT: Plot feed (placeholder)
        self.group_plots = QGroupBox("Voltage and Current Plots")
        self.plots_layout = QVBoxLayout()
        self.group_plots.setLayout(self.plots_layout)
        
                # Plot window
                    # Set-up the rolling window data
        self.plot_max_points = 300      # How many points to plot at once
        self.data_time = deque(maxlen = self.plot_max_points)
        self.data_voltage = deque(maxlen = self.plot_max_points)
        self.data_current = deque(maxlen = self.plot_max_points)
        self.start_time = time.time()
        
                    # Graph widget set-up
        self.graph_widget = pg.GraphicsLayoutWidget()
        self.voltage_colour = "#1f77b4"
        self.collector_current_colour = "#ff7f0e"
        # (Next colours in the T10 sequence are: #2ca02c, #d62728, #9467bd, #8c564b)
        
                    # Plot 1 - Voltage (measured)
        self.plot_V = self.graph_widget.addPlot(row = 0, col = 0)
        self.legend = self.plot_V.addLegend(offset = (10, 10))
        self.legend.setBrush(pg.mkBrush(255, 255, 255, 150))
        self.plot_V.setLabel("left", "Voltage", units = "V")
        self.curve_V = self.plot_V.plot(pen = pg.mkPen(self.voltage_colour, width = 2), name = "Voltage")
        self.plot_V.setLabel("bottom", "Time", units = "s")
        
                    # Plot 2 - Collector current
        self.view_current = pg.ViewBox()
        self.plot_V.scene().addItem(self.view_current)
        self.plot_V.getAxis("right").linkToView(self.view_current)
        self.view_current.setXLink(self.plot_V)
        self.plot_V.showAxis("right")
        self.plot_V.getAxis("right").setLabel("Current", units = "A")
        self.curve_I = pg.PlotCurveItem(pen = pg.mkPen(self.collector_current_colour, width = 2))
        self.view_current.addItem(self.curve_I)
        self.legend.addItem(self.curve_I, "Collector current")
        
        def update_views():
            # Function to update the view box to match the first (voltage)
            self.view_current.setGeometry(self.plot_V.vb.sceneBoundingRect())
            self.view_current.linkedViewChanged(self.plot_V.vb, self.view_current.XAxis)
        
        self.plot_V.vb.sigResized.connect(update_views)
        
                    # Add graphs to layout
        self.plots_layout.addWidget(self.graph_widget)
        
                # Log Window
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(100)
        self.plots_layout.addWidget(self.log_box)
        
            # BUILD WHOLE ROW
        self.feeds_layout.addWidget(self.group_cam_feed, stretch = 1)
        self.feeds_layout.addWidget(self.group_plots, stretch = 1)
        self.main_layout.addLayout(self.feeds_layout, stretch = 2)

        # Initialize Workers
        self.cam_worker = CameraWorker()
        self.daq_worker = DAQWorker()

        # Connect Signals (Worker -> GUI)
        self.cam_worker.log_message.connect(self.append_log)
        self.cam_worker.image_ready.connect(self.update_image_display) # You need to write this function
        self.daq_worker.data_ready.connect(self.update_daq_display)
        self.daq_worker.log_message.connect(self.append_log)


        # Recall previous settings values
        self.settings = QSettings("config.ini", QSettings.Format.IniFormat)
        
            # restore values
                # filepath
        self.input_filepath.setText(self.settings.value("filepath", ""))
        self.input_fps.setValue(float(self.settings.value("fps", 10.0)))
                # ROI
        self.input_ROI_width.setValue(int(self.settings.value("roi_w", 4096)))
        self.input_ROI_height.setValue(int(self.settings.value("roi_h", 3000)))   
                # Voltage Controls
        self.input_voltage.setValue(float(self.settings.value("voltage", 0.0)))
        self.input_high_time.setValue(float(self.settings.value("high_time", 1.0)))
        self.input_polarity_mode.setCurrentIndex(int(self.settings.value("polarity_idx", 0)))
        
        self.hw_config = {
            "ai_device": self.settings.value("ai_device", "cDAQ9185-2023AF4Mod1"),
            "ai_channels": self.settings.value("ai_channels", "0, 1"),
            "ao_device": self.settings.value("ao_device", "cDAQ9185-2023AF4Mod2"),
            "ao_channels": self.settings.value("ao_channels", "0, 1"),
            # Load maps if they exist, else empty dict
            "ai_map": self.settings.value("ai_map", {}),
            "ao_map": self.settings.value("ao_map", {})
        }

        # Menu Bar and Hardware Config Menu/Dialogue
        self.menubar = self.menuBar()
        self.config_menu = self.menubar.addMenu("Configuration")
        
            #actions
        action_hardware = self.config_menu.addAction("Hardware connections...")
        action_hardware.triggered.connect(self.open_hardware_config)

    def start_system(self):
        # UI Updates
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.combo_mode.setEnabled(False)
        self.append_log("System Starting...")
        
        # Create timestamp linked filename
        self.filenametime = time.strftime("ESPRAY_%Y-%m-%d_%H%M")
        
        # Lock inputs
        self.input_fps.setEnabled(False)
        self.input_filepath.setEnabled(False)
        self.input_sample_rate.setEnabled(False)
        
        # Clear buffers (for plot)
        self.data_time.clear()
        self.data_voltage.clear()
        self.data_current.clear()
        self.start_time = time.time()
        
        # Check if camera is in use
        if "Camera" in self.combo_mode.currentText():
            use_cam = True
            self.cam_worker.trigger_mode = "Hardware"
            self.append_log("Mode: Camera + DAQ") 
        else:
            use_cam = False
            self.append_log("Mode: DAQ Only (Camera OFF)") 
    
        # Pass settings to workers
            # Cam worker
        if use_cam == True:
            self.cam_worker.filepath = f"{self.input_filepath.text()}/{self.filenametime}_IMAGES.tiff"
            self.cam_worker.ROI = [self.input_ROI_width.value(), self.input_ROI_height.value()]
            # Daq worker
        self.daq_worker.filepath = f"{self.input_filepath.text()}/{self.filenametime}_DATA.csv"
        
        self.inputted_fps = self.input_fps.value()
        self.inputted_filepath = self.input_filepath.text()
        
        # Parse Configuration from Settings
        ai_str = self.hw_config.get("ai_channels", "")   # Using .get() to avoid crashes if keys are missing
        ao_str = self.hw_config.get("ao_channels", "")

        try:
            # Split by comma, strip whitespace, and ignore empty strings
            # This handles "0, 1" AND "" safely.
            
            if ai_str.strip():
                ai_chans = [int(x.strip()) for x in ai_str.split(',') if x.strip()]
            else:
                ai_chans = [] # Empty list if string is empty

            if ao_str.strip():
                ao_chans = [int(x.strip()) for x in ao_str.split(',') if x.strip()]
            else:
                ao_chans = []
                
        except ValueError:
            self.append_log("Error parsing channels! Check config format.")
            self.btn_start.setEnabled(True) 
            return

            # Update workers
        self.daq_worker.ai_channel_name = self.hw_config["ai_device"]
        self.daq_worker.ao_channel_name = self.hw_config["ao_device"]
        self.daq_worker.ai_channels_to_use = ai_chans 
        self.daq_worker.ao_channels_to_use = ao_chans
        self.daq_worker.ao_map = self.hw_config.get("ao_map", {}) 
        self.daq_worker.ai_map = self.hw_config.get("ai_map", {})
        
        # Force update to live settings
        self.daq_worker.set_voltage(self.input_voltage.value())
        self.daq_worker.set_hightime(self.input_high_time.value())
        self.daq_worker.set_polarity_mode(self.input_polarity_mode.currentText())
        
        # Start Threads
        if use_cam == True:
            self.cam_worker.start()
        self.daq_worker.start()
        
            
    def closeEvent(self, event):
        """
        Runs automatically when the user clicks 'X'.
        """
        
        # Safety Check: Is the experiment still running?
        if self.daq_worker.is_running or self.cam_worker.is_running:
            self.stop_system() # Force a safe shutdown of hardware
            time.sleep(0.5)    # Give threads a tiny moment to close file handles
            
        # Save all settings to file
        self.settings.setValue("filepath", self.input_filepath.text())
        self.settings.setValue("fps", self.input_fps.value())
        self.settings.setValue("roi_w", self.input_ROI_width.value())
        self.settings.setValue("roi_h", self.input_ROI_height.value())
        self.settings.setValue("voltage", self.input_voltage.value())
        self.settings.setValue("high_time", self.input_high_time.value())
        self.settings.setValue("polarity_idx", self.input_polarity_mode.currentIndex())
        
        # Save Hardware Config
        self.settings.setValue("ai_device", self.hw_config.get("ai_device"))
        self.settings.setValue("ai_channels", self.hw_config.get("ai_channels"))
        self.settings.setValue("ao_device", self.hw_config.get("ao_device"))
        self.settings.setValue("ao_channels", self.hw_config.get("ao_channels"))
        self.settings.setValue("ai_map", self.hw_config.get("ai_map"))
        self.settings.setValue("ao_map", self.hw_config.get("ao_map"))
        
        # Close up
        event.accept()

    def update_DAQ_voltage(self, value):
        self.daq_worker.set_voltage(value)
        
    def update_DAQ_hightime(self, value):
        self.daq_worker.set_hightime(value)
        
    def update_DAQ_polarity_mode(self, value):
        text = self.input_polarity_mode.currentText()
        self.daq_worker.set_polarity_mode(text)

    def open_hardware_config(self):
        # Pass the dictionary to the dialog so it can read/write to it
        dialog = HardwareConfigDialog(self.hw_config, self)
        if dialog.exec():
            self.append_log("Hardware configuration updated.")
            self.append_log(f"Current AI Device: {self.hw_config['ai_device']}")
            self.append_log(f"Current AO Device: {self.hw_config['ao_device']}")

    def stop_system(self):
        self.append_log("Stopping...")
        self.cam_worker.stop()
        self.daq_worker.stop()
        
        # unlock inputs
        self.input_fps.setEnabled(True)
        self.input_filepath.setEnabled(True)
        self.input_sample_rate.setEnabled(True)
        
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.combo_mode.setEnabled(True)

    @pyqtSlot(str)
    def append_log(self, text):
        self.log_box.append(text)

    @pyqtSlot(object)
    def update_image_display(self, image_array):
        # Transpose to fix rotation (Cameras scan differently than screens)
        display_data = image_array.T

        # AUTO-RANGE LOGIC
        # If the view is empty (first frame), Force Zoom-to-Fit
        if self.cam_view.image is None:
            self.cam_view.setImage(display_data, autoLevels=True, autoRange=True)
            # Optional: Set a fixed brightness range (e.g. 0 to 200 for dim signals)
            # self.cam_view.setLevels(0, 255)
        else:
            # Afterwards, keep user's zoom/pan
            self.cam_view.setImage(display_data, autoLevels=False, autoRange=False)
            
    @pyqtSlot(float, float)
    def update_daq_display(self, volts, amps):
        # Update plots
        t = time.time() - self.start_time
        self.data_time.append(t)
        self.data_voltage.append(volts)
        self.data_current.append(amps)
        
        self.curve_V.setData(list(self.data_time), list(self.data_voltage))
        self.curve_I.setData(list(self.data_time), list(self.data_current))
        
        #self.voltage_placeholder_text.setText(f"Voltage: {volts:.2f} V | Current: {amps:.6f} A")

# --- APP ENTRY POINT ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ElectrosprayUI()
    window.show()
    sys.exit(app.exec())