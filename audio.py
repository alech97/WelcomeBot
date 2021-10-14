import os
from datetime import datetime, time
from threading import Thread

import numpy as np
import pvporcupine

import soundfile
from pvrecorder import PvRecorder

import speech_recognition as sr #Speech Recognition and Audio
import numpy as np

def show_audio_devices():
    for i, dev in enumerate(PvRecorder.get_audio_devices()):
        print(f'[{i}]: {dev}')

def record_seconds(device_id, seconds = 3, sample_rate = 16_000, frame_length = 512):
    recorder = PvRecorder(device_index=device_id, frame_length=frame_length, 
        buffer_size_msec=1000, log_overflow=True)

    num_loops = (seconds * sample_rate) // frame_length
    frames = []

    recorder.start()
    for i in range(num_loops):
        frames.append(recorder.read())
    recorder.stop()
    recorder.delete()
    return frames

def write_audio(audio_frames, output_path, sample_rate = 16_000):
    recorded_audio = np.concatenate(audio_frames, axis=0).astype(np.int16)
    soundfile.write(output_path, recorded_audio, samplerate=sample_rate, subtype='PCM_16')
    print("Saved audio to file:", output_path)

class WakeThread(Thread):
    """
    It creates an input audio stream from a microphone and optionally await a wake word or listen for audio.
    """

    def __init__(
            self,
            callback=lambda keyword: print('[%s] Detected %s' % (str(datetime.now()), keyword)),
            library_path=pvporcupine.LIBRARY_PATH,
            model_path=pvporcupine.MODEL_PATH,
            keyword_paths=[pvporcupine.KEYWORD_PATHS['jarvis']],
            sensitivities=[0.5],
            input_device_index=None,
            output_path=None):

        """
        Constructor.
        :param library_path: Absolute path to Porcupine's dynamic library.
        :param model_path: Absolute path to the file containing model parameters.
        :param keyword_paths: Absolute paths to keyword model files.
        :param sensitivities: Sensitivities for detecting keywords. Each value should be a number within [0, 1]. A
        higher sensitivity results in fewer misses at the cost of increasing the false alarm rate. If not set 0.5 will
        be used.
        :param input_device_index: Optional argument. If provided, audio is recorded from this input device. Otherwise,
        the default audio input device is used.
        :param output_path: If provided recorded audio will be stored in this location at the end of the run.
        """

        super(WakeThread, self).__init__()

        self._callback = callback
        self._library_path = library_path
        self._model_path = model_path
        self._keyword_paths = keyword_paths
        self._sensitivities = sensitivities
        self._input_device_index = input_device_index

        self._output_path = output_path
        if self._output_path is not None:
            self._recorded_frames = []

    def run(self):
        """
         Creates an input audio stream, instantiates an instance of Porcupine object, and monitors the audio stream for
         occurrences of the wake word(s). It prints the time of detection for each occurrence and the wake word.
         """

        keywords = list()
        for x in self._keyword_paths:
            keyword_phrase_part = os.path.basename(x).replace('.ppn', '').split('_')
            if len(keyword_phrase_part) > 6:
                keywords.append(' '.join(keyword_phrase_part[0:-6]))
            else:
                keywords.append(keyword_phrase_part[0])

        porcupine = None
        recorder = None
        result = None

        #Wait for speech to begin and adjust for background noise
        self.voice_threshold = 4
        self.threshold_alpha = 0.8
        self.pause_threshold = 2
        self.silent_threshold = 1.2
        self.timeout_seconds = 10

        keyword_reached = False
        seconds_silent = 0

        try:
            porcupine = pvporcupine.create(
                library_path=self._library_path,
                model_path=self._model_path,
                keyword_paths=self._keyword_paths,
                sensitivities=self._sensitivities)

            recorder = PvRecorder(device_index=self._input_device_index, frame_length=porcupine.frame_length)
            recorder.start()

            print(f'Listening on device {recorder.selected_device} (')
            for keyword, sensitivity in zip(keywords, self._sensitivities):
                print('  %s (%.2f)' % (keyword, sensitivity))
            print(')')

            # num_loops = (seconds * SRATE) / FRAME_LENGTH
            # num_loops = seconds / seconds_per_loop
            # seconds / seconds_per_loop = (seconds * SRATE) / FRAME_LENGTH
            # 1 / seconds_per_loop = SRATE / FRAME_LENGTH
            # seconds_per_loop = FRAME_LENGTH / SRATE
            seconds_per_loop = porcupine.frame_length / porcupine.sample_rate
            alpha = self.threshold_alpha ** (1 / seconds_per_loop) #Adjust alpha to compensate for number of loops needed for 1s

            total_seconds = 0
            while True:
                pcm = recorder.read() #Read in audio buffer

                result = porcupine.process(pcm)
                if result >= 0:
                    keyword_reached = True
                    print('[%s] Detected %s' % (str(datetime.now()), keywords[result]))
                    print("Voice Threshold set to:", self.voice_threshold)
                
                amplitude = np.mean(np.abs(np.array(pcm, dtype=np.int16)))
                log_amplitude = np.log(amplitude)

                # print(f"Amplitude: {amplitude:.2f}, Log Amplitude: {log_amplitude:.2f}, Seoncds Silent: {seconds_silent:.2f}")
                
                #Record frames
                if keyword_reached:
                    self._recorded_frames.append(pcm)

                    total_seconds += seconds_per_loop

                    #If amplitude falls below voice threshold, count as silent
                    if log_amplitude < self.voice_threshold * self.silent_threshold:
                        seconds_silent += seconds_per_loop
                    else:
                        seconds_silent = 0

                    #Print Debug output each second of audio
                    if int(total_seconds - seconds_per_loop) != int(total_seconds):
                        print(f"Total Seconds: {total_seconds:.2f}, Amplitude (log): {log_amplitude:.2f}, Seconds Silent: {seconds_silent:.2f}")
                    
                    #If we have reached timeout or remained silent for logner than pause_threshold, then end
                    if total_seconds > self.timeout_seconds or seconds_silent > self.pause_threshold:
                        break

                #Else continue listening to background audio
                else:
                    #Adjust voice threshold to adjust to background noise
                    self.voice_threshold = (log_amplitude * alpha) + (self.voice_threshold * (1 - alpha))

        except KeyboardInterrupt:
            print('Stopping ...')
            
        finally:
            if porcupine is not None:
                porcupine.delete()

            if recorder is not None:
                recorder.delete()

            #Call back
            print("Listening Resources deleted, calling back...")
            self._callback(keywords[result], self._recorded_frames)

            if self._output_path is not None and len(self._recorded_frames) > 0:
                write_audio(self._recorded_frames, self._output_path, sample_rate = porcupine.sample_rate)

