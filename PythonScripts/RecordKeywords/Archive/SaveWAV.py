import serial
import wave
import os
import time

SERIAL_PORT = '/dev/tty.usbmodem1201'  # e.g., '/dev/cu.usbmodem14101' or 'COM3'
BAUD_RATE = 1000000
OUTPUT_DIR = "/Users/andreabettini/Documents/Native Instruments/Maschine 2/Projects/Soundsaber/Keywords/dataset"

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
CHANNELS = 1
RECORD_DURATION_MS = 1500

AUDIO_BYTES_PER_RECORDING = int(SAMPLE_RATE * (RECORD_DURATION_MS / 1000.0) * SAMPLE_WIDTH)

def get_next_sequence_number(directory, keyword):
    max_num = -1

    if not os.path.exists(directory):
        return 0

    for filename in os.listdir(directory):
        if filename.startswith(f"{keyword}_") and filename.endswith(".wav"):
            try:
                num = int(filename.replace(".wav", "").split("_")[-1]) # Extract the number after the last underscore
                if num > max_num:
                    max_num = num
            except ValueError:
                pass

    return max_num + 1

# ----------------------------------------------------------------------------------- SETUP
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

try:
    arduino = serial.Serial(SERIAL_PORT,BAUD_RATE,timeout=5)
    print(f"Connected to Arduino on {SERIAL_PORT}")
except Exception as e:
    print(f"Error connecting to port {SERIAL_PORT}: {e}")
    exit()

print("\n--- DATASET BUILDER ---")
print("Enter the keywords you want to cycle through, separated by commas.")
print("Example: Light, Jedi, Sith, Darkness, Noise")

raw_input_keywords = input("Keywords: ")
keywords = [word.strip() for word in raw_input_keywords.split(",") if word.strip()] # .strip removes whitespace, but keeps them
# So, the if statement filters out empty entries

if not keywords:
    print("No valid keywords entered. Exiting.")
    arduino.close()
    exit()

targets = {}

print("\nEnter the target number of total samples needed for each keyword:")

for kw in keywords:
    while True:
        try:
            target = int(input(f"Target count for '{kw}': ")) # choose how many samples you want for each keyword
            if target <= 0:
                print("Please enter a positive integer.")
                continue
            targets[kw] = target
            break
        except ValueError:
            print("Please enter a valid integer.")

print("\nConfiguration loaded!")

counts = {kw: get_next_sequence_number(OUTPUT_DIR, kw) for kw in keywords} # used to determine how many samples are already there
for kw in keywords:
    print(f"  - {kw}: current progress {counts[kw]}/{targets[kw]}") 

def get_next_keyword_index(start_index):
    for i in range(len(keywords)):
        idx = (start_index + i) % len(keywords) #  when start_index reaches the end of the list, it wraps around to the beginning 
        if counts[keywords[idx]] < targets[keywords[idx]]:
            return idx                                      # if the current keyword count is less than the target, return the index of that keyword
    return None                                             # otherwise, return None if all keywords (starting from the one at start_index) have reached their target counts

current_keyword_index = get_next_keyword_index(0) # first iteration starts with the first keyword,
if current_keyword_index is None:                 # but if all the keywords already have all the samples, stop here.
    print("\n🎉 All keywords have already reached their target sample counts! Exiting.")
    arduino.close()
    exit()

# ------------------------------------------------------------------------------------------MAIN LOOP

print("\nLook at the Arduino LED. Watch the prompt below to know WHICH word to say next!")
print("Press Ctrl+C at any time to save and quit.\n")
time.sleep(2) # give the user a moment to read the instructions before starting

arduino.reset_input_buffer()
arduino.write(b"STARTSESSION\n") # requires \n because arduino is using .readStringUntil('\n')

first_kw = keywords[current_keyword_index]
print(
    f"👉 NEXT UP: Say '{first_kw}' "
    #f"(Will save as {first_kw}_{counts[first_kw]:03d}.wav | "
    f"Progress: {counts[first_kw]}/{targets[first_kw]})"
)

try:
    while True:
        line = arduino.readline()

        if b"RECORD_NOW" not in line:
            continue # continue is used to restart the loop. This way, ignore any lines that don't contain the "RECORD_NOW" signal

        active_keyword = keywords[current_keyword_index]
        file_num = counts[active_keyword]

        print(
            f" 🔴 RECORDING NOW: '{active_keyword}'... "
            f"({file_num + 1}/{targets[active_keyword]})"
        )

        audio_data = arduino.read(AUDIO_BYTES_PER_RECORDING)

        if len(audio_data) != AUDIO_BYTES_PER_RECORDING:
            print(
                f"⚠ Incomplete recording received "
                f"({len(audio_data)}/{AUDIO_BYTES_PER_RECORDING} bytes). Skipping."
            )
            continue

        arduino.readline() # Arduino will still send the "STOP" byte. Read it to clear the buffer for the next recording

        filepath = os.path.join(
            OUTPUT_DIR,
            f"{active_keyword}_{file_num:03d}.wav" # creates the filename with the keyword and a zero-padded number (e.g., Lightsaber_001.wav)
        )

        with wave.open(filepath, 'wb') as wav_file: #same as wav_file = wave.open(filepath, 'wb'), ..., and then wav_file.close(). Creates a .wav file
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(SAMPLE_WIDTH)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(audio_data)

        counts[active_keyword] += 1

        print(f" ✅ Saved: {active_keyword}_{file_num:03d}.wav")

        current_keyword_index = get_next_keyword_index(
            (current_keyword_index + 1) % len(keywords)
        )

        if current_keyword_index is None:
            print("\n🎉 SUCCESS! All keywords have successfully reached their target counts.")
            break

        next_kw = keywords[current_keyword_index]

        print(
            f"👉 NEXT UP: Get ready to say '{next_kw}' "
            f"(Will save as {next_kw}_{counts[next_kw]:03d}.wav | "
            f"Progress: {counts[next_kw]}/{targets[next_kw]})"
        )

except KeyboardInterrupt:
    print("\nSession paused.")

finally:
    arduino.write(b"ENDSESSION\n")
    arduino.flush()
    arduino.close()
    print("Progress saved safely. Check your 'dataset' folder!")