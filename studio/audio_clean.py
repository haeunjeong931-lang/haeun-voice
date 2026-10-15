"""Post-processing for generated voice, numpy + scipy only (both ship with GPT-SoVITS).

1. 80 Hz high-pass (removes rumble)
2. Stationary spectral gating: noise profile from the quietest frames, soft mask,
   noise reduced by PROP (0.6 = 60%) - gentle enough not to thin the voice
3. 10 ms fades + 0.15 s silence padding
4. Loudness normalised to -16 LUFS (ITU-R BS.1770 K-weighting, gated) - typical for Reels/Shorts
5. Soft limiter: peaks rounded off toward a -1 dBFS ceiling
"""
import numpy as np
from scipy.signal import butter, sosfiltfilt, stft, istft, lfilter
from scipy.ndimage import uniform_filter

PROP = 0.8
TARGET_LUFS = -16.0


def _biquad(G, Q, fc, rate, kind):
    A = 10 ** (G / 40.0)
    w0 = 2.0 * np.pi * (fc / rate)
    alpha = np.sin(w0) / (2.0 * Q)
    c = np.cos(w0)
    if kind == "high_shelf":
        b = [A * ((A + 1) + (A - 1) * c + 2 * np.sqrt(A) * alpha),
             -2 * A * ((A - 1) + (A + 1) * c),
             A * ((A + 1) + (A - 1) * c - 2 * np.sqrt(A) * alpha)]
        a = [(A + 1) - (A - 1) * c + 2 * np.sqrt(A) * alpha,
             2 * ((A - 1) - (A + 1) * c),
             (A + 1) - (A - 1) * c - 2 * np.sqrt(A) * alpha]
    else:  # high_pass
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
        a = [1 + alpha, -2 * c, 1 - alpha]
    return np.array(b) / a[0], np.array(a) / a[0]


def loudness_lufs(x, sr):
    y = x.astype(np.float64)
    for args in [(4.0, 1 / np.sqrt(2), 1500.0, sr, "high_shelf"), (0.0, 0.5, 38.0, sr, "high_pass")]:
        b, a = _biquad(*args)
        y = lfilter(b, a, y)
    blk, step = int(0.4 * sr), int(0.1 * sr)
    if len(y) < blk:
        y = np.pad(y, (0, blk - len(y)))
    z = np.array([np.mean(y[i:i + blk] ** 2) for i in range(0, len(y) - blk + 1, step)])
    with np.errstate(divide="ignore"):
        l = -0.691 + 10 * np.log10(z + 1e-20)
    z = z[l >= -70]
    if len(z) == 0:
        return -70.0
    rel = -0.691 + 10 * np.log10(z.mean()) - 10
    z2 = z[(-0.691 + 10 * np.log10(z)) >= rel]
    return float(-0.691 + 10 * np.log10(z2.mean()))


def spectral_gate(x, sr, prop=PROP):
    nper = 1024
    f, t, Z = stft(x, sr, nperseg=nper, noverlap=nper * 3 // 4)
    mag = np.abs(Z)
    db = 20 * np.log10(mag + 1e-10)
    frame_energy = db.mean(axis=0)
    quiet = np.argsort(frame_energy)[: max(5, int(len(frame_energy) * 0.15))]
    mu = db[:, quiet].mean(axis=1, keepdims=True)
    sd = db[:, quiet].std(axis=1, keepdims=True)
    thresh = mu + 1.5 * sd
    mask = (db > thresh).astype(np.float64)
    # smooth over ~300 Hz and ~60 ms like noisereduce's defaults
    fbins = max(1, int(300 / (sr / nper)))
    tbins = max(1, int(0.06 / ((nper // 4) / sr)))
    mask = uniform_filter(mask, size=(fbins, tbins))
    gain = 1.0 - (1.0 - mask) * prop
    _, y = istft(Z * gain, sr, nperseg=nper, noverlap=nper * 3 // 4)
    return y[: len(x)]


def clean(x, sr, prop=PROP, target=TARGET_LUFS):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if np.abs(x).max() > 1.5:  # int16 range -> float
        x = x / 32768.0
    x = sosfiltfilt(butter(4, 80, "highpass", fs=sr, output="sos"), x)
    x = spectral_gate(x, sr, prop)
    f = int(sr * 0.01)
    x[:f] *= np.linspace(0, 1, f)
    x[-f:] *= np.linspace(1, 0, f)
    pad = np.zeros(int(sr * 0.15))
    x = np.concatenate([pad, x, pad])
    x *= 10 ** ((target - loudness_lufs(x, sr)) / 20)
    thr, ceil = 0.6, 0.891
    a = np.abs(x)
    over = a > thr
    x[over] = np.sign(x[over]) * (thr + (ceil - thr) * np.tanh((a[over] - thr) / (ceil - thr)))
    return x.astype(np.float32)
