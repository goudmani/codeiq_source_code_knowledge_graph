# CodeIQ — Source Code Knowledge Graph Assistant

Parse a real React / React Native codebase into a queryable knowledge graph, then a
semantic vector index on top of it — so a developer (or an LLM agent) can ask
plain-English questions about code structure, component relationships, and
impact, and get back answers grounded in real file paths and code snippets.

Built for HCLTech × UBC AI/ML Hackathon, Use Case #03 (Developer Tooling /
Code Intelligence). Target codebase: [bluesky-social/social-app](https://github.com/bluesky-social/social-app)
(~100K lines, React Native + web).

## Pipeline

```
GitHub repo (bluesky-social/social-app)
        │  make clone
        ▼
data/raw/**/*.{ts,tsx}                      raw TypeScript source
        │  make extract  (ts-morph, src/ts_extract/extract.mjs)
        ▼
data/processed/entities.jsonl               nodes: File / Component / Hook / Screen
data/processed/edges.jsonl                  edges: depends_on / renders / calls / defines
        │  make graph  (networkx, src/build_graph/build_graph.py)
        ▼
data/processed/graph.graphml                exported graph for Gephi / yEd viewing
        │
        │  python src/vector_index/build_index.py
        ▼
data/processed/chroma/                      ChromaDB vector index (one doc per entity:
                                             graph context + real source snippet)
        │
        │  python -m src.qa_agent.agent "<question>"  (src/qa_agent/)
        ▼
Answer + High/Medium/Low confidence + cited file/snippet sources
        │
        ▼
   (next) chat/console UI on top of the agent
```

Each stage reads the previous stage's output and is independently re-runnable.
`entities.jsonl` / `edges.jsonl` are the source of truth — `graph.graphml` and
the Chroma index are both *derived* from them, not from each other.

## Setup

0. Before setting up this project, you must have the following installed manually (these are **not** provided by the conda environment):
   - [Conda](https://docs.conda.io/en/latest/miniconda.html) (Miniconda recommended) — manages the Python environment.
   - [Node.js](https://nodejs.org/en/download) — for the ts-morph-based extractor.

1. Create and activate the Python environment

   ```bash
   conda env create -f environment.yml
   conda activate codeiq_source_code_knowledge_graph
   ```

2. Install Node dependencies

   ```bash
   npm install
   ```

## Running the pipeline

All steps can be run individually or together via `make all`.

```bash
make clone      # download bluesky-social/social-app source into data/raw/
make extract    # parse TS/TSX with ts-morph -> data/processed/{entities,edges}.jsonl
make graph      # load into networkx, print example queries, export graph.graphml
```

Then build the vector index (not yet wired into the Makefile):

```bash
python src/vector_index/build_index.py
```

### `make clone` — `src/clone_raw/clone_raw.py`

Downloads the target repo as a zip (`src/clone_raw/repo_link.py` configures
owner/repo/branch — currently `bluesky-social/social-app@main`) and extracts
only `.ts`/`.tsx` files into `data/raw/`. This directory is gitignored and
regenerated on demand — nobody needs to commit ~100K lines of someone else's
source.

### `make extract` — `src/ts_extract/extract.mjs`

Walks `data/raw/` with [ts-morph](https://ts-morph.com/) and emits two JSONL files.

**`entities.jsonl`** — one JSON object per node. Four entity types, classified
by naming/return-type heuristics (`useX` → Hook, `PascalCase` returning JSX →
Component, Component in a `screens/` dir or named `*Screen` → Screen,
everything else → File):

```json
{"id": "src/state/session/index.tsx#useRequireAuth", "type": "Hook", "name": "useRequireAuth", "file": "src/state/session/index.tsx", "kindGuess": "function", "startLine": 438, "endLine": 454}
```

| field | meaning |
|---|---|
| `id` | `<file>#<name>` for declarations, or bare file path for Files |
| `type` | `File` \| `Component` \| `Hook` \| `Screen` |
| `name` | identifier name |
| `file` | repo-relative source path |
| `kindGuess` | `function` \| `arrow` \| `class` |
| `startLine` / `endLine` | source line range, used to pull real code snippets later |

**`edges.jsonl`** — one JSON object per relationship:

```json
{"from": "src/App.tsx#InnerApp", "to": "src/state/session/index.tsx#useSession", "type": "calls"}
```

| edge type | meaning |
|---|---|
| `depends_on` | file A imports file B |
| `defines` | file A declares entity B |
| `renders` | component A renders JSX tag B |
| `calls` | function/component A calls hook/function B |

Edges may also carry `external: true` (target is an npm package, not local
code), `unresolvedFileGuess: true` (target file inferred, not import-resolved),
or `sameFile: true` (target defined in the same file as the source).

Current corpus (bluesky-social/social-app): **3,820 entities** (1,651 Files,
1,052 Components, 572 Hooks, 543 Screens) and **~25,000 edges**.

### `make graph` — `src/build_graph/build_graph.py`

Loads the JSONL pair into a `networkx.MultiDiGraph` and runs a few example
queries you'll actually want when exploring the graph interactively:

- `who_uses(g, "useSession")` — who renders/calls a given entity
- `transitive_deps(g, entity_id)` — BFS over `depends_on` to see what a
  screen/component pulls in, transitively
- `top_fan_in(g, "Hook", "calls")` — most-called hooks (candidate "core" pieces)

It then exports the graph to `data/processed/graph.graphml` for viewing in
[Gephi](https://gephi.org/) or [yEd](https://www.yworks.com/products/yed) —
useful for eyeballing structure, but GraphML stringifies every attribute
(`startLine` becomes `"109"` not `109`), so the vector-index build below reads
directly from the JSONL instead of round-tripping through GraphML.

### Vector index — `src/vector_index/`

`build_index.py` turns every entity into one document in a persistent
[ChromaDB](https://www.trychroma.com/) collection at `data/processed/chroma/`
(collection name `codeiq_entities`), embedded with Chroma's default local
model (`all-MiniLM-L6-v2`, ONNX, CPU, no API key, ~90MB one-time download).

Each document combines three things, so a single retrieval hit is enough to
answer *and* cite evidence:

1. **Header** — entity type, name, kind, file (e.g. `Hook useRequireAuth (function) in src/state/session/index.tsx`)
2. **Graph context** — a natural-language sentence built from the entity's
   edges in both directions (`Renders: ...`, `Calls: ...`, `Rendered by: ...`,
   `Called by: ...`, `Depends on: ...`, `Defines: ...`), capped at 8 names per
   relation with a "+N more" suffix
3. **Source snippet** — the entity's actual code, read from `data/raw/<file>`
   lines `startLine:endLine` (capped at 60 lines)

Rebuild the index any time the JSONL/raw source changes:

```bash
python src/vector_index/build_index.py
```

Runs in well under a minute for the current corpus size (~3,800 docs) — the
embedding model is tiny and runs on CPU, so no GPU or special hardware is
needed.

**Querying it** — `query_index.py` exposes `search_code()` as a plain,
importable function (JSON-serializable return, no side effects beyond reading
the index), so it can be wrapped directly as a tool for an LLM agent (e.g.
LangChain's `@tool`) without any adapter code:

```python
from src.vector_index.query_index import search_code

hits = search_code("who handles session restore", n_results=5, entity_type="Hook")
# -> [{"id", "type", "name", "file", "start_line", "end_line",
#      "snippet", "graph_context", "relevance"}, ...]
```

It also runs as a CLI for manual sanity checks:

```bash
python src/vector_index/query_index.py "authentication session hook"
python src/vector_index/query_index.py "session" --n 10 --type Hook
```

## Project structure

```
codeiq_source_code_knowledge_graph/
├── README.md                    this file
├── LICENSE
├── Makefile                     make clone / extract / graph / all
├── environment.yml               conda env spec (Python 3.11 + pip deps)
├── package.json                  node deps for the extractor (ts-morph)
│
├── src/
│   ├── clone_raw/                 stage 1: fetch target repo source
│   │   ├── repo_link.py             REPO_OWNER / REPO_NAME / BRANCH config
│   │   │                            (currently bluesky-social/social-app@main)
│   │   └── clone_raw.py             downloads repo zip, extracts *.ts/*.tsx
│   │                                only into data/raw/, no git history needed
│   │
│   ├── ts_extract/                stage 2: parse source -> structured graph data
│   │   └── extract.mjs              ts-morph walk over data/raw/**/*.{ts,tsx}
│   │                                classifies each declaration as
│   │                                File / Component / Hook / Screen,
│   │                                records its line range, and emits
│   │                                depends_on / renders / calls / defines
│   │                                edges -> entities.jsonl + edges.jsonl
│   │
│   ├── build_graph/                stage 3: load graph, run example queries
│   │   └── build_graph.py           entities.jsonl/edges.jsonl -> networkx
│   │                                MultiDiGraph; who_uses() / transitive_deps()
│   │                                / top_fan_in() helpers; exports graph.graphml
│   │                                for Gephi/yEd
│   │
│   └── vector_index/                stage 4: semantic search over the graph
│       ├── build_index.py           reads entities.jsonl/edges.jsonl + source
│       │                            from data/raw/, builds one document per
│       │                            entity (header + graph-context sentence +
│       │                            real code snippet), embeds with Chroma's
│       │                            local MiniLM model, persists the collection
│       └── query_index.py           search_code(query, n_results, entity_type)
│                                    - importable function returning structured
│                                    hits (id/type/name/file/lines/snippet/
│                                    graph_context/relevance), designed to be
│                                    wrapped as an LLM agent tool (LangChain
│                                    @tool or similar); also runnable as a CLI
│                                    for manual sanity checks
│
│   └── qa_agent/                    stage 5: LLM-powered Q&A agent
│       ├── tools.py                   find_entity_by_id_or_name() (exact
│       │                              id/name lookup) + get_related_entities()
│       │                              (uncapped graph traversal for one
│       │                              entity) — reuse build_index.py's
│       │                              load_entities()/load_adjacency()
│       ├── agent.py                   ask(question, model) — binds
│       │                              search_code + the two tools above to a
│       │                              Groq chat model, runs a bounded
│       │                              tool-calling loop, computes a
│       │                              High/Medium/Low confidence level
│       │                              deterministically from retrieval
│       │                              relevance (not LLM self-reported); also
│       │                              a CLI for one-off questions
│       └── eval.py                    runs data/eval/questions.json against
│                                      every model in agent.MODELS, writes
│                                      data/eval/results.json + RESULTS.md
│
└── data/
    ├── raw/                        gitignored — cloned *.ts/*.tsx source,
    │                                regenerate any time with `make clone`
    ├── processed/                  pipeline outputs, checked into git
    │   ├── entities.jsonl            graph nodes (source of truth)
    │   ├── edges.jsonl                graph edges (source of truth)
    │   ├── graph.graphml              GraphML export of the above, for
    │   │                              opening in Gephi/yEd — derived, not
    │   │                              a separate source of data
    │   └── chroma/                    ChromaDB persistent store (SQLite +
    │                                  HNSW index segment) for the
    │                                  codeiq_entities collection — derived
    │                                  from entities.jsonl/edges.jsonl +
    │                                  data/raw/, safe to delete/rebuild,
    │                                  should be gitignored
    └── eval/                       checked into git
        ├── questions.json            10 self-generated question/expected-
        │                              answer/expected-entity pairs, written
        │                              before tuning the agent
        ├── results.json              raw structured output of the last
        │                              `make eval` run (all models x all
        │                              questions)
        └── RESULTS.md                human-readable comparison report
```

## Q&A agent

`src/qa_agent/` answers natural-language questions about the codebase, grounded
in retrieved evidence, using a Groq-hosted LangChain agent with three tools:

1. **`search_code`** (`src/vector_index/query_index.py`) — semantic search over
   the vector index; the entry point for discovery questions.
2. **`find_entity_by_id_or_name`** (`src/qa_agent/tools.py`) — exact/near-exact
   identifier lookup, preferred over semantic similarity when a question names
   a specific entity directly (embedding search can't reliably disambiguate
   identically-named entities in different files, e.g. two `useSessionId`
   hooks).
3. **`get_related_entities`** (`src/qa_agent/tools.py`) — uncapped graph
   traversal for one entity, for when a question needs more of its
   relationships than `search_code`'s capped preview (8 names per relation
   type) exposes.

Every answer gets a **High/Medium/Low confidence level**, computed
deterministically from `search_code`'s retrieval relevance scores (not
self-reported by the LLM), plus a one-line rationale.

### Setup

```bash
cp .env.example .env   # then fill in GROQ_API_KEY
```

### Usage

```bash
python -m src.qa_agent.agent "which hook manages session state?" --model llama-3.3-70b-versatile
python -m src.qa_agent.agent "what breaks if useSession changes?" --model openai/gpt-oss-120b
```

### Evaluation

`data/eval/questions.json` holds 10 self-generated question/expected-answer
pairs, grounded in real entities from the parsed graph, written *before*
tuning the agent so answer quality can be measured as the agent changes — not
just checked once at the end.

```bash
make eval   # or: python -m src.qa_agent.eval
```

Runs all 10 questions against every model in `agent.MODELS`
(`llama-3.3-70b-versatile` and `openai/gpt-oss-120b`, compared head-to-head)
and writes `data/eval/results.json` (raw) and `data/eval/RESULTS.md`
(human-readable side-by-side report: per-question answers/confidence/latency,
plus a per-model summary table).

## Roadmap

- [x] Parse codebase into entities/edges (File, Component, Hook, Screen)
- [x] Build knowledge graph (NetworkX) + GraphML export
- [x] Vector search index (ChromaDB, local embeddings)
- [x] LangChain retriever + LLM Q&A agent over the vector index, with graph
      expansion for multi-hop/impact questions ("what breaks if X changes?")
- [x] Confidence scoring (High/Medium/Low) per answer
- [x] Answer-quality evaluation against a hand-written question set (10
      questions x 2 Groq models)
- [ ] Chat UI or console interface with source citations (planned as
      `feat/qa-ui`, to branch off this agent once it's validated)
