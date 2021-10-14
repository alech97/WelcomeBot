from audio import WakeThread, ListenInputThread, record_seconds, write_audio
from visual import capture_face, GuestManager

import azure.cognitiveservices.speech as speechsdk
import numpy as np

class Responses:
    UNKNOWN_COMMAND = "Sorry, I couldn't quite understand what you wanted from me."
    TAKE_MY_PHOTO = "Sure, please look into my camera so I can take a good look at you."
    ASK_FOR_NAME = "It's nice to meet a new face!  What's your name?"

class CommandsParser:
    """Handles logic related to parsing commands given by the user."""

    def __init__(self, commands_file='commands.context'):
        command_lines = open(commands_file, 'r').readlines()

        self.commands = {}
        curr_command = None
        for line in command_lines:
            line = line.strip()
            print(line, curr_command)
            if line.endswith(':'):
                curr_command = line[:-1]
                self.commands[curr_command] = set()
            elif line.startswith('- '):
                assert curr_command is not None
                self.commands[curr_command].add(line[2:])
        
        print("Commands being used:", self.commands)

    def parse(self, text):
        """Parses a given string of text for a command and returns the command."""
        if text is not None:
            print("Parsing text:", text)
            text = ''.join([c.lower() for c in text if str.isalnum(c) or str.isspace(c)])

            #For command, {set of all prompts which map to the command}
            for command, prompts in self.commands.items():
                #For all prompts, check if it is constained in text
                for prompt in prompts:
                    if prompt in text:
                        print("Found command:", command)
                        return command
        
        #If no command is found or no text is received, return no result
        print("Found no commands in:", text)
        return None

class WelcomeBot:
    """
    Jarvis Welcome bot object which handles listening, speaking, and picture 
    capturing behavior.    
    """

    def __init__(self,
                 commands_file_name = 'commands.context',
                 guest_log_file_name = 'data/guest_log.json',
                 audio_input_device_index = None,
                 audio_output_device_index = None,
                 camera_device_index = None,
                 azure_speech_config = None):
        
        #Store device configurations
        self._audio_input_device_index = audio_input_device_index
        self._audio_output_device_index = audio_output_device_index
        self._camera_device_index = camera_device_index
        self._azure_speech_config = azure_speech_config

        #Create Listening Thread instance
        self.wake_thread = WakeThread(
            callback = lambda keyword, audio_frames: self._run_callback(keyword, audio_frames),
            input_device_index=audio_input_device_index,
            output_path='data/logs/latest_speech.wav'
        )

        #Create Commands Parser for interpeting user language
        self.commands_parser = CommandsParser(commands_file = commands_file_name)

        #Create Guest Manager for managing all faces stored
        self.guest_manager = GuestManager(guest_log_file_name)

    def run(self):
        """Begin running the bot by spawning a WakeThread."""
        self.wake_thread.run()
    
    def _run_callback(self, keyword, audio_frames):
        """Once woken up, take remaining audio and interpret."""
        #Interpret speech using Azure
        text = self.azure_speech_recognition(audio_frames)

        #Parse text using WelcomeBot's commands
        self.parse_text(text)
    
    def parse_text(self, text):
        #If no text was received from Azure, then TTS "Sorry, I couldn't quite understand what you wanted from me."
        command = self.commands_parser.parse(text)

        #If no command was received, inform the user
        if command is None:
            return self.azure_speech_synthesis(Responses.UNKNOWN_COMMAND)
        #Otherwise, execute WelcomeBot's command
        else:
            try:
                func = getattr(self, command)
                func()
            except AttributeError as e:
                print("Command wasn't found in WelcomeBot:", command)
    
    def recognizeMe(self):
        """Take a photo of the user and try to recognize them from the past."""
        #TODO

    def takeMyPhoto(self):
        """Take a photo of the user and store in database under their name."""
        #Ask user for their name
        self.azure_speech_synthesis(Responses.ASK_FOR_NAME)

        #If not using WSL, can convert this section to azure speech's listen_once_async()
        audio_frames = record_seconds(self._audio_input_device_index, seconds=3)
        
        #Ask user to position themselves for the camera
        self.azure_speech_synthesis(Responses.TAKE_MY_PHOTO)

        #Take photo of user
        frame = capture_face(self._camera_device_index)

        #Try to interpet user name (#TODO)
        name = self.azure_speech_recognition(audio_frames)

        #Store guest into the database
        self.guest_manager.add_guest(frame, audio_frames, name)

    def azure_speech_recognition(self, audio_frames):
        print("Writing Audio to Stream: ", len(audio_frames), "frames")
        
        channels = 1
        bitsPerSample = 16
        samplesPerSecond = 16000
        audioFormat = speechsdk.audio.AudioStreamFormat(samplesPerSecond, bitsPerSample, channels)
        custom_push_stream = speechsdk.audio.PushAudioInputStream(stream_format=audioFormat)
        audio_config = speechsdk.audio.AudioConfig(stream=custom_push_stream)

        #Write audio_frames to stream
        for frames in audio_frames:
            custom_push_stream.write(np.array(frames, dtype='int16').tobytes())
        custom_push_stream.close()

        speech_recognizer = speechsdk.SpeechRecognizer(speech_config=self._azure_speech_config, audio_config=audio_config)

        print("Sending voice data to Azure...")
        result = speech_recognizer.recognize_once_async().get()

        # Check the result
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            print("Recognized: {}".format(result.text))
            return result.text
        elif result.reason == speechsdk.ResultReason.NoMatch:
            print("No speech could be recognized")
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print("Speech Recognition canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print("Error details: {}".format(cancellation_details.error_details))
    
    def azure_speech_synthesis(self, text):
        """Upload text to Azure and output response to speaker"""
        #Speech synthesizer using the default speaker as audio output.
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self._azure_speech_config, 
            audio_config=speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
        )

        # Receives a text from console input and synthesizes it to speaker.
        result = speech_synthesizer.speak_text_async(text).get()
        # Check result
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print(f"Speech synthesized to speaker for text: {text}")
            result_stream = speechsdk.AudioDataStream(result)

            #Write to file here and save sentence which was sent to file
            #TODO
            result_stream.save_to_wav_file('data/logs/latest_tts.wav')
            
            #Add to list of sentences spoken
            #TODO
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print("Speech synthesis canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print("Error details: {}".format(cancellation_details.error_details))

        