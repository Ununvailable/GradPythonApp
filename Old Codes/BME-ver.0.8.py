# import os
# import glob
# import time
# import random

# import bluetooth

import threading
from threading import Thread
import tkinter as tk
import pandas as pd
from tkinter import filedialog
import numpy as np
import datetime
import socket
# from ecgdetectors import Detectors
from filter_and_detector import Detectors
# import numpy as np
# Stall during window moving
# Cannot work with asynchronous thread

# Global variable
real_time_data = [0] * 1000

# Peak detectors
sampling_freq = 250
detectors = Detectors(sampling_freq)


# class LocalFilter():
#     def __init__(self, plotter):
#         self.plotter = plotter
#         self.v_final = [0] * self.plotter.buffer_size
#         self.v_lp = [0] * self.plotter.buffer_size
#         self.v_avr = [0] * self.plotter.buffer_size
#     def FIR_implementation(self, sample):


class Plotter(tk.Canvas):
    def __init__(self, master, buffer_size=1000):
        super().__init__(master, height=500, width=buffer_size + 1, background="white")
        self.buffer_size = buffer_size
        self.plot_list = [0] * buffer_size
        self.mw_size = 100
        self.mw_list = [0] * self.mw_size
        # print(self.plot_list)
        # self.data_scale = 1
        self.index = 0
        self.file_read_index = 0
        self.real_time_index = 0
        self.file_reader = FileReader(self)
        self.plot_manager = PlotManager(self)
        self.peaks = 0
        self.horizontal_scale = 50  # Resolution for horizontal axis
        self.vertical_scale = 50  # Distance between lines on the vertical axis

        # Flags
        self.FileReaderFlag = False
        self.ConnectionFlag = False

    def update_plot(self, i=0):
        # Peak detection (Pan-Tompkins with Butterworth bandpass)
        # self.peaks = detectors.pan_tompkins_detector(self.plot_list)
        self.peaks = [0]
        if self.FileReaderFlag:
            # self.plot_list[self.index] = detectors.constructed_filter(self.plot_list,
            #                                                           mode="Value",
            #                                                           index=self.index)
            if self.file_read_index < len(global_file_data):
                self.plot_list[self.index] = global_file_data[self.file_read_index]
                self.file_read_index += 1
            else:
                # FileReaderFlag is no longer needed, reset it
                self.file_read_index = 0
                self.FileReaderFlag = False
        if self.ConnectionFlag:
            if self.real_time_index < len(real_time_data):
                self.plot_list[self.index] = real_time_data[self.real_time_index]
                self.real_time_index = (self.real_time_index + 1) % len(real_time_data)
            else:
                # Handle the case when real_time_data is smaller than 1000
                self.plot_list[self.index] = 0
        # print(f"{self.index}: {self.mw_list}")
        if self.FileReaderFlag is False and self.ConnectionFlag is False:
            self.plot_list[self.index] = 0
        if self.index % 10000 == 0:
            self.plot_manager.draw_grid()
            self.plot_manager.clear_text()
            self.plot_manager.draw_text()
        if self.index % 50 == 0:
            self.plot_manager.clear_count()
            self.plot_manager.draw_count()

        # Put above flag handlers when not used for evaluation
        if self.index >= self.mw_size:
            self.mw_list = self.plot_list[self.index - self.mw_size:self.index]
        if self.index < self.mw_size:
            self.mw_list = self.plot_list[self.buffer_size-self.mw_size+self.index:] + self.plot_list[:self.index]
        self.plot_list[self.index] = detectors.constructed_filter(self.mw_list,
                                                                  mode="Value",
                                                                  index=self.index)
        # self.plot_list[self.index] = detectors.constructed_filter(self.plot_list,
        #                                                           mode="Value",
        #                                                           index=self.index)
        # print(self.plot_list[self.index])

        self.plot_manager.draw_line()
        self.plot_manager.delete_line(self.buffer_size)
        self.index = (self.index + 1) % self    .buffer_size
        self.after(int(1000/sampling_freq), self.update_plot, i + 1)


