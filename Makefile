# One-line full pipeline:  make all
# Target repo is picked via env vars, e.g.:
#   REPO_OWNER=raysk4ever REPO_NAME=Simple-React-Native-App make all
# LLM backend for descriptions: LLM=remote (Groq, default) or LLM=local (LM Studio)
# Extra description flags: DESC_ARGS="--num-files 10 --max-workers 4"
#
# eval / eval-all / cost-eval / reliability spend real Groq API quota --
# run `make probe-quota` first to check the configured keys' headroom.
TAG := $(shell python3 -c "from src.clone_raw.clone_raw import TAG; print(TAG)")
LLM ?= remote
DESC_ARGS ?=

.PHONY: all clone extract graph describe index app probe-quota eval eval-all cost-eval reliability cost-plots

all: clone extract graph describe index

clone:
	python src/clone_raw/clone_raw.py

extract:
	node src/ts_extract/extract.mjs $(TAG)

graph:
	python src/build_graph/build_graph.py data/processed/$(TAG)

describe:
	python src/ts_extract/add_descriptions_stepped.py --tag $(TAG) --llm $(LLM) $(DESC_ARGS)

index:
	python src/vector_index/build_index.py --tag $(TAG)

app:
	shiny run app/app.py --reload

# 1-token request per key/model -- cheap check before any live run below.
probe-quota:
	python -m src.qa_agent.probe_quota

eval:
	python -m src.qa_agent.eval

# All three committed question sets, written to their own results/RESULTS files.
eval-all:
	python -m src.qa_agent.eval --questions data/eval/questions.json
	python -m src.qa_agent.eval --questions data/eval/questions_2.json --suffix _2
	python -m src.qa_agent.eval --questions data/eval/questions_3.json --suffix _3

# Single pass over all 30 eval questions -> data/cost/{cost_log.jsonl,COST_REPORT.md}
cost-eval:
	python -m src.qa_agent.cost_eval

# Repeated-sampling consistency run (3-5 samples/question) over the fixed
# 10-question subset -> data/reliability/ + a section in COST_REPORT.md
reliability:
	python -m src.qa_agent.reliability_eval

# Offline -- renders data/cost/cost_log.jsonl into data/cost/plots/*.png
cost-plots:
	python -m src.qa_agent.cost_plots
