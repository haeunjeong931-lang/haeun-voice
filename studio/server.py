# -*- coding: utf-8 -*-
"""하은 보이스 스튜디오 - local server.

Runs with the GPT-SoVITS Windows package's own Python:
    runtime\\python.exe -I -u C:\\AI\\haeun-voice\\server.py
then open http://localhost:9880
"""
import os, sys, re, json, time, uuid, shutil, threading, datetime, traceback

APP_DIR = os.path.dirname(os.path.abspath(__file__))
GSV_DIR = os.environ.get("GSV_DIR", r"C:\AI\GPT-SoVITS-v2pro-20250604")
VOICE_DIR = os.environ.get("VOICE_DIR", r"C:\AI\voice-data")
MODEL_GPT = os.environ.get("MODEL_GPT", os.path.join(GSV_DIR, "GPT_weights_v2Pro", "haeun-e15.ckpt"))
MODEL_SOVITS = os.environ.get("MODEL_SOVITS", os.path.join(GSV_DIR, "SoVITS_weights_v2Pro", "haeun_e8_s640.pth"))
OUT_DIR = os.environ.get("OUT_DIR", os.path.join(APP_DIR, "outputs"))
LINE_DIR = os.path.join(OUT_DIR, "_lines")
PORT = int(os.environ.get("PORT", "9880"))

os.makedirs(LINE_DIR, exist_ok=True)
os.chdir(GSV_DIR)
sys.path.insert(0, GSV_DIR)
sys.path.insert(0, os.path.join(GSV_DIR, "GPT_SoVITS"))
sys.path.insert(0, APP_DIR)

import numpy as np
from typing import Optional, List
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel

import audio_clean

# Voice settings chosen by listening tests (2026-10-15)
TONES = {
    "bright": {
        "label": "밝게",
        "ref": "haeun_002.wav",
        "prompt": "이거 모르고 여행 가면 진짜 손해예요, 끝까지 봐 주세요.",
    },
    "calm": {
        "label": "차분하게",
        "ref": "haeun_029.wav",
        "prompt": "이 영상이 도움이 됐다면 팔로우하고 다음 편도 기다려 주세요.",
    },
}
GEN = dict(top_k=10, top_p=0.9, temperature=0.8, text_split_method="cut0", batch_size=1,
           repetition_penalty=1.35, parallel_infer=False, fragment_interval=0.3)
NATURAL_RATE = (3.6, 5.0)  # syllables/sec of the user's own recordings is ~4.2

state = {"ready": False, "error": None, "loading_since": time.time()}
tts = None
lock = threading.Lock()


