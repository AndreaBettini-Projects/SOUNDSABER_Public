import tkinter as tk
import serial
from audio_engine import AudioEngine
import math

# --- SERIAL SETUP ---
SERIAL_PORT = "XXXXXX" # insert your serial port name here e.g. "/device/cu.usbmodem1201"
BAUD_RATE = 1000000

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
except Exception as e:
    print(f"Warning: Could not open serial port {SERIAL_PORT}: {e}")
    ser = None


class SaberGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Lightsaber Control & Tuning Panel")
        self.root.geometry("1150x920")
        self.root.configure(bg="#1a1a1a")

        self.active_fx = 0
        self.performance_state = "IDLE"
        self.audio = AudioEngine()

        # --- MAIN LAYOUT FRAMES ---
        self.left_frame = tk.Frame(root, bg="#1a1a1a")
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=12)

        self.right_frame = tk.Frame(root, bg="#111111", highlightbackground="cyan", highlightthickness=1)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=12, pady=12)

        # ==================== LEFT PANEL ====================

        tk.Label(self.left_frame, text="SABER TELEMETRY & COMMAND TUNER", font=("Arial", 13, "bold"), fg="cyan", bg="#1a1a1a").pack(pady=2)

        self.fx_label = tk.Label(self.left_frame, text="FX0", font=("Arial", 13, "bold"), fg="#00ff00", bg="#1a1a1a")
        self.fx_label.pack(pady=2)

        self.state_label = tk.Label(self.left_frame, text="MODE: IDLE", font=("Arial", 13, "bold"), fg="#445dff", bg="#1a1a1a")
        self.state_label.pack(pady=2)

        # ==================== SMALL DOM PANEL ====================

        dom_frame = tk.LabelFrame(self.left_frame, text=" DOMINANCE / GATE ", fg="cyan", bg="#111111", font=("Arial", 9, "bold"))
        dom_frame.pack(fill=tk.X, pady=4)

        self.gate_indicator = tk.Label(dom_frame, text="GATE: CLOSED (Filtering)", font=("Arial", 9, "bold"), fg="red", bg="#111111")
        self.gate_indicator.pack(pady=2)

        self.dom_canvas_w = 300
        self.dom_canvas_h = 145
        self.dom_canvas = tk.Canvas(dom_frame, width=self.dom_canvas_w, height=self.dom_canvas_h, bg="#111111", highlightthickness=0)
        self.dom_canvas.pack(pady=2)

        self.peaks = {"X": 0.0, "Y": 0.0, "Z": 0.0}
        self.peak_timers = {"X": 0, "Y": 0, "Z": 0}

        # ==================== LEFT PANEL: Arduino Parameters ====================

        cmd_frame = tk.LabelFrame(self.left_frame, text=" Arduino Firmware Parameters ", fg="cyan", bg="#1a1a1a", font=("Arial", 11, "bold"))
        cmd_frame.pack(pady=4, fill=tk.BOTH, expand=True)

        self.entries = {}
        params = [
            ("v", "LIN_THRESH (v:)", "0.4"),
            ("p", "PRINT_INTERVAL (p:)", "20"),
            ("c", "CYCLES_REQ (c:)", "3"),
            ("t", "FLICK_THRESH (t:)", "100.0"),
            ("b", "BOOST_COEFF (b:)", "0.02"),
            ("r", "BLEEDER_RATE (r:)", "0.001"),
            ("d", "THRUST_DEADBAND (d:)", "2.0"),
            ("l", "LOCKOUT_TIME (l:)", "500"),
            ("f", "SMOOTHING_ALPHA (f:)", "0.12")
        ]

        for i, (key, label_txt, default_val) in enumerate(params):
            row = i // 2
            col = i % 2
            sub_f = tk.Frame(cmd_frame, bg="#1a1a1a")
            sub_f.grid(row=row, column=col, sticky="w", padx=8, pady=3)
            tk.Label(sub_f, text=label_txt, fg="white", bg="#1a1a1a", font=("Arial", 10), width=18, anchor="w").pack(side=tk.LEFT)
            ent = tk.Entry(sub_f, width=10, bg="#222222", fg="cyan", insertbackground="white", font=("Arial", 11))
            ent.insert(0, default_val)
            ent.bind("<Return>", lambda event, k=key: self.send_single_parameter(k))
            ent.pack(side=tk.RIGHT)
            self.entries[key] = ent

        tk.Button(self.left_frame, text="⚡ Send All Parameters to Arduino", command=self.send_parameters, bg="#004444", fg="white", font=("Arial", 11, "bold")).pack(pady=4, fill=tk.X)

        # ==================== SOUND PARAMETERS (PYTHON AUDIO) ====================

        sound_cmd_frame = tk.LabelFrame(self.left_frame, text=" Python Audio & Sound Parameters ", fg="magenta", bg="#1a1a1a", font=("Arial", 11, "bold"))
        sound_cmd_frame.pack(pady=4, fill=tk.BOTH, expand=True)

        self.sound_entries = {}
        sound_params = [
            ("gd", "GRAIN_DUR (s):", "0.5"),
            ("gn", "GRAIN_INT (s):", "0.05"),
            ("gl", "GLIDE FACTOR:", "0.35"),
            ("res", "RESONANCE (%):", "40.0")
        ]

        for i, (key, label_txt, default_val) in enumerate(sound_params):
            row = i // 2
            col = i % 2
            sub_f = tk.Frame(sound_cmd_frame, bg="#1a1a1a")
            sub_f.grid(row=row, column=col, sticky="w", padx=8, pady=3)
            tk.Label(sub_f, text=label_txt, fg="white", bg="#1a1a1a", font=("Arial", 11), width=16, anchor="w").pack(side=tk.LEFT)
            ent = tk.Entry(sub_f, width=8, bg="#222222", fg="magenta", insertbackground="white", font=("Arial", 11))
            ent.insert(0, default_val)
            ent.bind("<Return>", lambda event: self.send_sound_parameters())
            ent.pack(side=tk.RIGHT)
            self.sound_entries[key] = ent

        tk.Button(self.left_frame, text="🎵 Apply Sound Parameters", command=self.send_sound_parameters, bg="#440044", fg="white", font=("Arial", 11, "bold")).pack(pady=2, fill=tk.X)

        # ==================== In-GUI Log Console ====================

        log_frame = tk.LabelFrame(self.left_frame, text=" GUI Log & Messages ", fg="yellow", bg="#1a1a1a", font=("Arial", 11, "bold"))
        log_frame.pack(pady=4, fill=tk.BOTH, expand=True)

        self.log_box = tk.Text(log_frame, height=4, bg="#111111", fg="#00ff00", font=("Courier", 9), highlightthickness=0)
        self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)

        scrollbar = tk.Scrollbar(log_frame, command=self.log_box.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_box.config(yscrollcommand=scrollbar.set)
        self.log_message("System initialized. Defaults loaded.")

        # ==================== RIGHT PANEL: LARGE ROTATION / MOTION VIEW ====================

        tk.Label(self.right_frame, text="ROTATION / MOTION TELEMETRY", font=("Arial", 16, "bold"), fg="cyan", bg="#111111").pack(pady=12)

        # Telemetry Visualizer Canvas
        self.canvas = tk.Canvas(self.right_frame, width=500, height=600, bg="#222222", highlightthickness=0)
        self.canvas.pack(pady=8, fill=tk.BOTH, expand=True)

        self.bars = []
        self.bar_colors = ["#ff4444", "#44ff44", "#4444ff"]
        axis_names = ["Volume φ", "Pitch θ", "Cutoff ψ"]

        for i, col in enumerate(self.bar_colors):
            x = 65 + (i * 145)
            rect = self.canvas.create_rectangle(x, 240, x + 70, 240, fill=col, outline="")
            self.canvas.create_text(x + 35, 275, text=axis_names[i], fill="white", font=("Arial", 14, "bold"))
            self.canvas.create_line(x - 10, 240, x + 80, 240, fill="#777777")
            self.bars.append({"rect": rect, "x": x})

        # Center line / scale
        self.canvas.create_line(25, 240, 475, 240, fill="#555555")
        self.canvas.create_text(250, 25, text="+1.0", fill="#aaaaaa", font=("Arial", 10))
        self.canvas.create_text(250, 455, text="-1.0", fill="#aaaaaa", font=("Arial", 10))
        self.canvas.create_text(250, 240, text="0", fill="#aaaaaa", font=("Arial", 9))





        # --- orientation processing state ---
        self.TILT_LIMIT = 80.0      # deg; +/-80 => 160 deg total range
        self.saber_yaw = 180.0
        self.last_yaw = None

        self.update_data()

    def log_message(self, msg):
        self.log_box.insert(tk.END, f"{msg}\n")
        self.log_box.see(tk.END)

    def send_single_parameter(self, key):
        if not ser:
            self.log_message("Error: Serial port not connected!")
            return
        try:
            val = self.entries[key].get().strip()
            if val:
                cmd = f"{key}:{val}\n"
                ser.write(cmd.encode("utf-8"))
                ser.flush()
                self.log_message(f"Sent -> {cmd.strip()}")
        except Exception as e:
            self.log_message(f"Error sending {key}: {e}")

    def send_parameters(self):
        if not ser:
            self.log_message("Error: Serial port not connected!")
            return
        try:
            for key, ent in self.entries.items():
                val = ent.get().strip()
                if val:
                    cmd = f"{key}:{val}\n"
                    ser.write(cmd.encode("utf-8"))
            ser.flush()
            self.log_message("Sent all parameters to Arduino.")
        except Exception as e:
            self.log_message(f"Error sending batch: {e}")

    def send_sound_parameters(self):
        try:
            grain_dur = self.sound_entries["gd"].get().strip()
            grain_int = self.sound_entries["gn"].get().strip()
            glide_factor = self.sound_entries["gl"].get().strip()
            resonance = self.sound_entries["res"].get().strip()

            self.audio.update_sound_params(grain_dur, grain_int, glide_factor, resonance)
            self.log_message(f"Sound Params Updated -> Dur:{grain_dur}s Int:{grain_int}s Gl:{glide_factor} Res:{resonance}%")
        except Exception as e:
            self.log_message(f"Error updating sound params: {e}")

    def update_data(self):
        if ser and ser.in_waiting:
            try:
                while ser.in_waiting:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()

                    #  added the option to use Q coming from Magdwick in uC
                    if line.startswith("M:") or line.startswith("Q:"):
                        if line.startswith("Q:"):
                            q = [float(v) for v in line[2:].split(",")]
                            if len(q) != 4:
                                continue
                            vals = list(self.process_quaternion(*q))
                        else:
                            vals = [float(v) for v in line[2:].split(",")]

                        if len(vals) == 3:
                            for i, val in enumerate(vals):
                                norm = max(-1.0, min(val, 1.0))
                                center_y = 240
                                half_h = abs(norm) * 200
                                y1, y2 = (center_y - half_h, center_y) if norm >= 0 else (center_y, center_y + half_h)
                                self.canvas.coords(self.bars[i]["rect"], self.bars[i]["x"], y1, self.bars[i]["x"] + 70, y2)

                            vol_pct = (vals[0] + 1.0) * 50.0
                            pitch_pct = (vals[1] + 1.0) * 50.0
                            cutoff_pct = (vals[2] + 1.0) * 50.0
                            self.audio.update_params(vol_pct, pitch_pct, cutoff_pct)

                    elif line.startswith("PS:"):
                        state = line[3:].strip().upper()
                        self.performance_state = state

                        if state == "IDLE":
                            self.state_label.config(text="MODE: IDLE", fg="#445dff")
                        elif state == "JEDI":
                            self.state_label.config(text="MODE: JEDI", fg="#00ff00")
                        elif state == "SITH":
                            self.state_label.config(text="MODE: SITH", fg="#ff4444")

                        self.audio.update_state(state)

                    elif line.startswith("FX:"):
                        self.active_fx = int(line[3:])
                        self.audio.update_fx(self.active_fx)

                        if self.active_fx == 1:
                            self.fx_label.config(text="FX1", fg="#ff4444")
                        elif self.active_fx == 2:
                            self.fx_label.config(text="FX2", fg="#00ff00")
                        elif self.active_fx == 3:
                            self.fx_label.config(text="FX3", fg="#445dff")
                        else:
                            self.fx_label.config(text="No FX")

                    elif line.startswith("DOM:"):
                        parts = line[4:].split(",")

                        if len(parts) == 4:
                            dx, dy, dz, is_lin = float(parts[0]), float(parts[1]), float(parts[2]), int(float(parts[3]))

                            if is_lin:
                                self.gate_indicator.config(text="LINEAR MOTION: DETECTED", fg="#00ff00")
                            else:
                                self.gate_indicator.config(text="LINEAR MOTION: 0", fg="#ff4444")

                            axes = {"X": dx, "Y": dy, "Z": dz}
                            colors = {"X": "#ff4444", "Y": "#44ff44", "Z": "#4444ff"}

                            self.dom_canvas.delete("all")

                            scale_factor = self.dom_canvas_w / 1.5
                            zero_x = 35

                            try:
                                current_thresh = float(self.entries["v"].get())
                            except ValueError:
                                current_thresh = 0.3

                            thresh_x = zero_x + current_thresh * scale_factor
                            self.dom_canvas.create_line(thresh_x, 0, thresh_x, self.dom_canvas_h, fill="yellow", dash=(3, 3))
                            self.dom_canvas.create_text(thresh_x, 10, text=f"T:{current_thresh:.2f}", fill="yellow", font=("Arial", 7))

                            y_pos = 30

                            for axis, val in axes.items():
                                bar_width = max(0, val * scale_factor)

                                if val > self.peaks[axis]:
                                    self.peaks[axis] = val
                                    self.peak_timers[axis] = 50
                                elif self.peak_timers[axis] > 0:
                                    self.peak_timers[axis] -= 1
                                else:
                                    self.peaks[axis] *= 0.92

                                peak_x = zero_x + self.peaks[axis] * scale_factor

                                self.dom_canvas.create_text(12, y_pos + 7, text=f"{axis}: {val:+.2f}", fill=colors[axis], font=("Arial", 7, "bold"))
                                self.dom_canvas.create_rectangle(zero_x, y_pos, zero_x + bar_width, y_pos + 12, fill=colors[axis], outline="")
                                self.dom_canvas.create_line(peak_x, y_pos - 2, peak_x, y_pos + 14, fill="white", width=1)

                                y_pos += 35

            except Exception as e:
                print("Read error:", e)

        self.root.after(20, self.update_data)


    # ========================== USE THIS TO INTERPRET QUATERNIONS INSTEAD OF EULER from uC============= 
    # @staticmethod
    # def wrap180(a):
    #     return (a + 180.0) % 360.0 - 180.0

    # def tilt_norm(self, g):
    #     g = max(-1.0, min(1.0, g))
    #     deg = math.degrees(math.asin(g))
    #     deg = max(-self.TILT_LIMIT, min(self.TILT_LIMIT, deg))
    #     return deg / self.TILT_LIMIT

    # def _param(self, key, default):
    #     try:
    #         return float(self.entries[key].get())
    #     except ValueError:
    #         return default

    # def process_quaternion(self, q0, q1, q2, q3):
    #     # gravity direction in the sensor frame (continuous, no wrap, no gimbal lock)
    #     gx = 2.0 * (q1 * q3 - q0 * q2)
    #     gy = 2.0 * (q0 * q1 + q2 * q3)

    #     volume = self.tilt_norm(gy)   # negate here if the direction feels backwards
    #     pitch = self.tilt_norm(gx)

    #     # --- yaw ---
    #     dt = max(self._param("p", 20.0), 1.0) / 1000.0
    #     yaw = math.degrees(math.atan2(2.0 * (q0 * q3 + q1 * q2),
    #                                   1.0 - 2.0 * (q2 * q2 + q3 * q3)))
    #     if self.last_yaw is None:
    #         self.last_yaw = yaw

    #     if abs(gx) > 0.97:
    #         dyaw = 0.0                # near +/-90 deg pitch yaw is undefined, hold it
    #     else:
    #         dyaw = self.wrap180(yaw - self.last_yaw)
    #     self.last_yaw = yaw

    #     # boost (same logic as the firmware, but on the yaw rate)
    #     rate = dyaw / dt
    #     flick = self._param("t", 100.0)
    #     coeff = self._param("b", 0.02)
    #     mult = 1.0
    #     if abs(rate) > flick:
    #         mult = min(1.0 + (abs(rate) - flick) * coeff, 3.5)
    #     self.saber_yaw += dyaw * mult

    #     # bleeder toward 180 (rate tuned per 100 Hz step, rescaled to this update rate)
    #     r = self._param("r", 0.001)
    #     k = 1.0 - (1.0 - r) ** (dt * 100.0)
    #     self.saber_yaw = (1.0 - k) * self.saber_yaw + k * 180.0
    #     self.saber_yaw = max(60.0, min(300.0, self.saber_yaw))

    #     cutoff = -(self.saber_yaw - 180.0) / 120.0
    #     return volume, pitch, cutoff
    #  ======================================================================================


    def onClose(self):
        self.audio.close()
        if ser:
            ser.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SaberGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.onClose)
    root.mainloop()
