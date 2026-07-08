# CodeIQ - Source Code Explorer
Parse a real codebase into a queryable knowledge graph — then let any developer ask plain-English questions about code structure, component impact, and test coverage.

## Setup

0. Before setting up this project, you must have the following installed manually (these are **not** provided by the conda environment):
- [Conda](https://docs.conda.io/en/latest/miniconda.html) (Miniconda recommended) --> Manages the project environment.
- [Nodejs](https://nodejs.org/en/download) --> for ease of working with ts/tsx files

1. Create and activate python environment

```bash
conda env create -f environment.yml
conda activate codeiq_source_code_knowledge_graph
```

2. Create node environment

```bash
npm install
```

## Cloning the target repo

We have provided make commands to make extraction in 2 different languages easier

```make
make clone
make extract
make graph
```