import numpy as np
import pywt
import ecgtemplates

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib
import scipy.signal as signal


class Detectors:
    def __init__(self, sampling_frequency=250):
        """
        The constructor takes the sampling rate in Hz of the ECG data.
        The constructor can be called without speciying a sampling rate to
        just access the detector_list, however, detection won't
        be possible.
        """

        # Sampling rate
        self.fs = sampling_frequency

        # This is set to a positive value for benchmarking
        self.engzee_fake_delay = 0

        # 2D Array of the different detectors: [[description,detector]]
        self.detector_list = [
            # ["Elgendi et al (Two average)",self.two_average_detector],
            # ["Matched filter",self.matched_filter_detector],
            # ["Kalidas & Tamil (Wavelet transform)",self.swt_detector],
            # ["Engzee",self.engzee_detector],
            # ["Christov",self.christov_detector],
            # ["Hamilton",self.hamilton_detector],
            ["Pan Tompkins", self.pan_tompkins_detector],
            # ["WQRS",self.wqrs_detector]
        ]

    def get_detector_list(self):
        """
        Returns a 2D array of the different detectors in the form:
        [[description1,detector1],[description2,detector2], ...]
        where description is a string and detector a function pointer
        to the detector. Use this for benchmarking to loop through
        detectors.
        """
        return self.detector_list

    def constructed_filter(self, unfiltered_ecg, mode, index):
        print(f"{index}: {unfiltered_ecg}")
        f1 = 0.5 / self.fs
        f2 = 99.5 / self.fs

        # Original Butterworth
        # b, a = signal.butter(1, [f1, f2], btype='bandpass')
        # filtered = signal.lfilter(b, a, unfiltered_ecg)

        # Design FIR bandpass filter using firwin
        num_taps = 11    # Adjust the number of taps as needed
        taps = signal.firwin(num_taps, [f1, f2], pass_zero=False)
        # print(taps)
        filtered = signal.convolve(unfiltered_ecg, taps, mode='same')

        # Calculate group delay (IIR)
        # center_frequency = (f1 + f2) / (2 * self.fs)
        # nyquist = 0.5 * self.fs
        # frequency_response = signal.freqz(taps, 1, worN=8000)
        # phase_response = np.unwrap(np.angle(frequency_response[1]))
        # frequency_points = frequency_response[0] * nyquist / np.pi
        # center_frequency_index = np.argmin(np.abs(frequency_points - center_frequency))
        # group_delay = -np.diff(phase_response)[center_frequency_index] / np.diff(frequency_response[0])[
        #     center_frequency_index]
        # print(f"Group Delay at Center Frequency: {group_delay} samples")

        # for i in range(len(filtered)):
        # print(filtered)
        # print(len(filtered))
        print(filtered[len(filtered) - 1])
        if mode == "Value":
            return filtered[len(filtered) - 1]
            # return 0
        if mode == "List":
            return filtered

    def pan_tompkins_detector(self, unfiltered_ecg, MWA_name='cumulative'):
        """
        Jiapu Pan and Willis J. Tompkins.
        A Real-Time QRS Detection Algorithm.
        In: IEEE Transactions on Biomedical Engineering
        BME-32.3 (1985), pp. 230–236.
        """

        maxQRSduration = 0.150  # sec

        # Call filter
        filtered_ecg = self.constructed_filter(unfiltered_ecg, mode="List", index=0)

        # Other parts of Pan-Tompkins
        diff = np.diff(filtered_ecg)
        squared = diff * diff
        N = int(maxQRSduration * self.fs)
        mwa = MWA_from_name(MWA_name)(squared, N)
        mwa[:int(maxQRSduration * self.fs * 2)] = 0

        mwa_peaks = panPeakDetect(mwa, self.fs)

        return mwa_peaks


def MWA_from_name(function_name):
    if function_name == "cumulative":
        return MWA_cumulative
    # elif function_name == "convolve":
    #     return MWA_convolve
    # elif function_name == "original":
    #     return MWA_original
    else:
        raise RuntimeError('invalid moving average function!')


def MWA_cumulative(input_array, window_size):
    ret = np.cumsum(input_array, dtype=float)
    ret[window_size:] = ret[window_size:] - ret[:-window_size]

    for i in range(1, window_size):
        ret[i - 1] = ret[i - 1] / i
    ret[window_size - 1:] = ret[window_size - 1:] / window_size

    return ret


def panPeakDetect(detection, fs):
    min_distance = int(0.25 * fs)

    signal_peaks = [0]
    noise_peaks = []

    SPKI = 0.0
    NPKI = 0.0

    threshold_I1 = 0.0
    threshold_I2 = 0.0

    RR_missed = 0
    index = 0
    indexes = []

    missed_peaks = []
    peaks = []

    for i in range(1, len(detection) - 1):
        if detection[i - 1] < detection[i] and detection[i + 1] < detection[i]:
            peak = i
            peaks.append(i)

            if detection[peak] > threshold_I1 and (peak - signal_peaks[-1]) > 0.3 * fs:

                signal_peaks.append(peak)
                indexes.append(index)
                SPKI = 0.125 * detection[signal_peaks[-1]] + 0.875 * SPKI
                if RR_missed != 0:
                    if signal_peaks[-1] - signal_peaks[-2] > RR_missed:
                        missed_section_peaks = peaks[indexes[-2] + 1:indexes[-1]]
                        missed_section_peaks2 = []
                        for missed_peak in missed_section_peaks:
                            if missed_peak - signal_peaks[-2] > min_distance \
                                    and signal_peaks[-1] - missed_peak > min_distance \
                                    and detection[missed_peak] > threshold_I2:
                                missed_section_peaks2.append(missed_peak)

                        if len(missed_section_peaks2) > 0:
                            signal_missed = [detection[i] for i in missed_section_peaks2]
                            index_max = np.argmax(signal_missed)
                            missed_peak = missed_section_peaks2[index_max]
                            missed_peaks.append(missed_peak)
                            signal_peaks.append(signal_peaks[-1])
                            signal_peaks[-2] = missed_peak

            else:
                noise_peaks.append(peak)
                NPKI = 0.125 * detection[noise_peaks[-1]] + 0.875 * NPKI

            threshold_I1 = NPKI + 0.25 * (SPKI - NPKI)
            threshold_I2 = 0.5 * threshold_I1

            if len(signal_peaks) > 8:
                RR = np.diff(signal_peaks[-9:])
                RR_ave = int(np.mean(RR))
                RR_missed = int(1.66 * RR_ave)

            index = index + 1

    signal_peaks.pop(0)

    return signal_peaks