def load_model():
    global tts
    try:
        from TTS_infer_pack.TTS import TTS, TTS_Config
        cfg = TTS_Config({"custom": {
            "device": "cpu", "is_half": False, "version": "v2Pro",
            "t2s_weights_path": MODEL_GPT, "vits_weights_path": MODEL_SOVITS,
            "bert_base_path": "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large",
            "cnhuhbert_base_path": "GPT_SoVITS/pretrained_models/chinese-hubert-base",
        }})
        tts = TTS(cfg)
        state["ready"] = True
        print("[voice studio] model ready", flush=True)
    except Exception as e:
        state["error"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()


def syllable_rate(audio, sr, text):
    n = len(re.findall("[가-힣]", text)) or max(1, len(text) // 2)
    a = np.abs(audio.astype(np.float32))
    if a.max() == 0:
        return 0.0
    a = a / a.max()
    idx = np.where(a > 0.03)[0]
    dur = (idx[-1] - idx[0]) / sr if len(idx) > 1 else len(audio) / sr
    return n / max(dur, 0.1)


def synth(text, tone, speed, seed):
    t = TONES[tone]
    req = dict(GEN, text=text, text_lang="ko", prompt_lang="ko",
               ref_audio_path=os.path.join(VOICE_DIR, t["ref"]), prompt_text=t["prompt"],
               speed_factor=float(speed), seed=int(seed))
    sr, parts = None, []
    for sr_, chunk in tts.run(req):
        sr = sr_
        parts.append(chunk)
    return sr, np.concatenate(parts)


app = FastAPI()


class LineReq(BaseModel):
    text: str
    tone: str = "bright"
    speed: float = 0.9
    seed: Optional[int] = None


class ExportReq(BaseModel):
    title: str = ""
    ids: List[str]
    gap: float = 0.35


@app.get("/")
def index():
    return FileResponse(os.path.join(APP_DIR, "index.html"))


@app.get("/api/status")
def status():
    return {"ready": state["ready"], "error": state["error"],
            "loading_seconds": int(time.time() - state["loading_since"]),
            "tones": {k: v["label"] for k, v in TONES.items()}, "out_dir": OUT_DIR}


@app.post("/api/line")
def make_line(r: LineReq):
    if not state["ready"]:
        raise HTTPException(503, "아직 목소리 모델을 불러오는 중이에요.")
    text = re.sub(r"\s+", " ", r.text).strip()
    if not text:
        raise HTTPException(400, "문장이 비어 있어요.")
    if r.tone not in TONES:
        raise HTTPException(400, "알 수 없는 톤이에요.")
    speed = min(1.3, max(0.7, r.speed))
    seeds = [r.seed] if r.seed is not None else []
    seeds += [int(np.random.randint(1, 2**31 - 1)) for _ in range(3)]
    t0 = time.time()
    best = None
    with lock:
        for seed in seeds[:3]:
            sr, audio = synth(text, r.tone, speed, seed)
            rate = syllable_rate(audio, sr, text) * speed  # compare at 1.0x pace
            nsyl = len(re.findall("[가-힣]", text))
            ok = nsyl < 12 or NATURAL_RATE[0] <= rate <= NATURAL_RATE[1] * 1.1
            if best is None or ok:
                best = (sr, audio, seed, rate, ok)
            if ok:
                break
    sr, audio, seed, rate, ok = best
    clean = audio_clean.clean(audio, sr)
    lid = uuid.uuid4().hex[:12]
    sf.write(os.path.join(LINE_DIR, lid + ".wav"), clean, sr, subtype="PCM_16")
    with open(os.path.join(LINE_DIR, lid + ".json"), "w", encoding="utf-8") as f:
        json.dump({"text": text, "tone": r.tone, "speed": speed, "seed": seed, "sr": sr}, f, ensure_ascii=False)
    return {"id": lid, "url": f"/line/{lid}.wav", "seed": seed, "seconds": round(len(clean) / sr, 1),
            "took": round(time.time() - t0), "maybe_skipped": not ok}


@app.get("/line/{name}")
def get_line(name: str):
    p = os.path.join(LINE_DIR, os.path.basename(name))
    if not os.path.exists(p):
        raise HTTPException(404)
    return FileResponse(p, media_type="audio/wav")


def safe_title(s):
    s = re.sub(r'[\\/:*?"<>|\n\r\t]', " ", s).strip()
    return re.sub(r"\s+", "_", s)[:40] or "voice"


@app.post("/api/export")
def export(r: ExportReq):
    if not r.ids:
        raise HTTPException(400, "저장할 문장이 없어요.")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    name = f"{stamp}_{safe_title(r.title)}"
    folder = os.path.join(OUT_DIR, name)
    os.makedirs(folder, exist_ok=True)
    pieces, sr, script = [], None, []
    for i, lid in enumerate(r.ids, 1):
        lid = os.path.basename(str(lid))
        wav = os.path.join(LINE_DIR, lid + ".wav")
        if not os.path.exists(wav):
            raise HTTPException(400, f"{i}번 문장 음성을 찾을 수 없어요. 다시 만들어 주세요.")
        x, sr = sf.read(wav, dtype="float32")
        meta = json.load(open(os.path.join(LINE_DIR, lid + ".json"), encoding="utf-8"))
        shutil.copy(wav, os.path.join(folder, f"{i:02d}.wav"))
        script.append(f"{i:02d}\t{meta['text']}")
        pieces.append(x)
        if i < len(r.ids):
            pieces.append(np.zeros(int(sr * max(0.0, min(2.0, r.gap))), dtype=np.float32))
    full = np.concatenate(pieces)
    sf.write(os.path.join(folder, "전체.wav"), full, sr, subtype="PCM_16")
    with open(os.path.join(folder, "대본.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(script) + "\n")
    return {"folder": folder, "name": name, "seconds": round(len(full) / sr, 1),
            "url": f"/out/{name}/전체.wav", "count": len(r.ids)}


@app.get("/api/history")
def history():
    items = []
    for d in sorted(os.listdir(OUT_DIR), reverse=True):
        p = os.path.join(OUT_DIR, d)
        if d.startswith("_") or not os.path.isdir(p) or not os.path.exists(os.path.join(p, "전체.wav")):
            continue
        try:
            first = open(os.path.join(p, "대본.txt"), encoding="utf-8").readline().split("\t", 1)[-1].strip()
        except Exception:
            first = ""
        info = sf.info(os.path.join(p, "전체.wav"))
        items.append({"name": d, "url": f"/out/{d}/전체.wav", "seconds": round(info.duration, 1),
                      "lines": len([f for f in os.listdir(p) if re.match(r"\d\d\.wav$", f)]), "first": first})
    return items[:50]


@app.get("/out/{name}/{file}")
def get_out(name: str, file: str):
    p = os.path.join(OUT_DIR, os.path.basename(name), os.path.basename(file))
    if not os.path.exists(p):
        raise HTTPException(404)
    return FileResponse(p, media_type="audio/wav", filename=f"{os.path.basename(name)}.wav")


@app.post("/api/open-folder")
def open_folder(payload: dict):
    target = os.path.join(OUT_DIR, os.path.basename(payload.get("name", ""))) if payload.get("name") else OUT_DIR
    if os.name == "nt" and os.path.isdir(target):
        os.startfile(target)
        return {"ok": True}
    return {"ok": False, "path": target}


if __name__ == "__main__":
    threading.Thread(target=load_model, daemon=True).start()
    print(f"[voice studio] open http://localhost:{PORT}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
