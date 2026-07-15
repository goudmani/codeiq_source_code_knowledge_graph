TAG := $(shell python3 -c "from src.clone_raw.clone_raw import TAG; print(TAG)")

.PHONY: all clone extract graph eval

all: clone extract graph

clone:
	python src/clone_raw/clone_raw.py

extract:
	node src/ts_extract/extract.mjs $(TAG)

graph:
	python src/build_graph/build_graph.py data/processed/$(TAG)

eval:
	python -m src.qa_agent.eval