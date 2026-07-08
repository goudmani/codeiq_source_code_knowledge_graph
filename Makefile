.PHONY: all clone extract graph

all: clone extract graph

clone:
	python src/clone_raw/clone_raw.py

extract:
	node src/ts_extract/extract.mjs data/raw/ data/processed

graph:
	python src/build_graph/build_graph.py data/processed/