from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import math

# Get default audio device using PyCAW
devices = AudioUtilities.GetSpeakers()
interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
volume = cast(interface, POINTER(IAudioEndpointVolume))

def get_current_volume():
    # Returns current volume in decibels
    return volume.GetMasterVolumeLevel()

def volume_up(decibels=1.5):
    try:
        current_volume = get_current_volume()
        volume.SetMasterVolumeLevel(current_volume + decibels, None)
    except:
        pass

def volume_down(decibels=1.5):
    volume_up(-decibels)