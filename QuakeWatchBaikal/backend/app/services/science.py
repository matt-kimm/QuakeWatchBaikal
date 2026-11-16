import os
import io
import csv
import base64
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import math
from scipy import signal
import matplotlib.dates as mdates
from matplotlib.ticker import MultipleLocator

import numpy as np
import pandas as pd
import ephem
from scipy.fft import rfft
from scipy.signal import hilbert, medfilt
from scipy.ndimage import convolve1d
from obspy import read, UTCDateTime, Stream
from obspy.imaging.beachball import beach

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import tempfile
from app.core.s3 import list_s3_keys, download_s3_object

from app.core.config import settings

# =================== Параметры анализа =====================
FILTER_FREQ = 50 / 24          # ≈ 2.083 Гц
FILTER_BANDWIDTH = 0.01
FILTER_WINDOW = 13
WINDOW_SEC = 300
OVERLAP_FRAC = 0.5
TARGET_SAMPLING_RATE = 5.0     # Гц
TIDE_INTERPOLATION_STEP = 3600 # 1 час

STATIONS = {
    "KYD": {"name": "Култук / Кырен (KYD)", "lat": "52.566499", "lon": "106.136094", "elev": 150},
    "ZUNM": {"name": "Зун-Мурино (ZUNM)", "lat": "51.72092", "lon": "102.89358", "elev": 0},
}

def _collect_files_s3_or_local(s3_prefix: str, filename_filter) -> tuple[list[str], tempfile.TemporaryDirectory]:
    """Ищет файлы в S3 по префиксу и скачивает во временную папку; если в S3 пусто — берет из DATA_DIR."""
    tmp_dir = tempfile.TemporaryDirectory()
    matched_paths = []

    try:
        s3_keys = [k for k in list_s3_keys(s3_prefix) if filename_filter(os.path.basename(k))]
        for key in s3_keys:
            local_target = os.path.join(tmp_dir.name, os.path.basename(key))
            download_s3_object(key, local_target)
            matched_paths.append(local_target)
    except Exception:
        pass

    if not matched_paths:
        local_dir = os.path.join(settings.DATA_DIR, *s3_prefix.strip("/").split("/"))
        if os.path.exists(local_dir):
            for fname in os.listdir(local_dir):
                if filename_filter(fname):
                    matched_paths.append(os.path.join(local_dir, fname))

    return matched_paths, tmp_dir


def read_and_process_daily(ss_name: str, dt_start: datetime, dt_end: datetime) -> Stream:
    st = Stream()
    current_date = dt_start.date()
    end_date = dt_end.date()
    file_list = []

    temp_dirs = []
    while current_date <= end_date:
        prefix = f"SS/{current_date.year}/{current_date.month:02d}/{current_date.day:02d}/"
        day_files, t_dir = _collect_files_s3_or_local(
            prefix, lambda fn: fn.startswith(f"BY.{ss_name}") and fn.endswith(".seed")
        )
        temp_dirs.append(t_dir)
        file_list.extend(day_files)
        current_date += timedelta(days=1)


    if not file_list:
        return st

    def load_file(file_path: str):
        try:
            stream = read(file_path)
            for tr in stream:
                if tr.stats.sampling_rate > 50:
                    tr.resample(50)
                factor = int(tr.stats.sampling_rate / TARGET_SAMPLING_RATE)
                if factor > 1:
                    tr.decimate(factor, strict_length=False)
            return stream
        except Exception:
            return None


    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(load_file, file_list))

    for result in results:
        if result:
            st += result

    if len(st) == 0:
        return st

    st.merge(fill_value="interpolate")
    st = st.slice(starttime=UTCDateTime(dt_start), endtime=UTCDateTime(dt_end))
    st.detrend("demean")
    st.detrend("linear")
    st.taper(max_percentage=0.1)

    f_min = FILTER_FREQ - FILTER_BANDWIDTH / 2
    f_max = FILTER_FREQ + FILTER_BANDWIDTH / 2
    st.filter("bandpass", freqmin=f_min, freqmax=f_max)

    return st



