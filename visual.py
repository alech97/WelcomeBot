import os
import cv2
import json

from audio import write_audio
from deepface import DeepFace #Facial Recognition

def write_photo(file_name, frame):
    """Write a frame to a new filename"""
    cv2.imwrite(file_name, frame)

def capture_face(device_id = None):
    """Open a camera device and capture a photo"""
    cap = cv2.VideoCapture()

    if cap.isOpened():
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            return frame
        else:
            print("Frame was not returned")
    raise Exception("Could not capture photo.")

class GuestManager:
    """Manages the captured faces and names of stored guests."""

    def __init__(self, guest_log_file_name = 'data/guest_log.json'):
        self._guest_log_file_name = guest_log_file_name

        with open(self._guest_log_file_name, 'r', encoding='utf-8') as f:
            self.guests = json.load(f)
        
        print("Loaded Guests:", self.guests)
        
    def add_guest(self, face_frame, name_audio, name, sample_rate = 16_000):
        """
        Given the data for a new guest, add them to the system and 
        save corresponding data.
        """
        guest_id = len(self.guests)

        #Write Face to file in data/ and record
        face_file_name = os.path.join('data/faces', str(guest_id) + '.jpg')
        write_photo(face_file_name, face_frame)

        #Write Name Audio to file ind ata/ and record
        audio_file_name = os.path.join('data/names', str(guest_id) + '.wav')
        write_audio(name_audio, audio_file_name, sample_rate = sample_rate)

        #Record new guest in memory
        self.guests.append({
            'id': guest_id,
            'name': name,
            'audio_file_name': audio_file_name,
            'face_file_name': face_file_name
        })

        #Overwrite disk Guest Log with new updated guest
        with open(self._guest_log_file_name, 'w', encoding='utf-8') as f:
            json.dump(self.guests, f, ensure_ascii=False, indent=4)