class ListenInputThread(Thread):
    """
    It creates an input audio stream from a microphone and listen for a spoken input until timeout stops
    """

    def __init__(
            self,
            callback = lambda keyword: print('[%s] Detected %s' % (str(datetime.now()), keyword)),
            timeout_seconds = 3,
            input_device_index = None,
            output_path = 'data/logs/latest_input.wav'):

        """
        Constructor.
        :param input_device_index: Optional argument. If provided, audio is recorded from this input device. Otherwise,
        the default audio input device is used.
        :param output_path: If provided recorded audio will be stored in this location at the end of the run.
        """

        super(WakeThread, self).__init__()

        self._callback = callback
        self._timeout_seconds = timeout_seconds
        self._input_device_index = input_device_index
        self._output_path = output_path

        self._recorded_frames = []

    def run(self):
        """Creates an input audio stream and listens until timeout."""
        recorder = None

        try:
            recorder = PvRecorder(device_index=self._input_device_index, frame_length=512)
            recorder.start()

            seconds = 0
            while True:
                pcm = recorder.read() #Read in audio buffer
                
                self._recorded_frames.append(pcm)

                seconds += 1
                if seconds > self._timeout_seconds:
                    break

        except KeyboardInterrupt:
            print('Stopping ...')
            
        finally:
            if recorder is not None:
                recorder.delete()
            
            self._callback(self._recorded_frames)

            if self._output_path is not None and len(self._recorded_frames) > 0:
                write_audio(self._recorded_frames, self._output_path)