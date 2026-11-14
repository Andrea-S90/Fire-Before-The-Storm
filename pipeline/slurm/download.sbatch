#!/usr/bin/env bash
#SBATCH --job-name=ashwatch-dl
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=06:00:00
#SBATCH --output=logs/ashwatch_dl_%j.log
# Only if your cluster has a partition with internet access (often called "transfer", "dtn" or "io"):
#   sbatch --partition=<transfer-partition> slurm/download.sbatch
# Otherwise run scripts/run_downloads.sh on the login node with nohup.
set -uo pipefail
# module load miniforge3; source activate ashwatch
bash scripts/run_downloads.sh
