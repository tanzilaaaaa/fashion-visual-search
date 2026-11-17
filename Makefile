.PHONY: setup test lint smoke-data dev-index dev-api dev-web bench kaggle-build kaggle-status kaggle-logs kaggle-download

PY := .venv/bin/python
SMOKE := /tmp/df2_synthetic

setup:        ## create the venv and install everything
	python3.11 -m venv .venv
	.venv/bin/pip install -r backend/requirements-dev.txt -r backend/requirements-ml.txt
	.venv/bin/pip install -e "ml[dev]"
	cd frontend && npm install

test:         ## run every test suite
	cd backend && ../$(PY) -m pytest -q
	cd ml && ../$(PY) -m pytest -q
	cd frontend && npm test

lint:
	.venv/bin/ruff check backend ml
	cd frontend && npm run lint

smoke-data:   ## synthetic DeepFashion2-format data (plumbing checks only, not for metrics)
	$(PY) ml/scripts/make_synthetic_df2.py --out $(SMOKE) --images 450

dev-index:    ## small local index; override with DATASET=/path/to/df2 ITEMS=3000 FINETUNE=1
	cd ml && ../$(PY) -m fvs_ml.pipeline --dataset-root $(or $(DATASET),$(SMOKE)) \
		--output-dir ../backend/artifacts --target-items $(or $(ITEMS),3000) --num-workers 0 --batch-size 64 \
		$(if $(FINETUNE),--finetune --ft-epochs 15,)

dev-api:
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000

dev-web:
	cd frontend && npm run dev

bench:
	cd backend && ../$(PY) scripts/benchmark.py

# Real 50k index + fine-tuned adapter on a Kaggle GPU. Needs Kaggle API credentials
# (~/.kaggle/access_token) and a phone-verified account. See docs/DEPLOYMENT.md §2.
kaggle-build:     ## push the self-contained build kernel and start it
	$(PY) ml/kaggle/run_kaggle.py push

kaggle-status:
	$(PY) ml/kaggle/run_kaggle.py status

kaggle-logs:      ## build log (after the run finishes)
	$(PY) ml/kaggle/run_kaggle.py logs

kaggle-download:  ## fetch the finished artifacts into backend/artifacts/
	$(PY) ml/kaggle/run_kaggle.py download
