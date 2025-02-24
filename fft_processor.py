import numpy as np
from scipy.fft import fft
from scipy.signal import windows, butter, filtfilt

class FFTProcessor:
    def __init__(self, sample_rate, buffer_size):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.window = windows.hann(buffer_size)
        
        # Setup butterworth filter
        self.nyquist = sample_rate / 2
        self.cutoff = 20  # Hz
        self.b, self.a = butter(4, self.cutoff/self.nyquist)
        
    def process(self, data):
        # Apply window function
        windowed_data = np.array(data) * self.window
        
        # Perform FFT
        fft_result = fft(windowed_data)
        frequencies = np.fft.fftfreq(len(data), 1/self.sample_rate)
        
        # Calculate magnitude spectrum
        magnitude = 2.0/self.buffer_size * np.abs(fft_result)
        
        return frequencies, magnitude
        
    def apply_filter(self, data):
        # Apply butterworth filter
        return filtfilt(self.b, self.a, data) 