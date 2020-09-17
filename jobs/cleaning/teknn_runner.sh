#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --account=uoml
module load python3/3.6.1

dataset=$1
n_estimators=$2
max_depth=$3
check_pct=$4
train_frac=$5
tree_kernel=$6
rs=$7

python3 scripts/experiments/cleaning.py \
  --teknn \
  --dataset $dataset \
  --n_estimators $n_estimators \
  --max_depth $max_depth \
  --check_pct $check_pct \
  --tree_kernel $tree_kernel \
  --train_frac $train_frac \
  --rs $rs
