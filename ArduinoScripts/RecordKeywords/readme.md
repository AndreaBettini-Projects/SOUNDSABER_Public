**RecordKeywords_upd.ino** is used to record your personal keyword dataset. <br>

It establishes serial communication with Arduino microphone and sends the recordings to Python. <br>
It works in combination with **SaveWAV_upd.py**, which catches the serial com and saves the recordings in structured folders, ready for ML pipeline (see repository tree on the general README.md)

Key parameters:
- RECORD_DURATION_MS = 1500 - chosen duration of keywords samples .wav
- PAUSE_DURATION_MS = 1500  - pause between recordings, for long but smooth recording sessions
