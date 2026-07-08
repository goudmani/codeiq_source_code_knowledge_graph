#!/usr/bin/env node
/**
 * extract.mjs
 *
 * Walks a TS/TSX source tree with ts-morph and emits two JSONL files:
 *   entities.jsonl  -> one JSON object per Hook / Component / Screen / File
 *   edges.jsonl     -> one JSON object per relationship (depends_on / renders / calls)
 *
 * Usage:
 *   node extract.mjs <path-to-src-root> <out-dir>
 *
 * Example (bluesky-social/social-app):
 *   node extract.mjs ../social-app/src ./out
 */
import { Project, SyntaxKind } from "ts-morph";
import path from "node:path";
import fs from "node:fs";

const [, , SRC_ROOT_ARG, OUT_DIR_ARG] = process.argv;
if (!SRC_ROOT_ARG) {
  console.error("Usage: node extract.mjs <src-root> [out-dir]");
  process.exit(1);
}
const SRC_ROOT = path.resolve(SRC_ROOT_ARG);
const OUT_DIR = path.resolve(OUT_DIR_ARG || "./out");
fs.mkdirSync(OUT_DIR, { recursive: true });

// --- naming heuristics -----------------------------------------------------
const isHookName = (name) => /^use[A-Z0-9]/.test(name);
const isComponentName = (name) => /^[A-Z]/.test(name) && !isHookName(name);
const isScreenByName = (name) => /Screen$/.test(name);
const isScreenByPath = (relPath) => /\/screens\//i.test(relPath) || /\/view\/screens\//i.test(relPath);

// Skip test/story/mock files - noise for an architecture graph
const SKIP_PATTERNS = [/\.test\.[tj]sx?$/, /\.stories\.[tj]sx?$/, /__tests__/, /__mocks__/, /__e2e__/];
const shouldSkip = (filePath) => SKIP_PATTERNS.some((r) => r.test(filePath));

function relOf(p) {
  return path.relative(SRC_ROOT, p).split(path.sep).join("/");
}

// --- project setup ----------------------------------------------------------
const project = new Project({
  tsConfigFilePath: fs.existsSync(path.join(SRC_ROOT, "..", "tsconfig.json"))
    ? path.join(SRC_ROOT, "..", "tsconfig.json")
    : undefined,
  skipAddingFilesFromTsConfig: true,
});

const globPattern = path.join(SRC_ROOT, "**/*.{ts,tsx}");
project.addSourceFilesAtPaths(globPattern);
const sourceFiles = project.getSourceFiles().filter((sf) => !shouldSkip(sf.getFilePath()));
console.error(`Loaded ${sourceFiles.length} source files from ${SRC_ROOT}`);

const entities = [];
const edges = [];
const entitySeen = new Set();

function addEntity(e) {
  if (entitySeen.has(e.id)) return;
  entitySeen.add(e.id);
  entities.push(e);
}
function addEdge(from, to, type, extra = {}) {
  edges.push({ from, to, type, ...extra });
}

