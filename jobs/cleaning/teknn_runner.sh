#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --account=uoml
module load python3/3.6.1

dataset=$1
tree_type=$2
n_estimators=$3
max_depth=$4
check_pct=$5
train_frac=$6
tree_kernel=$7
rs=$8

python3 scripts/experiments/cleaning.py \
  --teknn \
  --tree_type $tree_type \
  --dataset $dataset \
  --n_estimators $n_estimators \
  --max_depth $max_depth \
  --check_pct $check_pct \
  --tree_kernel $tree_kernel \
  --train_frac $train_frac \
  --rs $rs