def calculate_polarization_vectorized(data_matrix: np.ndarray, window_starts: np.ndarray, win_samples: int):
    n_windows = len(window_starts)
    rectilinearity = np.zeros(n_windows)
    ellipticity = np.zeros(n_windows)
    azimuth = np.zeros(n_windows)
    incidence = np.zeros(n_windows)

    for idx, start in enumerate(window_starts):
        end = start + win_samples
        window_data = data_matrix[:, start:end]

        window_mean = np.mean(window_data, axis=1, keepdims=True)
        centered = window_data - window_mean
        cov_matrix = (centered @ centered.T.conj()) / (win_samples - 1)

        evals, evecs = np.linalg.eigh(cov_matrix)
        sort_idx = np.argsort(evals)[::-1]
        l1, l2, l3 = evals[sort_idx]
        v1 = evecs[:, sort_idx[0]]

        if l1 > 0:
            rectilinearity[idx] = 1.0 - ((max(0, l2) + max(0, l3)) / (2.0 * l1))
            ellipticity[idx] = np.sqrt(max(0, l2) / l1)

        r = np.real(v1)
        q = np.imag(v1)
        phi = 0.5 * np.arctan2(2.0 * np.dot(r, q), np.dot(r, r) - np.dot(q, q))
        v1_major = r * np.cos(phi) + q * np.sin(phi)

        if np.dot(v1_major, v1_major) < np.dot(
            r * np.sin(phi) - q * np.cos(phi), r * np.sin(phi) - q * np.cos(phi)
        ):
            phi += np.pi / 2.0
            v1_major = r * np.cos(phi) + q * np.sin(phi)

        az = np.degrees(np.arctan2(v1_major[2], v1_major[1]))
        azimuth[idx] = az if az >= 0 else az + 360.0

        norm_horiz = np.sqrt(v1_major[1] ** 2 + v1_major[2] ** 2)
        incidence[idx] = np.degrees(np.arctan2(norm_horiz, abs(v1_major[0])))

    return rectilinearity, ellipticity, azimuth, incidence


def _render_beachball_base64(st_azimuth: float, st_incidence: float, ss_name: str, eq_time_str: str) -> str | None:
    try:
        focal_mech = [135, 60, -135]
        r = np.sqrt(2) * np.sin(np.radians(st_incidence) / 2)
        theta = np.radians(90 - st_azimuth)
        x_st = r * np.cos(theta)
        y_st = r * np.sin(theta)

        fig_bb, ax_bb = plt.subplots(figsize=(5, 5), dpi=120)
        bball = beach(focal_mech, xy=(0, 0), width=2.0, facecolor="red", linewidth=1.5, zorder=1)
        ax_bb.add_collection(bball)
        ax_bb.plot(
            x_st,
            y_st,
            marker="^",
            color="blue",
            markersize=11,
            markeredgecolor="black",
            zorder=10,
            label=f"Станция {ss_name}",
        )
        ax_bb.set_title(f"Нодальные плоскости\n{eq_time_str} | {ss_name}", fontsize=10, pad=10)
        ax_bb.legend(loc="upper right")
        ax_bb.set_aspect("equal")
        ax_bb.axis("off")
        ax_bb.set_xlim(-1.2, 1.2)
        ax_bb.set_ylim(-1.2, 1.2)

        buf = io.BytesIO()
        fig_bb.savefig(buf, format="png", bbox_inches="tight", transparent=True)
        plt.close(fig_bb)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except Exception:
        return None


