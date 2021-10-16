import os
import json
# import azure.cognitiveservices.speech as speechsdk

from azure.cognitiveservices.speech import SpeechSynthesizer

class SpeechManager:
    """Controls spoken response behavior and speaker threads."""

    def __init__(self, speech_log_file_name = 'data/speech_log.json',
                 output_device_index = 0, speaker = True):

        self._output_device_index = output_device_index
        self._speaker = speaker
        self._speech_log_file_name = speech_log_file_name

        if not os.path.exists(speech_log_file_name):
            with open(speech_log_file_name, 'w') as f:
                json.dump({}, f)
        
        with open(speech_log_file_name, 'r') as f:
            self.speech_log = json.load(f)
            print('[Speech Log]', self.speech_log)
    
    def speak(self, text):
        print("[Response]", text)

        #If we are outputting sound to the speaker
        if self._speaker:
            #If this text has already been received from Azure before
            if text in self.speech_log:
                self.play_audio_from_file(self.speech_log[text])
            else:
                #Synthesize audio
                #Play to speaker
                # 
                #Write to file
                #Record in guest log
                #Overwrite guest log

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
       