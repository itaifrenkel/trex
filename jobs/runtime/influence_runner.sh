#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --account=uoml
module load python3/3.6.1

dataset=$1
n_estimators=$2
max_depth=$3
rs=$4

python3 scripts/experiments/runtime.py \
  --inf_k 0 \
  --dataset $dataset \
  --n_estimators $n_estimators \
  --max_depth $max_depth \
  --rs $rs