class PlotManager:
    def __init__(self, plotter):
        self.tag = None
        self.plotter = plotter
        self.line_tags = set()  # Set to store line tags
        self.delete_index = 0  # Track the current delete index
        self.ready_to_delete = False  # Flag to indicate when to start deleting lines
        self.plot_data_scale = 0.5
        self.plot_shift_vertical = 200
        self.plot_shift_horizontal = 245

    def draw_line(self):
        self.tag = f"A{self.plotter.index}"
        self.plotter.create_line(self.plotter.index - 1,
                                 self.plotter.winfo_height() // 2 - self.plotter.plot_list[self.plotter.index - 1] * self.plot_data_scale
                                 + self.plot_shift_vertical,
                                 self.plotter.index,
                                 self.plotter.winfo_height() // 2 - self.plotter.plot_list[self.plotter.index] * self.plot_data_scale
                                 + self.plot_shift_vertical,
                                 width=3,
                                 fill="red",
                                 tags=self.tag)

        if self.plotter.index == 999:
            # Set the flag to indicate that lines are ready for deletion
            self.ready_to_delete = True

    def delete_line(self, buffer_size, delete_size=50):
        if self.ready_to_delete:
            delete_index = self.plotter.index + 1
            if self.plotter.index == buffer_size:
                delete_index = 0
            # Delete lines only after the first 1000 values are drawn
            for tag_name in range(delete_index, delete_index + delete_size):
                # print(delete_index)
                self.plotter.delete(f"A{tag_name}")

    def draw_count(self):
        # print(peaks)
        print(len(self.plotter.peaks))
        self.plotter.create_text(100,490,
                                 text=f"Counted number of beats: {len(self.plotter.peaks)}",
                                 font=("Helvetica", 10), fill="blue",
                                 tags="counts")

    def clear_count(self):
        self.plotter.delete(f"counts")

    def draw_grid(self):
        # Draw horizontal grid lines
        for i in range(0, self.plotter.winfo_width() + 1, self.plotter.horizontal_scale):
            self.plotter.create_line(i, 0, i, self.plotter.winfo_height(),
                                     width=0.5,
                                     fill="lightgray",
                                     tags="grid")

        # Draw vertical grid lines
        for i in range(-250, 250, self.plotter.vertical_scale):
            y = self.plotter.winfo_height() // 2 - i
            self.plotter.create_line(0, y, self.plotter.winfo_width(), y,
                                     width=0.5,
                                     fill="lightgray",
                                     tags="grid")

    def draw_text(self):
        # Draw horizontal grid lines
        for i in range(self.plotter.horizontal_scale, self.plotter.winfo_width() + 1, self.plotter.horizontal_scale):
            self.plotter.create_text(i, self.plot_shift_horizontal + self.plot_shift_vertical,
                                     text=f"{int(i)}",
                                     tags="texts")

        # Draw vertical grid lines
        for i in range(-250, 250, self.plotter.vertical_scale):
            self.plotter.create_text(15, i + self.plot_shift_horizontal,
                                     text=f"{int((-i + self.plot_shift_vertical) / self.plot_data_scale)}",
                                     tags="texts")

    def clear_text(self):
        self.plotter.delete(f"texts")


