#!/bin/bash
# Ablation Study Launcher for Unix/macOS
# This script activates the maf-py conda environment and runs the ablation study

echo "======================================================================"
echo "ABLATION STUDY LAUNCHER"
echo "======================================================================"

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "ERROR: conda command not found. Please install Miniconda/Anaconda."
    exit 1
fi

# Activate maf-py environment
echo ""
echo "Activating maf-py environment..."
eval "$(conda shell.bash hook)"
conda activate maf-py 2>/dev/null

# Verify activation
if ! python -c "import sys; print('✓ Environment: ' + sys.executable)" 2>/dev/null; then
    echo "ERROR: Failed to activate maf-py environment"
    echo "Please run: conda create -f environment.yml -n maf-py"
    exit 1
fi

# Navigate to project root
cd "$(dirname "$0")/.."

# Run verification
echo ""
echo "Running setup verification..."
python ablation/verify_setup.py
if [ $? -ne 0 ]; then
    echo "Setup verification failed!"
    exit 1
fi

# Run ablation study harness with arguments
echo ""
echo "Running ablation study harness..."
python ablation/run_ablation.py "$@"
