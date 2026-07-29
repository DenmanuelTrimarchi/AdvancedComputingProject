#!/usr/bin/env bash
# Single repeatable entry point for the canonical local macOS validation run.
# Never prints a private environment-variable value or writes a raw log to
# the repository -- only the step names and each tool's own stdout/stderr.
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

trap 'echo "ERROR: local run failed at line $LINENO"' ERR

echo "============================================================"
echo "Advanced Computing Project — Local macOS Run"
echo "============================================================"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: This runner is intended for macOS."
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo "ERROR: .env is missing."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "ERROR: .venv is missing."
  exit 1
fi

source .venv/bin/activate

# Quoted values in .env (required for OneDrive paths containing spaces) are
# preserved by `source`; `set -a` exports every variable it defines.
set -a
source .env
set +a

required_variables=(
  FACE_DATA_ROOT
  FACE_PROTOCOL_ROOT
  FACE_MODEL_ROOT
  FACE_CPLFW_RAW_ROOT
)

for variable in "${required_variables[@]}"; do
  value="${!variable:-}"
  if [[ -z "$value" ]]; then
    echo "ERROR: $variable is not configured."
    exit 1
  fi
done

echo "[1/9] Checking dependency contract"
python scripts/check_environment.py

echo "[2/9] Running the synthetic-fixture test suite"
pytest -v

echo "[3/9] Verifying pinned YuNet and SFace models"
python scripts/verify_models.py --model-root "$FACE_MODEL_ROOT"

echo "[4/9] Verifying LFW dataset and protocols"
python scripts/verify_lfw_dataset.py \
  --dataset-root "$FACE_DATA_ROOT/lfw_funneled" \
  --protocol-root "$FACE_PROTOCOL_ROOT"

echo "[5/9] Verifying raw CPLFW dataset and protocol"
python scripts/verify_cplfw_dataset.py \
  --dataset-root "$FACE_CPLFW_RAW_ROOT" \
  --protocol-root "$FACE_PROTOCOL_ROOT" \
  --image-variant raw

echo "[6/9] Running the complete five-experiment pipeline"
python scripts/run_complete_experiment.py \
  --dataset-root "$FACE_DATA_ROOT" \
  --protocol-root "$FACE_PROTOCOL_ROOT" \
  --model-root "$FACE_MODEL_ROOT" \
  --cplfw-dataset-root "$FACE_CPLFW_RAW_ROOT" \
  --cplfw-image-variant raw \
  --output-root results/aggregate

echo "[7/9] Checking public outputs"
python scripts/check_public_outputs.py \
  --paths results/aggregate results/report_evidence results/historical

echo "[8/9] Regenerating evidence locally"
rm -rf /tmp/advanced-computing-local-evidence
python scripts/generate_report_evidence.py \
  --results-root results/aggregate \
  --output-root /tmp/advanced-computing-local-evidence \
  --run-validation \
  --model-root "$FACE_MODEL_ROOT" \
  --lfw-dataset-root "$FACE_DATA_ROOT/lfw_funneled" \
  --cplfw-dataset-root "$FACE_CPLFW_RAW_ROOT" \
  --protocol-root "$FACE_PROTOCOL_ROOT"

echo "[9/9] Final local privacy validation"
python scripts/check_public_outputs.py \
  --paths results/aggregate /tmp/advanced-computing-local-evidence results/historical

echo "============================================================"
echo "LOCAL MACOS RUN COMPLETED SUCCESSFULLY"
echo "============================================================"
echo "Aggregate outputs: results/aggregate"
echo "Temporary evidence: /tmp/advanced-computing-local-evidence"
echo "No remote GitHub Actions runner was used."
