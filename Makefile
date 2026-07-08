.PHONY: all clone extract

all: clone extract

clone:
	python src/clone_raw/clone_raw.py

extract:
	node src/ts_extract/extract.mjs data/raw/ data/processed