def compute_polarization(
    eq_dt: datetime,
    energy_class: float,
    station_code: str = "KYD",
    days_before: int = 10,
    days_after: int = 10,
) -> dict:
    station_info = STATIONS.get(station_code, STATIONS["KYD"])
    eq_time_str = eq_dt.strftime("%Y-%m-%d %H:%M:%S")

    d1 = eq_dt - timedelta(days=days_before)
    d2 = eq_dt + timedelta(days=days_after)
    dt1 = datetime.combine(d1.date(), datetime.min.time())
    dt2 = datetime.combine(d2.date(), datetime.max.time())

    st = read_and_process_daily(station_code, dt1, dt2)
    components = {tr.stats.component for tr in st} if len(st) > 0 else set()
    is_synthetic = False

    if {"Z", "N", "E"}.issubset(components):
        z_tr = st.select(component="Z")[0]
        n_tr = st.select(component="N")[0]
        e_tr = st.select(component="E")[0]
        min_len = min(len(z_tr.data), len(n_tr.data), len(e_tr.data))
        dt = z_tr.stats.delta
        start_time_dt = pd.to_datetime(str(z_tr.stats.starttime))
        z_data, n_data, e_data = z_tr.data[:min_len], n_tr.data[:min_len], e_tr.data[:min_len]
    else:
        st = read_and_process_daily(station_code, dt1, dt2)
        components = {tr.stats.component for tr in st} if len(st) > 0 else set()

        if not {"Z", "N", "E"}.issubset(components):
            raise FileNotFoundError(
                f"Для станции {station_code} не найдены полные 3-компонентные (Z, N, E) .seed файлы "
                f"за период с {dt1.strftime('%Y-%m-%d')} по {dt2.strftime('%Y-%m-%d')}."
            )

        z_tr = st.select(component="Z")[0]
        n_tr = st.select(component="N")[0]
        e_tr = st.select(component="E")[0]
        min_len = min(len(z_tr.data), len(n_tr.data), len(e_tr.data))
        dt = z_tr.stats.delta
        start_time_dt = pd.to_datetime(str(z_tr.stats.starttime))
        z_data, n_data, e_data = z_tr.data[:min_len], n_tr.data[:min_len], e_tr.data[:min_len]


    t_signal_dt = start_time_dt + pd.to_timedelta(np.arange(min_len) * dt, unit="s")
    data_matrix = np.vstack((hilbert(z_data), hilbert(n_data), hilbert(e_data)))

    win_samples = int(WINDOW_SEC / dt)
    step_samples = int(win_samples * (1.0 - OVERLAP_FRAC))
    window_starts = np.arange(0, min_len - win_samples + 1, step_samples)

    rectilinearity, ellipticity, azimuth, incidence = calculate_polarization_vectorized(
        data_matrix, window_starts, win_samples
    )

    center_samples = window_starts + win_samples // 2
    t_analysis_dt = pd.to_datetime(t_signal_dt[center_samples])
    if t_analysis_dt.tz is not None:
        t_analysis_dt = t_analysis_dt.tz_convert(None)

    # Сглаживание
    rectilinearity = medfilt(rectilinearity, kernel_size=FILTER_WINDOW)
    ellipticity = medfilt(ellipticity, kernel_size=FILTER_WINDOW)
    incidence = medfilt(incidence, kernel_size=FILTER_WINDOW)

    az_rad = np.radians(azimuth)
    cos_az = convolve1d(np.cos(az_rad), weights=np.ones(FILTER_WINDOW) / FILTER_WINDOW, mode="nearest")
    sin_az = convolve1d(np.sin(az_rad), weights=np.ones(FILTER_WINDOW) / FILTER_WINDOW, mode="nearest")
    azimuth = np.mod(np.degrees(np.arctan2(sin_az, cos_az)), 360.0)

    # Расчет лунно-солнечного прилива
    gate = ephem.Observer()
    gate.lat = station_info["lat"]
    gate.lon = station_info["lon"]
    gate.elevation = station_info["elev"]
    moon, sun = ephem.Moon(), ephem.Sun()

    t_start, t_end = t_analysis_dt[0], t_analysis_dt[-1]
    tide_times = pd.date_range(start=t_start, end=t_end, freq=f"{int(TIDE_INTERPOLATION_STEP)}s")
    tide_values = np.zeros(len(tide_times))

    for i, ts in enumerate(tide_times):
        gate.date = ts.to_pydatetime()
        moon.compute(gate)
        sun.compute(gate)
        tide_moon = (3.0 * np.sin(float(moon.alt)) ** 2 - 1.0) / (moon.earth_distance ** 3)
        tide_sun = 0.46 * (3.0 * np.sin(float(sun.alt)) ** 2 - 1.0) / (sun.earth_distance ** 3)
        tide_values[i] = tide_moon + tide_sun

    tides = np.interp(
        (t_analysis_dt - t_start).total_seconds().to_numpy(),
        (tide_times - t_start).total_seconds().to_numpy(),
        tide_values,
    )
    std_tides = np.std(tides)
    tides = (tides - np.mean(tides)) / std_tides if std_tides > 0 else tides

    # Статистика
    mask = rectilinearity > 0.5
    az_masked = np.where(mask, azimuth, None)
    inc_masked = np.where(mask, incidence, None)

    stats = {"bg_az": None, "bg_inc": None, "pre_az": None, "pre_inc": None, "diff_az": None}
    if np.sum(mask) > 0:
        eq_time_dt = pd.to_datetime(eq_dt)
        pre_days = min(3, days_before)
        pre_start = eq_time_dt - timedelta(days=pre_days)
        pre_mask = (t_analysis_dt >= pre_start) & (t_analysis_dt < eq_time_dt) & mask

        if np.any(pre_mask):
            stats["pre_az"] = round(float(np.nanmean(azimuth[pre_mask])), 1)
            stats["pre_inc"] = round(float(np.nanmean(incidence[pre_mask])), 1)

        if days_before > pre_days:
            bg_start = eq_time_dt - timedelta(days=days_before)
            bg_mask = (t_analysis_dt >= bg_start) & (t_analysis_dt < pre_start) & mask
            if np.any(bg_mask):
                stats["bg_az"] = round(float(np.nanmean(azimuth[bg_mask])), 1)
                stats["bg_inc"] = round(float(np.nanmean(incidence[bg_mask])), 1)
                if stats["pre_az"] is not None:
                    stats["diff_az"] = round(stats["pre_az"] - stats["bg_az"], 1)

    # Нодальные плоскости
    times_np = np.array(t_analysis_dt, dtype="datetime64[ns]")
    eq_idx = int(np.argmin(np.abs(times_np - np.datetime64(eq_dt))))
    st_azimuth = float(azimuth[eq_idx])
    st_incidence = float(incidence[eq_idx])
    beachball_b64 = _render_beachball_base64(st_azimuth, st_incidence, station_code, eq_time_str)

    timeline_str = [ts.strftime("%Y-%m-%d %H:%M:%S") for ts in t_analysis_dt]

    return {
        "station": station_code,
        "eq_time": eq_time_str,
        "is_synthetic": is_synthetic,
        "timeline": timeline_str,
        "azimuth": [round(float(x), 2) if x is not None else None for x in az_masked],
        "incidence_angle": [round(float(x), 2) if x is not None else None for x in inc_masked],
        "rectilinearity": np.round(rectilinearity, 4).tolist(),
        "ellipticity": np.round(ellipticity, 4).tolist(),
        "tides": np.round(tides, 4).tolist(),
        "stats": stats,
        "ray_params": {"azimuth": round(st_azimuth, 1), "incidence": round(st_incidence, 1)},
        "beachball_png": beachball_b64,
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
    fft_vals = np.abs(rfft(ws_arr - np.mean(ws_arr)))

    return {
        "timeline": timeline,
        "wind_speed": np.round(ws_arr, 2).tolist(),
        "wind_direction": wind_direction,
        "spectrum": np.round(fft_vals, 3).tolist(),
    }




def compute_meteo_seismic_analysis(
    dt1: datetime,
    dt2: datetime,
    ss_name: str = "KYD",
    channel: int = 2,
    mt_station: str = "bugd",
    f1: float = 1.0,
    f2: float = 5.0,
) -> dict:
    # 1. Чтение сейсмограммы из D:/data/SS/YYYY/MM/DD/
    stm = Stream()
    current_date = dt1.date()
    end_date = dt2.date()

    while current_date <= end_date:
        cdir = os.path.join(
            settings.DATA_DIR, "SS", str(current_date.year), f"{current_date.month:02d}", f"{current_date.day:02d}"
        )
        if os.path.exists(cdir):
            for fname in os.listdir(cdir):
                if ss_name in fname:
                    try:
                        stm += read(os.path.join(cdir, fname))
                    except Exception:
                        pass
        current_date += timedelta(days=1)

    if len(stm) == 0:
        raise FileNotFoundError(
            f"Сейсмограммы станции {ss_name} не найдены за период {dt1} — {dt2}."
        )

    stm.merge(fill_value="interpolate")
    sorted_stm = stm.sort()
    if channel >= len(sorted_stm):
        raise ValueError(f"Канал с индексом {channel} отсутствует (доступно каналов: {len(sorted_stm)}).")

    tr = sorted_stm[channel].slice(starttime=UTCDateTime(dt1), endtime=UTCDateTime(dt2))
    if tr.stats.npts == 0:
        raise FileNotFoundError(f"Нет данных сейсмограммы внутри точного окна {dt1} — {dt2}.")

    tr.detrend("linear")
    tr.filter("highpass", freq=0.005, corners=2, zerophase=True)

    sig_data = tr.data * 0.003
    times_mpl = tr.times(type="matplotlib")
    label = f"{tr.stats.station}.{tr.stats.channel}"

    # Расчет спектрограммы
    fs = tr.stats.sampling_rate
    duration_sec = tr.stats.endtime - tr.stats.starttime
    denom = math.sqrt(max(duration_sec * (f2 - f1), 1e-6))
    nfft = max(2, int(tr.stats.npts / denom))
    nover = int(nfft * 0.6)

    f, _, sxx = signal.spectrogram(
        tr.data, fs, nperseg=nfft, noverlap=nover, mode="magnitude", scaling="spectrum"
    )
    freq_slice = np.where((f >= f1) & (f <= f2))[0]
    sxx_db = 10 * np.log10(np.maximum(sxx[freq_slice, :], 1e-20))
    tm1 = mdates.date2num(tr.stats.starttime.datetime)
    tm2 = mdates.date2num(tr.stats.endtime.datetime)

    # 2. Чтение метеоданных из D:/data/MT/YYYY/MM/
    df = pd.DataFrame()
    for element in pd.period_range(dt1.date(), dt2.date(), freq="M"):
        prefix = f"MT/{element.year}/{element.month:02d}/"
        mt_files, t_dir = _collect_files_s3_or_local(
            prefix, lambda fn: fn.startswith(mt_station) and fn.endswith(".csv")
        )
        for fpath in mt_files:
            try:
                part = pd.read_csv(fpath, delimiter=";", index_col=0, parse_dates=True)
                df = pd.concat([df, part])
            except Exception:
                pass
        t_dir.cleanup()


    if len(df) > 0:
        df = df.sort_index()[dt1:dt2]

    if len(df) == 0:
        raise FileNotFoundError(
            f"Метеоданные ({mt_station}*.csv) не найдены в D:/data/MT за период {dt1} — {dt2}."
        )

    # 3. Построение 5-панельного графика (Matplotlib Agg)
    plt.rcParams.update({"font.size": 9})
    fig, axs = plt.subplots(
        5,
        2,
        sharex="col",
        figsize=(11, 10),
        dpi=130,
        gridspec_kw={
            "height_ratios": [1.6, 2.7, 1.6, 1.6, 1.6],
            "width_ratios": [40, 1], 
            "wspace": 0.04,
            },
    )
    
    for i in range(5):
        if i != 1:
            axs[i, 1].axis("off")

    main_ax = axs[1, 0]
    cax = axs[1, 1]

    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)

    for i in range(5):
        axs[i, 0].xaxis.set_major_locator(locator)
        axs[i, 0].xaxis.set_major_formatter(formatter)
        axs[i, 0].margins(x=0.01)
        axs[i, 0].grid(True, which="both", alpha=0.5)
        axs[i, 0].xaxis.set_minor_locator(mdates.HourLocator(interval=1))

    # Панель 1: Сейсмограмма
    axs[0, 0].plot(times_mpl, sig_data, linewidth=0.8)
    axs[0, 0].set_ylabel("мкм/с")
    axs[0, 0].legend([plt.Rectangle((0, 0), 1, 1)], [label], handletextpad=0, handlelength=0, loc="upper left")

    # Панель 2: Спектрограмма
    im = main_ax.imshow(
        sxx_db, aspect="auto", origin="lower", cmap="jet", extent=[tm1, tm2, f1, f2], interpolation="hanning"
    )
    main_ax.set_ylabel("Частота, Гц")
    main_ax.yaxis.set_minor_locator(MultipleLocator(0.5))
    main_ax.grid(True, which="both", color="white", alpha=0.4)
    fig.colorbar(im, cax=cax)

    # Панель 3: Скорость ветра
    ws_smooth = df["corrected_wind_speed"].rolling("1200s").mean()
    axs[2, 0].plot(ws_smooth, linewidth=1.0, color="#1f77b4")
    axs[2, 0].legend([f"MT.WS ({mt_station})"], handlelength=0, handletextpad=0, loc="upper left")
    axs[2, 0].set_ylabel("Ветер, м/с")

    # Панель 4: Векторы ветра (Quiver)
    df_res = df[["sin", "cos"]].resample("1200s").mean().dropna()
    lengths = np.hypot(df_res["sin"], df_res["cos"])
    u_vec = np.where(lengths > 0, df_res["sin"] / lengths, 0)
    v_vec = np.where(lengths > 0, df_res["cos"] / lengths, 0)

    x_num = mdates.date2num(df_res.index)
    axs[3, 0].get_yaxis().set_ticks([])
    axs[3, 0].set_ylabel("N\n↑\n↓\nS", rotation=0, labelpad=15, va="center", ha="center", fontsize=10)
    axs[3, 0].quiver(x_num, np.zeros_like(x_num), -u_vec, -v_vec, scale=14, width=0.0025, color="steelblue")

    # Панель 5: Направление ветра (откуда), град
    math_dir_deg = np.degrees(np.arctan2(df_res["sin"], df_res["cos"]))
    wind_dir_plot = (math_dir_deg.values) % 360.0
    diff = np.diff(wind_dir_plot)
    bad_indices = np.where(np.abs(diff) > 170)[0]
    for idx in bad_indices:
        wind_dir_plot[idx] = np.nan

    axs[4, 0].set_ylim(0, 360)
    axs[4, 0].yaxis.set_major_locator(MultipleLocator(90))
    axs[4, 0].yaxis.set_minor_locator(MultipleLocator(45))
    axs[4, 0].set_yticks([0, 90, 180, 270, 360])
    axs[4, 0].set_yticklabels(["С (0°)", "В (90°)", "Ю (180°)", "З (270°)", "С (360°)"])
    axs[4, 0].plot(df_res.index, wind_dir_plot, color="red", marker="o", markersize=2.5, linestyle="None")
    axs[4, 0].set_ylabel("Направление\nветра (откуда), град")

    plt.subplots_adjust(hspace=0.18)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    plot_b64 = base64.b64encode(buf.read()).decode("utf-8")

    return {
        "station": label,
        "mt_station": mt_station,
        "start_time": dt1.strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": dt2.strftime("%Y-%m-%d %H:%M:%S"),
        "max_wind_speed": round(float(df["corrected_wind_speed"].max()), 2),
        "mean_wind_speed": round(float(df["corrected_wind_speed"].mean()), 2),
        "plot_png": plot_b64,
    }
