#!/bin/bash
echo "Workingdir: $PWD";
echo "Started at $(date)";
echo "Running job $SLURM_JOB_NAME using $SLURM_JOB_CPUS_PER_NODE cpus per node with given JID $SLURM_JOB_ID on queue $SLURM_JOB_PARTITION";
echo "Environment variables"
env

# An example of using templates
for i in {1..$$UPPERBOUND$$};
  do echo $RANDOM >> integers.txt;
done
echo "Finished at $(date)";

# They templates could also be used for more advanced stuff. E.g.

# git clone https://github.com/EleutherAI/lm-evaluation-harness
# cd lm-evaluation-harness
# pip install -e .
# git checkout $$GIT_COMMIT_OR_BRANCH$$   # The commit or branch could be specified in the yaml file.
# pip install evaluate  # required for big-refactor branch

# # 2.7B model from microsoft, principally trained on coding but also artificial NLP tasks
# # https://huggingface.co/microsoft/phi-2
# model=microsoft/phi-2

# # 7B models will OOMs on 2080/3080
# # model=lvkaokao/mistral-7b-finetuned-orca-dpo-v2

# # Evaluate only 10 examples per task
# # Download model and datasets, ~6 min
# time PYTHONPATH=/home/$USER/lm-evaluation-harness python -m lm_eval \
#     --model hf \
#     --model_args pretrained=$model,dtype="bfloat16" \
#     --tasks mmlu \
#     --device cuda:0 \
#     --batch_size 1 \
#     --num_fewshot=0 \
#     --limit 10
