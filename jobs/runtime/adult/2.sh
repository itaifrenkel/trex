#!/bin/bash
#SBATCH --partition=long
#SBATCH --job-name=runtime
#SBATCH --output=jobs/logs/runtime/adult2
#SBATCH --error=jobs/errors/runtime/adult2
#SBATCH --time=1-00:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=5
#SBATCH --account=uoml
module load python3/3.6.1

dataset='adult'
n_estimators=100
max_depth=5

tree_kernels=('tree_output' 'leaf_path' 'leaf_output')
rs_list=(1 2 3 4 5)

for tree_kernel in ${tree_kernels[@]}; do
    for i in ${!rs_list[@]}; do
        python3 experiments/scripts/runtime.py \
          --dataset $dataset \
          --n_estimators $n_estimators \
          --max_depth $max_depth \
          --rs ${rs_list[$i]} \
          --trex \
          --tree_kernel $tree_kernel \
          --kernel_model 'klr'
    done
done