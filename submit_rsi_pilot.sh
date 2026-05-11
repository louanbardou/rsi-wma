#!/bin/bash
#SBATCH --job-name=rsi_pilot
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=/mnt/fac/CX500007_DS1/bardou/rsi-wma/logs/rsi_pilot_%j.out
#SBATCH --error=/mnt/fac/CX500007_DS1/bardou/rsi-wma/logs/rsi_pilot_%j.err

mkdir -p /mnt/fac/CX500007_DS1/bardou/rsi-wma/logs


source /mnt/fac/CX500007_DS1/bardou/wma-pipeline/activate_env.sh

cd /mnt/fac/CX500007_DS1/bardou/rsi-wma
python run_rsi_pilot.py
