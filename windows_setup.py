"""
windows_setup.py

Originally from ThorLabs (https://www.thorlabs.com/software-pages/ThorCam), modified to allow inputting of the DLL
directory manually.

In order for the Thorlabs Python examples to work, they need visibility of the directory containing the Thorlabs TSI
Native DLLs. This setup function changes the PATH environment variable (Just for the current process, not the system
PATH variable) by adding the directory containing the DLLs. This function is written specifically to work for the
Thorlabs Python SDK examples on Windows, but can be adjusted to work with custom programs. Changing the PATH variable
of a running application is just one way of making the DLLs visible to the program. The following methods could
be used instead:

- Use the os module to adjust the program's current directory to be the directory containing the DLLs.
- Manually copy the DLLs into the working directory of your application.
- Manually add the path to the directory containing the DLLs to the system PATH environment variable.

"""

import os
import sys

def configure_path(custom_dll_directory):
    """
    Configures the system PATH and Python DLL directory using a provided path.
    :param custom_dll_directory: The relative or absolute path to the DLL folder.
    """
    # 1. Convert the input to a reliable absolute path
    # If the user provides a relative path, this anchors it to the script's location
    base_dir = os.path.dirname(os.path.abspath(__file__))
    absolute_path = os.path.abspath(os.path.join(base_dir, custom_dll_directory))

    # 2. Check if the directory actually exists before proceeding
    if not os.path.isdir(absolute_path):
        print(f"Warning: The directory {absolute_path} does not exist.")
        return

    # 3. Update the System PATH
    # We prepend it so the OS looks here FIRST
    os.environ['PATH'] = absolute_path + os.pathsep + os.environ['PATH']

    # 4. Handle Python 3.8+ specific requirements
    try:
        os.add_dll_directory(absolute_path)
    except AttributeError:
        # This function doesn't exist in Python < 3.8, so we skip it
        pass
        
    print(f"Successfully added DLL directory: {absolute_path}")

# Example Usage:
# configure_path('../my_custom_dlls')