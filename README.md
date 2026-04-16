# 반려동물 안구질환 AI 모델

세종대학교 컴퓨터공학과 캡스톤디자인 2026-1

---

## 프로젝트 개요

반려동물(강아지/고양이) 안구 이미지를 입력받아 질환을 AI로 스크리닝하는 모델.  
보호자가 스마트폰으로 찍은 사진을 넣으면 질환별 확률을 출력합니다.

웹은 `frontend/`, 앱·DB 연동 API는 `backend/`, 이미지 추론 API는 `api/`에서 각각 실행합니다.

조직 GitHub에 **프론트·백·AI 레포가 분리**되어 있을 때, 클론 후 포트·환경변수까지 한 번에 맞추는 방법은 [docs/GANADI_LOCAL_RUN.md](docs/GANADI_LOCAL_RUN.md)를 참고하세요.

---

## 환경 설정

Python **3.10+** 권장. macOS·Windows·Linux 모두 동일한 저장소 구조로 동작합니다.

**가상환경(`venv`) 폴더는 OS마다 생기는 구조가 다릅니다.** 이건 정상입니다.

| | macOS / Linux | Windows |
|---|----------------|---------|
| 실행 파일 위치 | `venv/bin/python` | `venv\Scripts\python.exe` |
| 활성화 스크립트 | `venv/bin/activate` | `venv\Scripts\activate.bat` 또는 `Activate.ps1` |
| 경로 구분자 | `/` (슬래시) | `\` (백슬래시) |

명령은 똑같이 `python -m venv venv` 인데, Python이 OS에 맞는 레이아웃으로 만듭니다. **`venv/`는 Git에 올리지 않으므로**(`.gitignore`) 맥에서 만든 폴더를 윈도로 복사할 필요도 없고, **각자 PC에서 새로 만들면** 됩니다.

### 1. 가상환경 생성

**macOS / Linux**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell 또는 CMD)**

```bat
py -3 -m venv venv
venv\Scripts\activate
```

(`python` / `py` 중 설치에 맞는 쪽을 사용하면 됩니다.)

**동작 확인** — 프롬프트 앞에 `(venv)`가 보이면 성공입니다.

```bash
python -c "import sys; print(sys.executable)"
# 경로 끝에 .../venv/bin/python (맥·리눅스) 또는 ...\venv\Scripts\python.exe (윈도) 가 나와야 합니다.
```

#### 가상환경이 안 될 때

**macOS**

- `python3: command not found` → Xcode CLI 도구 또는 [python.org](https://www.python.org/downloads/)에서 Python 3.10+ 설치 후 터미널을 다시 엽니다.
- `Permission denied` → **시스템** Python에 `sudo`로 `venv` 만들지 말고, 위처럼 **일반 사용자** 권한으로 프로젝트 폴더 안에서 다시 시도합니다.
- 이미 깨진 `venv` 폴더가 있으면 삭제 후 재생성: `rm -rf venv` → `python3 -m venv venv`

**Windows**

- `py` / `python` 둘 다 안 됨 → [python.org](https://www.python.org/downloads/windows/) 설치 시 **“Add python.exe to PATH”** 체크. Microsoft Store 버전만 있으면 가끔 `venv`가 꼬이므로, 공식 설치본을 쓰는 것을 권장합니다.
- PowerShell에서 `activate` 실행이 막힘 → 한 번만 실행:
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
  ```
  그 다음 `venv\Scripts\Activate.ps1` (또는 CMD에서는 `venv\Scripts\activate.bat`).
- **백엔드**는 저장소 기준 `backend` 폴더로 들어가서 **별도** 가상환경을 만듭니다.
  ```bat
  cd backend
  py -3 -m venv venv
  venv\Scripts\activate
  pip install -r requirements.txt
  ```

**Linux**

- `ensurepip` 오류 → `sudo apt install python3-venv` (Ubuntu/Debian 계열) 후 다시 `python3 -m venv venv`.

### 2. 패키지 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

루트 `requirements.txt`는 AI(`api/`)용입니다. 백엔드만 쓸 때는 `backend/requirements.txt`를 따로 설치하세요.

### 3. 디바이스 가속 확인

**macOS (Apple Silicon)** — MPS:

```bash
python -c "import torch; print('MPS:', torch.backends.mps.is_available())"
```

**Windows / Linux** — NVIDIA GPU가 있으면 CUDA가 잡히는지 확인:

```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

GPU가 없거나 CUDA 미설치면 **CPU로 동작**합니다(느려질 수 있음).

### 4. OS별로 자주 하는 설정

| 항목 | macOS / Linux | Windows |
|------|----------------|---------|
| 프론트 실행 | `cd frontend && npm install && npm run dev` | 동일 |
| 포트 점유 확인 | `lsof -i :8000` | `netstat -ano` 후 8000 포트 PID 확인 |
| Git 줄바꿈 | 기본 LF 유지 가능 | `git config --global core.autocrlf true` 권장 |

PDF 한글은 **macOS**는 AppleGothic/나눔, **Windows**는 맑은 고딕(`malgun.ttf`) 등이 있으면 `api` 서버가 자동으로 찾습니다.

---

## 프로젝트 구조

```
capstone_petcare/
├── venv/                   # 가상환경 (git 제외)
├── eye_data/              # 데이터셋
├── models/
│   └── classifier/        # EfficientNet-B3 질환 분류 모델
│       ├── dataset.py
│       ├── model.py
│       ├── train.py
│       └── predict.py
├── api/                   # AI 추론 FastAPI (예: 포트 8000)
│   └── main.py
├── backend/               # 앱 백엔드 API (DB·인증·진단 연계)
├── frontend/            # 웹 UI (Vite + React)
├── requirements.txt       # 루트(AI) 패키지 의존성
├── .gitignore
└── README.md
```

---

## 모델 구성

### EfficientNet-B3 멀티태스크 질환 분류
- 공유 백본(EfficientNet-B3) + 질환별 독립 분류 헤드
- 강아지/고양이 각각 별도 모델로 학습
- 각 질환 헤드가 독립적으로 유무/중증도 분류
- 복합 질환 동시 감지 가능

---

## 강아지 모델 질환 헤드

| 질환 | 클래스 | 폴더 |
|------|--------|------|
| 결막염 | 무/유 | eye_data/TL1/개/안구/일반/결막염/ |
| 궤양성각막질환 | 무/상/하 | eye_data/TL1/개/안구/일반/궤양성각막질환/ |
| 백내장 | 무/초기/비성숙/성숙 | eye_data/TL1/개/안구/일반/백내장/ |
| 비궤양성각막질환 | 무/상/하 | eye_data/TL1/개/안구/일반/비궤양성각막질환/ |
| 색소침착성각막염 | 무/유 | eye_data/TL1/개/안구/일반/색소침착성각막염/ |
| 안검내반증 | 무/유 | eye_data/TL2/개/안구/일반/안검내반증/ |
| 안검염 | 무/유 | eye_data/TL2/개/안구/일반/안검염/ |
| 안검종양 | 무/유 | eye_data/TL2/개/안구/일반/안검종양/ |
| 유루증 | 무/유 | eye_data/TL2/개/안구/일반/유루증/ |
| 핵경화 | 무/유 | eye_data/TL2/개/안구/일반/핵경화/ |

## 고양이 모델 질환 헤드

| 질환 | 클래스 | 폴더 |
|------|--------|------|
| 각막궤양 | 무/유 | eye_data/TL2/고양이/안구/일반/각막궤양/ |
| 각막부골편 | 무/유 | eye_data/TL2/고양이/안구/일반/각막부골편/ |
| 결막염 | 무/유 | eye_data/TL2/고양이/안구/일반/결막염/ |
| 비궤양성각막염 | 무/유 | eye_data/TL2/고양이/안구/일반/비궤양성각막염/ |
| 안검염 | 무/유 | eye_data/TL2/고양이/안구/일반/안검염/ |

---

## 데이터셋 구조

```
eye_data/
├── TL1/          # 라벨링 데이터 (크롭 완료 400×400)
│   └── 개/안구/일반/{질환}/{중증도}/
│       ├── crop_D0_xxxxx.jpg   # 크롭 이미지
│       └── crop_D0_xxxxx.json  # 라벨 JSON
├── TL2/          # 라벨링 데이터 추가 질환
│   ├── 개/안구/일반/{질환}/{중증도}/
│   └── 고양이/안구/일반/{질환}/{중증도}/
├── VL/           # Validation 라벨링 데이터
└── TS1/          # 원천 데이터 (원본 고해상도 3264×2448)
    └── 개/안구/일반/{질환}/{중증도}/
        ├── D0_xxxxx.jpg    # 원본 이미지 (crop_ 없음)
        └── D0_xxxxx.json   # JSON (label_bbox 포함)
```

### 핵심 JSON 필드

```json
{
  "images": {
    "meta": {
      "file_name": "D0_02f99e22-xxxx.jpg",
      "device": "일반카메라",
      "breed": "말티즈",
      "age": 3,
      "gender": "수컷"
    }
  },
  "label": {
    "label_deleted": 0,
    "label_disease_nm": "결막염",
    "label_disease_lv_1": "유",
    "label_disease_lv_2": "유",
    "label_disease_lv_3": "유",
    "label_bbox": [x, y, w, h]
  }
}
```

### 데이터 필터 조건

```python
if label["label_deleted"] == 1: skip          # 삭제된 데이터
if device in ["안구초음파", "안저카메라"]: skip  # 전문 장비 이미지 제외
label = label["label_disease_lv_3"]            # 확정 라벨만 사용
```

---

## 기술 스택

- Python 3.10+
- PyTorch 2.x + MPS (MacBook M4)
- timm (EfficientNet-B3)
- Albumentations (augmentation)
- pytorch-grad-cam (GradCAM 히트맵)
- FastAPI + Uvicorn (AI 서버)
- ONNX Runtime (추론 최적화)

---

## UUID 매칭 방법 (TS ↔ TL)

```
TL 파일: crop_D0_02f99e22-60a5-11ec-8402-0a7404972c70.jpg
TS 파일:       D0_02f99e22-60a5-11ec-8402-0a7404972c70.jpg

"crop_" 제거하면 동일한 UUID → 1:1 매칭 가능
TL JSON의 label_bbox를 TS 원본 이미지와 매칭해 학습·전처리 파이프라인에 활용
```

---

## 개발 단계

1. ✅ 환경 설정 및 프로젝트 구조 생성
2. ⬜ EfficientNet-B3 질환 분류 모델 학습·튜닝
3. ✅ FastAPI 기반 추론 API (`api/`)
4. ⬜ 모델 최적화 및 배포

---

## 라이선스

세종대학교 컴퓨터공학과 캡스톤디자인 프로젝트