class ConnectionManager:
    def __init__(self, plotter, server_ip, server_port, sample_size, pack_size):
        self.plotter = plotter
        self.server_ip = server_ip
        self.server_port = server_port
        self.sample_size = sample_size
        self.pack_size = pack_size
        self.socket = None
        self.client_socket = None
        self.client_address = None
        self.connection_thread = None
        self.stop_event = None

    def process_received_data(self, value_set):
        processed_data = []

        for i in range(min(len(value_set), self.pack_size)):
            try:
                value = int(value_set[i])
            except ValueError:
                value = 0

            processed_data.append(value)

        return processed_data

    def connection_thread_func(self):
        try:
            while not self.stop_event.is_set():
                current_time = datetime.datetime.now()

                # Receive data from the server
                package = self.client_socket.recv(self.pack_size).decode('utf-8')
                package = package.strip('\n').strip('|').strip("\r").strip(' ')
                value_set = np.array(package.split(','))
                # print(value_set)
                # Process the received datas
                processed_data = self.process_received_data(value_set)

                # Update the global variable for real-time data
                global real_time_data
                real_time_data = processed_data

        except Exception as e:
            print(f"Error in connection thread: {e}")

        finally:
            self.client_socket.close()

    def start_connection(self):
        print("starting connection")
        try:
            # Create a socket object
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # Connect to the server
            self.socket.bind((self.server_ip, self.server_port))
            self.socket.listen(1)
            self.client_socket, self.client_address = self.socket.accept()
            print(f"Accepted connection from {self.client_address[0]}:{self.client_address[1]}")

            # Initialize stop event
            self.stop_event = threading.Event()

            # Start the connection thread
            self.connection_thread = Thread(target=self.connection_thread_func)
            self.connection_thread.start()

            self.plotter.ConnectionFlag = True

        except Exception as e:
            self.plotter.ConnectionFlag = False
            print(f"Error starting connection: {e}")

    def stop_connection(self):
        # Check if the connection thread is active
        if self.connection_thread is not None:
            # Set the stop event to signal the thread to stop
            self.stop_event.set()
            self.connection_thread.join()  # Wait for the thread to finish
            self.socket.close()
            self.client_socket.close()
            self.plotter.ConnectionFlag = False
        else:
            print("No active connection to stop.")


class FileReader:
    def __init__(self, plotter):
        super().__init__()
        self.file_length = int
        self.file_data = []
        self.filename = str
        self.plotter = plotter

    def open_file(self):
        self.filename = filedialog.askopenfilename(title="Select a file", filetypes=(("csv files", "*.csv"),))
        self.file_data = pd.read_csv(self.filename)
        self.file_data = self.file_data["0"].values.tolist()
        global global_file_data
        global_file_data = self.file_data
        self.file_length = len(self.file_data)
        self.plotter.FileReaderFlag = True

    def stop_reading(self):
        # Set the stop event to signal the thread to stop reading
        self.plotter.FileReaderFlag = False


class UserInterface(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)

        # Objects
        self.plotter = Plotter(self)
        self.connection_manager = ConnectionManager(self.plotter, '0.0.0.0', 9051, 1000, 4480)
        self.file_reader = FileReader(self.plotter)

        # Buttons
        connect_button = tk.Button(self, width=15, height=3, text="Connect",
                                   command=self.connection_manager.start_connection)
        disconnect_button = tk.Button(self, width=15, height=3, text="Disconnect",
                                      command=self.connection_manager.stop_connection)
        fileread_button = tk.Button(self, width=15, height=3, text="Choose file",
                                    command=self.file_reader.open_file)
        fileread_stop = tk.Button(self, width=15, height=3, text="Stop file read",
                                  command=self.file_reader.stop_reading)

        # Labels
        # status_label = tk.Label(self, text="Plotting...",
        #                         borderwidth=1,
        #                         compound="center", anchor="e",
        #                         relief="sunken",
        #                         width=142,
        #                         background="white"
        #                         )

        # Graphic placement
        connect_button.grid(row=1, column=0)
        disconnect_button.grid(row=2, column=0)
        fileread_button.grid(row=3, column=0)
        fileread_stop.grid(row=4, column=0)

        self.plotter.grid(row=0, rowspan=5, column=1)

        # status_label.grid(row=5, column=1)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("BME4 ECG Signal Plotter")

    user_interface = UserInterface(master=root)
    user_interface.pack(side="bottom", fill="both", expand=True)
    root.resizable(width=False, height=False)

    user_interface.plotter.update_plot()  # Start the continuous plot update

    root.mainloop()
