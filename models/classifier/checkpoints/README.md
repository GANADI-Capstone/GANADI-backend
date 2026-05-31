# 모델 체크포인트 (배포)

AI 서버(`api/main.py`)가 로드하는 모델 파일을 이 디렉터리에 둡니다.  
**Git에는 포함하지 않습니다** (용량 큼). Docker는 볼륨 마운트로 사용합니다.

## PyTorch (기본: `INFERENCE_BACKEND=pytorch`)

| 파일 | 동물 | 크기 | CPU 속도 | 정확도 |
|------|------|------|----------|--------|
| `dog_best_random_split.pth` | 강아지 | ~214MB | ~440ms | baseline |
| `cat_best_random_split.pth` | 고양이 | ~168MB | ~440ms | baseline |

## ONNX FP32 (`INFERENCE_BACKEND=onnx`) — **정확도 동일, CPU 11× 빠름**

| 파일 | 동물 | 크기 | CPU 속도 | 정확도 |
|------|------|------|----------|--------|
| `dog_best_random_split.onnx` | 강아지 | ~71MB | ~38ms | = baseline |
| `cat_best_random_split.onnx` | 고양이 | ~56MB | ~38ms | = baseline |

## ONNX INT8 (`INFERENCE_BACKEND=onnx_int8`) — **EC2 권장, 용량 74%↓**

| 파일 | 동물 | 크기 | CPU 속도 | 정확도 |
|------|------|------|----------|--------|
| `dog_best_random_split_int8.onnx` | 강아지 | ~18MB | ~56ms | 샘플 Top-1 차이 가능* |
| `cat_best_random_split_int8.onnx` | 고양이 | ~15MB | ~56ms | 샘플 Top-1 차이 가능* |

\* Dynamic INT8은 FP32 대비 일부 경계 샘플에서 순위가 달라질 수 있습니다.  
정확도 검증: `python models/classifier/benchmark.py --animal dog` (TL Val 필요)

## 생성 방법 (학습 서버 / 로컬)

```bash
# 1) PyTorch → ONNX
ANIMAL_TYPE=dog python models/classifier/export_onnx.py
ANIMAL_TYPE=cat python models/classifier/export_onnx.py

# 2) ONNX → INT8 (Dynamic, 기본)
ANIMAL_TYPE=dog python models/classifier/quantize_onnx.py
ANIMAL_TYPE=cat python models/classifier/quantize_onnx.py

# 3) Static INT8 (더 강한 압축, calibration 필요)
ANIMAL_TYPE=dog python models/classifier/quantize_onnx.py --static

# 4) 벤치마크
python models/classifier/benchmark.py --animal dog
```

## 배포 (Docker Compose)

```yaml
ai:
  volumes:
    - ./models/classifier/checkpoints:/app/models/classifier/checkpoints:ro
  environment:
    INFERENCE_BACKEND: onnx_int8   # 또는 onnx / pytorch
```

```bash
cd backend
docker compose up -d --build ai
curl http://localhost:8000/health
# inference_backend, models_loaded 확인
```

## 환경변수

`backend/api/.env`:

```env
MODEL_VERSION=random_split
MODEL_CHECKPOINT_DIR=models/classifier/checkpoints
INFERENCE_BACKEND=onnx_int8
# EC2 CPU only: ORT_PROVIDERS=CPUExecutionProvider
```

## 학습 정보

- **학습:** `train_random_split.py`
- **평가:** `eval_multitask_topk.py`, `benchmark.py`
- **백본:** EfficientNet-B3, 300×300
- **체크포인트:** `model_state_dict` (EMA weights)

## 검증

```bash
python api/test_client.py --base-url http://localhost:8000 health
python api/test_client.py predict --image sample.jpg --animal dog
```
