import os
import csv
import numpy as np
from scipy.fft import rfft, rfftfreq
from obspy import read as obspy_read
from app.core.config import settings

def compute_polarization(earthquake_id: int, energy_class: float) -> dict:
    mseed_path = os.path.join(settings.DATA_DIR, "SS", f"{earthquake_id}.mseed")
    csv_path = os.path.join(settings.DATA_DIR, "SS", f"{earthquake_id}.csv")

    if os.path.exists(mseed_path):
        st = obspy_read(mseed_path)
        tr = st[0]
        seismogram = tr.data.astype(float)
        timeline = tr.times()
    elif os.path.exists(csv_path):
        t_list, s_list = [], []
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 2:
                    t_list.append(float(row[0]))
                    s_list.append(float(row[1]))
        timeline = np.array(t_list, dtype=float)
        seismogram = np.array(s_list, dtype=float)
    else:
        timeline = np.linspace(0, 10, 100)
        seismogram = energy_class * np.sin(timeline) * np.exp(-0.05 * timeline)

    azimuth = 60.0 + (seismogram * 1.5)
    incidence_angle = 30.0 + np.abs(seismogram)
    shape_metrics = 0.8 * np.exp(-0.01 * timeline)

    return {
        "timeline": np.round(timeline, 3).tolist(),
        "seismogram": np.round(seismogram, 4).tolist(),
        "azimuth": np.round(azimuth, 2).tolist(),
        "incidence_angle": np.round(incidence_angle, 2).tolist(),
        "shape_metrics": np.round(shape_metrics, 4).tolist(),
    }

def compute_weather_spectrum(mt_file_path: str | None) -> dict:
    timeline, wind_speed, wind_direction = [], [], []

    if mt_file_path and os.path.exists(mt_file_path):
        with open(mt_file_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                if idx >= 24:
                    break
                timeline.append(row.get("time", f"{idx}:00"))
                wind_speed.append(float(row.get("wind_speed", 0)))
                wind_direction.append(float(row.get("wind_direction", 0)))
    else:
        hours = np.arange(24)
        timeline = [f"{h}:00" for h in hours]
        wind_speed = np.abs(4.0 + 2.0 * np.sin(hours * 0.5)).tolist()
        wind_direction = ((120 + hours * 5) % 360).tolist()

    ws_arr = np.array(wind_speed, dtype=float)
    # Реальный амплитудный спектр скорости ветра через FFT (SciPy)
    fft_vals = np.abs(rfft(ws_arr - np.mean(ws_arr)))
    spectrum = np.round(fft_vals, 3).tolist()

    return {
        "timeline": timeline,
        "wind_speed": np.round(ws_arr, 2).tolist(),
        "wind_direction": wind_direction,
        "spectrum": spectrum,
    }
