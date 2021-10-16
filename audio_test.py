from audio import show_audio_devices, record_seconds, WakeThread
import pyaudio

show_audio_devices()

wt = WakeThread(input_device_index = 2)
wt.run()