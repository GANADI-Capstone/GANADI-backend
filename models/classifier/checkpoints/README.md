# 모델 체크포인트 (배포)

AI 서버(`api/main.py`)가 로드하는 `.pth` 파일을 이 디렉터리에 둡니다.  
**Git에는 포함하지 않습니다** (용량 ~170–220MB/파일). Docker는 볼륨 마운트로 사용합니다.

## 필수 파일 (기본: `MODEL_VERSION=random_split`)

| 파일 | 동물 | 설명 | 대략 크기 |
|------|------|------|-----------|
| `dog_best_random_split.pth` | 강아지 | 멀티태스크 10헤드, TL random split | ~214MB |
| `cat_best_random_split.pth` | 고양이 | 멀티태스크 5헤드, TL random split | ~168MB |

## 레거시 (`MODEL_VERSION=legacy`)

| 파일 | 설명 |
|------|------|
| `dog_best.pth` | 구 단일/구 멀티태스크 |
| `cat_best.pth` | 구 단일/구 멀티태스크 |

## 배포 방법

### 1) 수동 복사 (Colab/학습 서버 → EC2)

```bash
# 학습 서버에서
scp models/classifier/checkpoints/dog_best_random_split.pth \
  user@server:/path/to/capstone_petcare/backend/models/classifier/checkpoints/

scp models/classifier/checkpoints/cat_best_random_split.pth \
  user@server:/path/to/capstone_petcare/backend/models/classifier/checkpoints/
```

### 2) Docker Compose (권장)

`backend/docker-compose.yml` 에 이미 마운트 설정:

```yaml
ai:
  volumes:
    - ./models/classifier/checkpoints:/app/models/classifier/checkpoints:ro
```

호스트의 `backend/models/classifier/checkpoints/` 에 `.pth` 를 넣은 뒤:

```bash
cd backend
docker compose up -d --build ai
```

### 3) 환경변수

`backend/api/.env` 또는 AI 컨테이너 env:

```env
MODEL_VERSION=random_split
MODEL_CHECKPOINT_DIR=models/classifier/checkpoints
# 선택: 개별 override
# MODEL_CHECKPOINT_DOG=/app/models/classifier/checkpoints/dog_best_random_split.pth
```

## 학습 정보

- **학습 스크립트:** `models/classifier/train_random_split.py`
- **평가:** `eval_multitask_topk.py`, `eval_vl_compare.py`
- **백본:** EfficientNet-B3, 300×300
- **체크포인트 키:** `model_state_dict` (EMA weights, `train_random_split.py` 저장)

## 검증

```bash
curl http://localhost:8000/health
# models_loaded.dog/cat true, checkpoints 경로 확인

python api/test_client.py health
python api/test_client.py predict --image sample.jpg --animal dog
```
