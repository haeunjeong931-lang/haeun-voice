# 하은 보이스 스튜디오

대본을 넣으면 내 목소리로 읽어 주는 로컬 TTS 대시보드. [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) v2Pro로 학습한 목소리 모델을 Windows 노트북(CPU)에서 돌린다.

> 녹음 파일과 학습된 목소리 모델(`.pth`, `.ckpt`)은 개인 데이터라 이 저장소에 포함하지 않는다.

## 구성

| 폴더 | 내용 |
|---|---|
| `recorder/voice-booth.html` | 학습용 녹음 대시보드. 문장 40개를 한 줄씩 보여 주고 Space로 녹음, WAV + GPT-SoVITS용 `.list` 파일을 폴더에 바로 저장 |
| `tools/` | GPT-SoVITS Windows 패키지 자동 설치 스크립트와 실행 파일(로그를 `C:\AI\webui-log.txt`에 남김) |
| `studio/` | 보이스 스튜디오: FastAPI 서버 + 웹 화면 |

## 보이스 스튜디오

- 대본을 문장 단위로 나눠 하나씩 생성, 마음에 안 드는 문장만 `다시 만들기`
- 톤 2가지(밝게 / 차분하게), 말 속도, 문장 사이 쉼 조절
- 저장하면 `outputs/<날짜>_<제목>/` 에 `01.wav, 02.wav…`, `전체.wav`, `대본.txt`
- 후처리(`audio_clean.py`, numpy·scipy만 사용): 80Hz 하이패스, 스펙트럴 게이팅 잡음 제거(80%), -16 LUFS 라우드니스 정규화, 소프트 리미터
- 단어를 건너뛴 결과는 말 속도(음절/초)로 감지해 최대 3번 다시 생성

### 확정한 생성 설정 (청취 테스트로 결정)

| 항목 | 값 | 이유 |
|---|---|---|
| GPT 모델 | 15 에폭 | |
| SoVITS 모델 | 8 에폭 | |
| 문장 분할 | `cut0` (쉼표에서 안 자름) | 쉼표마다 끊으면 조각 끝에서 음이 뚝 떨어짐 |
| 말 속도 | 0.9× | 기본 속도가 실제 말보다 약 20% 빨랐음 |
| 샘플링 | top_k 10, top_p 0.9, temperature 0.8 | |

### 실행

1. `studio/` 파일을 `C:\AI\haeun-voice\` 에 둔다.
2. `보이스 스튜디오.bat` 더블클릭 → 브라우저에서 `http://localhost:9880` 이 열린다.

경로는 환경 변수 `GSV_DIR`, `VOICE_DIR`, `MODEL_GPT`, `MODEL_SOVITS`, `OUT_DIR`, `PORT` 로 바꿀 수 있다.
