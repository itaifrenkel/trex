dataset=$1
n_estimators=$2
max_depth=$3
mem=$4
time=$5
partition=$6

# rs_list=(0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19)
rs_list=(20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39)

for rs in ${rs_list[@]}; do
    sbatch --mem=${mem}G \
           --time=$time \
           --partition=$partition \
           --job-name=R_MAPLE_$dataset \
           --output=jobs/logs/roar/$dataset \
           --error=jobs/errors/roar/$dataset \
           jobs/roar/maple_runner.sh $dataset $n_estimators \
           $max_depth $rs
done
