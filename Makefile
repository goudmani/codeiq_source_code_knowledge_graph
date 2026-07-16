# One-line full pipeline:  make all
# Target repo is picked via env vars, e.g.:
#   REPO_OWNER=raysk4ever REPO_NAME=Simple-React-Native-App make all
# LLM backend for descriptions: LLM=remote (Groq, default) or LLM=local (LM Studio)
# Extra description flags: DESC_ARGS="--num-files 10 --max-workers 4"
TAG := $(shell python3 -c "from src.clone_raw.clone_raw import TAG; print(TAG)")
LLM ?= remote
DESC_ARGS ?=

.PHONY: all clone extract graph describe index app eval

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
	python src/vector_index/build_index.py \
		--entities data/processed/$(TAG)/entities_with_desc.jsonl \
		--edges data/processed/$(TAG)/edges.jsonl \
		--raw-dir data/raw/$(TAG) \
		--chroma-dir data/processed/$(TAG)/chroma

app:
	shiny run app/app.py --reload

eval:
	python -m src.qa_agent.eval
