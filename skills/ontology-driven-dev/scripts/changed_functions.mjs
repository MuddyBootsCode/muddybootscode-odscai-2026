// Which named function encloses each changed line of a TypeScript file.
//
// stdin:  {"files":[{"path":"/abs/geo.ts","lines":[[3,3],[7,9]]}], "typescript":"/abs/node_modules/typescript"}
// stdout: {"/abs/geo.ts":["K.method","arrow"]}   (sorted, unique; "<module>" for top-level code)
//
// Uses the TypeScript compiler, so arrow functions assigned to a const, class
// methods, and nested closures all resolve to the name a reader would use.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';

const input = JSON.parse(readFileSync(0, 'utf8'));
const require = createRequire(import.meta.url);
const ts = require(input.typescript || 'typescript');

function nameOf(node) {
  if (ts.isFunctionDeclaration(node) && node.name) return node.name.text;
  if (ts.isMethodDeclaration(node) || ts.isGetAccessor(node) || ts.isSetAccessor(node)) {
    const owner = node.parent && node.parent.name ? node.parent.name.text : null;
    const own = node.name && node.name.getText ? node.name.getText() : null;
    return own ? (owner ? `${owner}.${own}` : own) : null;
  }
  if (ts.isConstructorDeclaration(node)) {
    const owner = node.parent && node.parent.name ? node.parent.name.text : 'class';
    return `${owner}.constructor`;
  }
  if (ts.isArrowFunction(node) || ts.isFunctionExpression(node)) {
    const p = node.parent;
    if (p && ts.isVariableDeclaration(p) && ts.isIdentifier(p.name)) return p.name.text;
    if (p && ts.isPropertyAssignment(p) && p.name && p.name.getText) return p.name.getText();
    if (p && ts.isPropertyDeclaration(p) && p.name && p.name.getText) {
      const owner = p.parent && p.parent.name ? p.parent.name.text : null;
      return owner ? `${owner}.${p.name.getText()}` : p.name.getText();
    }
    if (node.name) return node.name.text;
    return null; // an anonymous callback: attributed to its enclosing named function
  }
  return null;
}

function isFunctionLike(node) {
  return ts.isFunctionDeclaration(node) || ts.isMethodDeclaration(node) || ts.isArrowFunction(node)
    || ts.isFunctionExpression(node) || ts.isConstructorDeclaration(node) || ts.isGetAccessor(node)
    || ts.isSetAccessor(node);
}

function collect(sf) {
  const spans = []; // {name, start, end, depth}
  function walk(node, stack) {
    let next = stack;
    if (isFunctionLike(node)) {
      const name = nameOf(node);
      const start = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1;
      const end = sf.getLineAndCharacterOfPosition(node.getEnd()).line + 1;
      if (name) {
        spans.push({ name, start, end, depth: stack.length });
        next = [...stack, name];
      }
    }
    ts.forEachChild(node, (c) => walk(c, next));
  }
  walk(sf, []);
  return spans;
}

// mode "names": for each listed line, the name of the function-like node that STARTS on that
// line (a const arrow takes its const's name), else the innermost named function around it.
// Coverage tools that call every arrow "(anonymous_N)" get their names back this way.
function startsOn(spans, line) {
  const here = spans.filter((s) => s.start === line);
  return here.length ? here.reduce((a, b) => (b.depth < a.depth ? b : a)) : null;
}

const out = {};
for (const f of input.files) {
  const text = readFileSync(f.path, 'utf8');
  const kind = f.path.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sf = ts.createSourceFile(f.path, text, ts.ScriptTarget.Latest, true, kind);
  const spans = collect(sf);
  if (input.mode === 'names') {
    const byLine = {};
    for (const line of f.lines) {
      let best = startsOn(spans, line);
      if (!best) {
        for (const s of spans) if (s.start <= line && line <= s.end && (!best || s.depth > best.depth)) best = s;
      }
      byLine[line] = best ? best.name : null;
    }
    out[f.path] = byLine;
    continue;
  }
  const names = new Set();
  for (const [a, b] of f.lines) {
    for (let line = a; line <= b; line++) {
      let best = null;
      for (const s of spans) {
        if (s.start <= line && line <= s.end && (!best || s.depth > best.depth)) best = s;
      }
      names.add(best ? best.name : '<module>');
    }
  }
  out[f.path] = [...names].sort();
}
process.stdout.write(JSON.stringify(out));
