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
  function registerDeclaration(nameNode, kindGuess, node) {
    const name = nameNode;
    if (!name || !/^[A-Za-z_$][\w$]*$/.test(name)) return null;

    let type = null;
    if (isHookName(name)) type = "Hook";
    else if (isComponentName(name) && (isScreenByName(name) || isScreenByPath(relPath))) type = "Screen";
    else if (isComponentName(name) && returnsJsx(node)) type = "Component";
    else return null; // not an entity type we track (plain util function, etc.)

    const id = `${relPath}#${name}`;
    addEntity({ id, type, name, file: relPath, kindGuess });
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

  // --- function declarations: function useFoo() {} / function Screen() {}
  for (const fn of sf.getFunctions()) {
    const name = fn.getName();
    if (!name) continue;
    const entId = registerDeclaration(name, "function", fn);
    if (entId) scanBody(entId, fn, importMap, fileId);
  }

  // --- variable declarations: const useFoo = () => {} / const Screen = () => {}
  for (const vd of sf.getVariableDeclarations()) {
    const name = vd.getName();
    const initializer = vd.getInitializer();
    const isFnLike =
      initializer &&
      (initializer.getKind() === SyntaxKind.ArrowFunction ||
        initializer.getKind() === SyntaxKind.FunctionExpression);
    if (!isFnLike) continue;
    const entId = registerDeclaration(name, "arrow", initializer);
    if (entId) scanBody(entId, initializer, importMap, fileId);
  }

  // --- class declarations: class FooScreen extends React.Component
  for (const cls of sf.getClasses()) {
    const name = cls.getName();
    if (!name) continue;
    const entId = registerDeclaration(name, "class", cls);
    if (entId) scanBody(entId, cls, importMap, fileId);
  }
}

// scan a function/class body for: JSX tag usage (-> renders) and call expressions (-> calls)
function scanBody(entId, node, importMap, fileId) {
  const rendered = new Set();
  const called = new Set();

  node.forEachDescendant((d) => {
    const kind = d.getKind();
    if (kind === SyntaxKind.JsxOpeningElement || kind === SyntaxKind.JsxSelfClosingElement) {
      const tagNameNode = d.getTagNameNode ? d.getTagNameNode() : null;
      const tagName = tagNameNode ? tagNameNode.getText().split(".")[0] : null;
      if (tagName && /^[A-Z]/.test(tagName)) rendered.add(tagName);
    }
    if (kind === SyntaxKind.CallExpression) {
      const expr = d.getExpression();
      const calleeName = expr.getText().split(".")[0];
      if (isHookName(calleeName)) called.add(calleeName);
    }
  });

  for (const name of rendered) resolveAndEmit(entId, name, "renders", importMap, fileId);
  for (const name of called) resolveAndEmit(entId, name, "calls", importMap, fileId);
}

function resolveAndEmit(fromId, localName, edgeType, importMap, fileId) {
  const imp = importMap.get(localName);
  if (imp) {
    if (imp.kind === "external") {
      addEdge(fromId, `external:${imp.id}#${localName}`, edgeType, { external: true });
    } else {
      addEdge(fromId, `${imp.id}#${localName}`, edgeType, { unresolvedFileGuess: true });
    }
  } else {
    // likely defined in the same file
    addEdge(fromId, `${fileId}#${localName}`, edgeType, { sameFile: true });
  }
}

// --- write output ------------------------------------------------------------
const entitiesPath = path.join(OUT_DIR, "entities.jsonl");
const edgesPath = path.join(OUT_DIR, "edges.jsonl");
fs.writeFileSync(entitiesPath, entities.map((e) => JSON.stringify(e)).join("\n") + "\n");
fs.writeFileSync(edgesPath, edges.map((e) => JSON.stringify(e)).join("\n") + "\n");

console.error(`Wrote ${entities.length} entities -> ${entitiesPath}`);
console.error(`Wrote ${edges.length} edges -> ${edgesPath}`);
