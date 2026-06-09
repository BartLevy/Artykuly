import numpy as np
import scipy.io.wavfile as wavfile

import matplotlib
#matplotlib.use("GTK3Agg")  # GNOME-compatible interactive backend
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

# Load the audio file
audio_path = 'temp.wav'  # Replace with your file path
sr, y = wavfile.read(audio_path)

# Convert to float if necessary (ensures compatibility)
if y.dtype != np.float32:
    y = y.astype(np.float32) / np.iinfo(y.dtype).max

# Convert stereo to mono by averaging channels
if len(y.shape) > 1:  # Check if the audio has more than one channel
    y = y.mean(axis=1)

# Calculate frequencies and the magnitude spectrum
frequencies = np.fft.rfftfreq(len(y), d=1/sr)
magnitude_spectrum = np.abs(np.fft.rfft(y))

# Calculate the spectral centroid as the weighted average frequency
spectral_centroid_value = np.sum(frequencies * magnitude_spectrum) / np.sum(magnitude_spectrum)

# Visualization

# Time axis for the waveform
time = np.linspace(0, len(y) / sr, num=len(y))

plt.figure(figsize=(12, 6))

# Plot the waveform
plt.subplot(2, 1, 1)
plt.plot(time, y, color='gray')
plt.title('Audio Waveform')
plt.xlabel('Time (s)')
plt.ylabel('Amplitude')

# Plot the magnitude spectrum with the spectral centroid
plt.subplot(2, 1, 2)
plt.plot(frequencies, magnitude_spectrum, color='blue')
plt.axvline(spectral_centroid_value, color='red', linestyle='--', 
            label=f'Spectral Centroid: {spectral_centroid_value:.2f} Hz')
plt.title('Spectral Centroid Visualization')
plt.xlabel('Frequency (Hz)')
plt.ylabel('Magnitude')
plt.legend()

plt.tight_layout()
plt.show()
