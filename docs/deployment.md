# Deployment

## 현재 상태

**이 프로젝트는 현재 로컬 실행만 지원하며, 어떤 클라우드 서비스에도 배포되지
않았다.** Streamlit Community Cloud 등에 배포하는 것은 저장소를 외부에
공개하는 행위라 사용자 승인 없이 진행하지 않는다 — 배포를 원하면 별도로
요청할 것.

## 로컬 실행 순서

### 1. 환경 준비

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 원본 데이터 확보 (비공개 — 직접 다운로드 필요)

공식 출처(https://recsys.synerise.com/data-set)에서 `synerise_dataset.tar.gz`
를 받아 압축을 풀고 `data/raw/synerise_dataset/`에 위치시킨다. 상세 절차는
`reports/phase1_download_log.md` 참고. 원본 데이터는 라이선스(CC BY-NC 4.0)상
이 저장소에 포함되어 있지 않다.

### 3. 데이터마트 빌드

```bash
python3 scripts/build_database.py
```

`data/processed/crm.duckdb`에 staging → intermediate → mart(11개) 전체가
빌드된다 (약 5\~10분 소요, page_visit 1.99억 행 처리 포함).

### 4. 모델 학습 및 타기팅 시뮬레이션 (선택)

```bash
python3 scripts/train_model_a.py
python3 scripts/train_model_b.py
python3 scripts/build_targeting_simulation.py
```

### 5. 대시보드용 데이터 내보내기 + 실행

```bash
python3 scripts/build_dashboard_data.py
streamlit run app/Home.py
```

`http://localhost:8501`에서 확인.

### 6. LLM CRM 리포트 (선택)

API 키 없이도 mock 백엔드로 동작한다.

```bash
python3 scripts/generate_crm_report.py
```

실제 LLM을 쓰려면 `.env.example`을 `.env`로 복사한 뒤
`ANTHROPIC_API_KEY` 또는 `OPENAI_API_KEY`를 채운다.

### 7. 테스트

```bash
pytest tests/ -q
```

## 향후 클라우드 배포를 고려한다면

- Streamlit Community Cloud: `app/Home.py`를 엔트리포인트로 지정, `data/dashboard/*.csv`
  (약 15KB, 이미 집계된 소용량 파일)만 포함하면 됨 — `data/processed/*.duckdb`
  (3GB+, gitignore 대상)는 배포에 불필요.
- 원본 데이터·DuckDB 파일은 배포 환경에도 포함하지 않는다 (CLAUDE.md 33번).