// --- resolve an import specifier to a repo-relative module id, or mark external
function resolveModule(sourceFile, moduleSpecifierText) {
  if (moduleSpecifierText.startsWith(".")) {
    const dir = path.dirname(sourceFile.getFilePath());
    let resolved = path.resolve(dir, moduleSpecifierText);
    // try common extensions / index files since we don't always have an exact match
    const candidates = [
      resolved,
      `${resolved}.ts`,
      `${resolved}.tsx`,
      `${resolved}.native.ts`,
      `${resolved}.native.tsx`,
      path.join(resolved, "index.ts"),
      path.join(resolved, "index.tsx"),
    ];
    for (const c of candidates) {
      if (fs.existsSync(c) && fs.statSync(c).isFile()) {
        return { kind: "internal", id: relOf(c) };
      }
    }
    return { kind: "internal", id: relOf(resolved) }; // best-effort, file may be .native/.web variant
  }
  if (moduleSpecifierText.startsWith("#/")) {
    // path alias "#/*" -> "./src/*"  (see tsconfig.json)
    const rel = moduleSpecifierText.replace(/^#\//, "");
    return { kind: "internal", id: rel.replace(/\.tsx?$/, "") };
  }
  return { kind: "external", id: moduleSpecifierText }; // node_modules package
}

// --- main pass ---------------------------------------------------------------
for (const sf of sourceFiles) {
  const filePath = sf.getFilePath();
  const relPath = relOf(filePath);
  const fileId = relPath;

  addEntity({
    id: fileId,
    type: "File",
    name: path.basename(filePath),
    path: relPath,
    isScreenDir: isScreenByPath(relPath),
    startLine: 1,
    endLine: sf.getEndLineNumber(),
  });

  // local import map: localName -> { kind, id }
  const importMap = new Map();
  for (const imp of sf.getImportDeclarations()) {
    const modText = imp.getModuleSpecifierValue();
    const resolved = resolveModule(sf, modText);

    if (resolved.kind === "internal") {
      addEdge(fileId, resolved.id, "depends_on");
    }

    const defaultImport = imp.getDefaultImport();
    if (defaultImport) importMap.set(defaultImport.getText(), resolved);
    for (const named of imp.getNamedImports()) {
      const localName = named.getAliasNode()?.getText() ?? named.getNameNode().getText();
      importMap.set(localName, resolved);
    }
    const namespaceImport = imp.getNamespaceImport();
    if (namespaceImport) importMap.set(namespaceImport.getText(), resolved);
  }

  // helper: classify + register a top-level declaration, return its entity id (or null)
  // `scanNode` is what we walk for JSX/call-expressions (function body etc.)
  // `rangeNode` is what we use for the reported start/end line - broader,
  // e.g. the whole `const Foo = (...) => {...}` statement rather than just
  // the arrow function expression, so the snippet includes the declaration itself.
  function registerDeclaration(nameNode, kindGuess, scanNode, rangeNode = scanNode) {
    const name = nameNode;
    if (!name || !/^[A-Za-z_$][\w$]*$/.test(name)) return null;

    let type = null;
    if (isHookName(name)) type = "Hook";
    else if (isComponentName(name) && (isScreenByName(name) || isScreenByPath(relPath))) type = "Screen";
    else if (isComponentName(name) && returnsJsx(scanNode)) type = "Component";
    else return null; // not an entity type we track (plain util function, etc.)

    const id = `${relPath}#${name}`;
    // Note: nested/overlapping ranges are expected and fine - e.g. a child
    // component defined inline inside a parent's render will have a line
    // range fully contained within the parent's range.
    addEntity({
      id,
      type,
      name,
      file: relPath,
      kindGuess,
      startLine: rangeNode.getStartLineNumber(),
      endLine: rangeNode.getEndLineNumber(),
    });
    addEdge(fileId, id, "defines");
    return id;
  }

  function returnsJsx(node) {
    if (!node) return false;
    const jsxKinds = [
      SyntaxKind.JsxElement,
      SyntaxKind.JsxSelfClosingElement,
      SyntaxKind.JsxFragment,
    ];
    let found = false;
    node.forEachDescendant((d) => {
      if (jsxKinds.includes(d.getKind())) found = true;
    });
    return found;
  }

  // --- pass 1: find every declaration in the file, at ANY nesting depth ------
  // Important: sf.getFunctions()/getVariableDeclarations()/getClasses() only
  // return top-level declarations in ts-morph. A component or hook defined
  // *inside* another component's body (a common React pattern for small local
  // helper components) would be silently skipped by those. Using
  // forEachDescendant instead means a nested declaration is still found, and
  // its line range will naturally sit inside its parent's range - overlap
  // between a parent and a child defined in its body is expected here, not
  // deduplicated away.
  const declarations = []; // { entId, scanNode }

  sf.forEachDescendant((node) => {
    const kind = node.getKind();

    if (kind === SyntaxKind.FunctionDeclaration) {
      const name = node.getName();
      if (!name) return;
      const entId = registerDeclaration(name, "function", node);
      if (entId) declarations.push({ entId, scanNode: node });
      return;
    }

    if (kind === SyntaxKind.VariableDeclaration) {
      const name = node.getName();
      const initializer = node.getInitializer();
      const isFnLike =
        initializer &&
        (initializer.getKind() === SyntaxKind.ArrowFunction ||
          initializer.getKind() === SyntaxKind.FunctionExpression);
      if (!isFnLike) return;
      // Use the enclosing variable statement (e.g. `const Foo = () => {...}`)
      // for the reported line range so it includes the declaration keyword
      // and name, not just the function expression body.
      const stmt = node.getVariableStatement();
      const rangeNode = stmt ?? node;
      const entId = registerDeclaration(name, "arrow", initializer, rangeNode);
      if (entId) declarations.push({ entId, scanNode: initializer });
      return;
    }

    if (kind === SyntaxKind.ClassDeclaration) {
      const name = node.getName();
      if (!name) return;
      const entId = registerDeclaration(name, "class", node);
      if (entId) declarations.push({ entId, scanNode: node });
      return;
    }
  });

  // --- pass 2: scan each declaration's body for JSX/hook usage ---------------
  // A boundary set of every OTHER declared node lets us stop descending once
  // we hit a nested declaration - so a parent's `renders`/`calls` edges only
  // reflect what it directly does, and the nested child gets credit for what
  // happens inside its own body. Their line ranges still overlap; the
  // attribution of edges just doesn't double up.
  const boundaryNodes = new Set(declarations.map((d) => d.scanNode));
  for (const { entId, scanNode } of declarations) {
    scanBody(entId, scanNode, importMap, fileId, boundaryNodes);
  }
}

// scan a function/class body for: JSX tag usage (-> renders) and call expressions (-> calls)
// Tracks every line each name is used on (a component can render the same
// child in multiple branches, or call a hook only once - both are common).
// `boundaryNodes` are the scan-roots of every OTHER declared entity in the
// file; once traversal reaches one of those we skip its subtree so a parent
// doesn't also claim edges that belong to a nested child.
function scanBody(entId, node, importMap, fileId, boundaryNodes = new Set()) {
  const rendered = new Map(); // name -> [lines]
  const called = new Map();

  node.forEachDescendant((d, traversal) => {
    if (d !== node && boundaryNodes.has(d)) {
      traversal.skip();
      return;
    }
    const kind = d.getKind();
    if (kind === SyntaxKind.JsxOpeningElement || kind === SyntaxKind.JsxSelfClosingElement) {
      const tagNameNode = d.getTagNameNode ? d.getTagNameNode() : null;
      const tagName = tagNameNode ? tagNameNode.getText().split(".")[0] : null;
      if (tagName && /^[A-Z]/.test(tagName)) {
        const line = d.getStartLineNumber();
        if (!rendered.has(tagName)) rendered.set(tagName, []);
        rendered.get(tagName).push(line);
      }
    }
    if (kind === SyntaxKind.CallExpression) {
      const expr = d.getExpression();
      const calleeName = expr.getText().split(".")[0];
      if (isHookName(calleeName)) {
        const line = d.getStartLineNumber();
        if (!called.has(calleeName)) called.set(calleeName, []);
        called.get(calleeName).push(line);
      }
    }
  });

  for (const [name, lines] of rendered) resolveAndEmit(entId, name, "renders", importMap, fileId, lines);
  for (const [name, lines] of called) resolveAndEmit(entId, name, "calls", importMap, fileId, lines);
}

function resolveAndEmit(fromId, localName, edgeType, importMap, fileId, lines = []) {
  const meta = { lines }; // line number(s) within `fromId`'s own snippet where this occurs
  const imp = importMap.get(localName);
  if (imp) {
    if (imp.kind === "external") {
      addEdge(fromId, `external:${imp.id}#${localName}`, edgeType, { external: true, ...meta });
    } else {
      addEdge(fromId, `${imp.id}#${localName}`, edgeType, { unresolvedFileGuess: true, ...meta });
    }
  } else {
    // likely defined in the same file
    addEdge(fromId, `${fileId}#${localName}`, edgeType, { sameFile: true, ...meta });
  }
}

// --- write output ------------------------------------------------------------
const entitiesPath = path.join(OUT_DIR, "entities.jsonl");
const edgesPath = path.join(OUT_DIR, "edges.jsonl");
fs.writeFileSync(entitiesPath, entities.map((e) => JSON.stringify(e)).join("\n") + "\n");
fs.writeFileSync(edgesPath, edges.map((e) => JSON.stringify(e)).join("\n") + "\n");

console.error(`Wrote ${entities.length} entities -> ${entitiesPath}`);
console.error(`Wrote ${edges.length} edges -> ${edgesPath}`);