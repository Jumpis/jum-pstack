#!/usr/bin/env python3
"""Keep jum-pstack in step with upstream pstack.

  python3 tools/jp.py sync [--upstream DIR] [--commit REV]
      Copy upstream's Claude Code tree (cursor/plugins harness/pstack/claude-code) into
      vendor/pstack, bump VERSION, and update upstream.lock.json. Prints "up to date" and
      changes nothing when that tree is unchanged. Without --upstream it clones cursor/plugins.
  python3 tools/jp.py build [--bump]
      Rebuild plugins/pstack and both marketplace catalogs from vendor/ and overlay/.
  python3 tools/jp.py check [--against REF]
      Everything a merge needs: the build is current, both adapters cover every row of
      upstream's Claude Code adapter, manifests agree with VERSION, hooks parse, and no
      conflict markers remain.

Standard library only, so it runs unchanged in a cloud routine.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "pstack"
OVERLAY = ROOT / "overlay"
OUT = ROOT / "plugins" / "pstack"
HERMES_SKILLS = ROOT / "hermes" / "skills"
LOCK = ROOT / "upstream.lock.json"
VERSION_FILE = ROOT / "VERSION"
CLAUDE_MARKETPLACE = ".claude-plugin/marketplace.json"
CODEX_MARKETPLACE = ".agents/plugins/marketplace.json"

REPO_URL = "https://github.com/Jumpis/jum-pstack"
UPSTREAM_URL = "https://github.com/cursor/plugins"
UPSTREAM_TREE = "harness/pstack/claude-code"
UPSTREAM_WATCH = ("pstack", "harness/pstack")
KST = timezone(timedelta(hours=9))
SKIP = {".DS_Store", "__pycache__", ".git"}

# Upstream's generator adds this sentence to each skill that uses Cursor names.
# The build points it at every runtime's adapter instead of Claude Code's alone.
POINTER = re.compile(
    r"^In Claude Code, read \[the Claude Code adapter\]\((?P<dir>[^)\s]*?)claude-code\.md\) once per session "
    r"before you follow this skill\. It maps the Cursor names in pstack skills to Claude Code\.$",
    re.M,
)
POINTER_NEW = (
    "Read your runtime's adapter once per session before you follow this skill: "
    "[Claude Code]({d}claude-code.md), [Codex]({d}codex.md), or [Hermes]({d}hermes.md). "
    "It maps the Cursor names in pstack skills to that runtime."
)
UPSTREAM_ADAPTER = "docs/harness/claude-code.md"
ADAPTERS = ("docs/harness/codex.md", "docs/harness/hermes.md")
MANIFESTS = ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json")
VERSION_RE = re.compile(r"^\d{4}\.\d{3,4}\.\d+$")


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def git(*args: str, cwd: Path = ROOT, binary: bool = False, ok: bool = False):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if r.returncode != 0:
        if ok:
            return None
        die(f"git {' '.join(args)}: {r.stderr.decode(errors='replace').strip()}")
    return r.stdout if binary else r.stdout.decode()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP)
        for name in sorted(filenames):
            if name not in SKIP:
                yield Path(dirpath) / name


def snapshot(root: Path) -> dict[str, tuple[bytes, bool]]:
    if not root.is_dir():
        return {}
    return {p.relative_to(root).as_posix(): (p.read_bytes(), os.access(p, os.X_OK)) for p in walk(root)}


def read_version() -> str:
    return VERSION_FILE.read_text().strip() if VERSION_FILE.exists() else ""


def next_version(current: str, now: datetime | None = None) -> str:
    """YYYY.MDD.N: the KST date, then a counter for several releases on one day."""
    d = now or datetime.now(KST)
    stamp = f"{d.year}.{d.month * 100 + d.day}"
    if current.startswith(stamp + "."):
        return f"{stamp}.{int(current.rsplit('.', 1)[1]) + 1}"
    return f"{stamp}.0"


def bump_version() -> str:
    new = next_version(read_version())
    VERSION_FILE.write_text(new + "\n")
    return new


# ---------------------------------------------------------------- sync


def read_upstream_tree(repo: Path, commit: str) -> dict[str, tuple[bytes, bool]]:
    listing = git("ls-tree", "-r", "-z", "--full-tree", commit, "--", UPSTREAM_TREE, cwd=repo, binary=True)
    entries = []
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, name = record.split(b"\t", 1)
        mode, kind, sha = meta.decode().split()
        if kind != "blob" or mode not in ("100644", "100755"):
            die(f"{name.decode()} is a {kind} with mode {mode}; only regular files are supported")
        entries.append((mode, sha, name.decode()))
    if not entries:
        die(f"{UPSTREAM_TREE} does not exist at {commit[:12]}")
    batch = subprocess.run(
        ["git", "cat-file", "--batch"], cwd=repo, capture_output=True, check=True,
        input=b"".join(sha.encode() + b"\n" for _, sha, _ in entries),
    ).stdout
    files, pos = {}, 0
    for mode, _, name in entries:
        header_end = batch.index(b"\n", pos)
        size = int(batch[pos:header_end].split()[2])
        body = batch[header_end + 1 : header_end + 1 + size]
        pos = header_end + 1 + size + 1
        files[name[len(UPSTREAM_TREE) + 1 :]] = (body, mode == "100755")
    return files


def write_tree(root: Path, files: dict[str, tuple[bytes, bool]]) -> None:
    if root.exists():
        shutil.rmtree(root)
    for rel, (body, executable) in sorted(files.items()):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        path.chmod(0o755 if executable else 0o644)


def last_change(repo: Path, commit: str) -> dict | None:
    if (git("rev-parse", "--is-shallow-repository", cwd=repo, ok=True) or "").strip() == "true":
        return None
    out = git("log", "-1", "--format=%H %cs", commit, "--", *UPSTREAM_WATCH, cwd=repo).strip()
    if not out:
        return None
    sha, date = out.split()
    return {"commit": sha, "date": date}


def sibling_upstream() -> Path | None:
    """A cursor/plugins checkout next to this repo, as a routine clones its attached repos."""
    candidate = ROOT.parent / "plugins"
    if not (candidate / UPSTREAM_TREE).is_dir():
        return None
    origin = git("remote", "get-url", "origin", cwd=candidate, ok=True) or ""
    return candidate if "cursor/plugins" in origin else None


def cmd_sync(args: argparse.Namespace) -> None:
    temp = None
    if args.upstream:
        repo = Path(args.upstream).resolve()
    elif sibling_upstream():
        repo = sibling_upstream()
    else:
        temp = Path(tempfile.mkdtemp(prefix="jp-upstream-"))
        repo = temp / "plugins"
        git("clone", "--quiet", "--filter=blob:none", "--no-checkout", UPSTREAM_URL, str(repo))
    print(f"upstream checkout: {repo if not temp else 'fresh clone of ' + UPSTREAM_URL}")
    try:
        commit = git("rev-parse", "--verify", f"{args.commit}^{{commit}}", cwd=repo).strip()
        tree = git("rev-parse", f"{commit}:{UPSTREAM_TREE}", cwd=repo).strip()
        lock = read_json(LOCK) if LOCK.exists() else {}
        if lock.get("tree") == tree and VENDOR.is_dir():
            print(f"up to date: {UPSTREAM_TREE} is unchanged at {commit[:7]} "
                  f"(pinned {lock.get('upstream_version')} since {lock.get('synced_at')})")
            return
        files = read_upstream_tree(repo, commit)
        upstream_version = json.loads(files["plugin.json"][0]).get("version", "unknown")
        before = snapshot(VENDOR)
        write_tree(VENDOR, files)
        version = bump_version()
        change = last_change(repo, commit)
        write_json(LOCK, {
            "repo": UPSTREAM_URL,
            "path": UPSTREAM_TREE,
            "commit": commit,
            "tree": tree,
            "upstream_version": upstream_version,
            "last_upstream_change": change,
            "synced_at": datetime.now(KST).date().isoformat(),
        })
        added = sorted(files.keys() - before.keys())
        removed = sorted(before.keys() - files.keys())
        modified = sorted(k for k in files.keys() & before.keys() if files[k] != before[k])
        print(f"synced upstream {lock.get('upstream_version', 'none')} -> {upstream_version} "
              f"({lock.get('commit', '')[:7] or 'none'} -> {commit[:7]}), VERSION {version}")
        print(f"files: {len(added)} added, {len(modified)} modified, {len(removed)} removed")
        for label, paths in (("added", added), ("modified", modified), ("removed", removed)):
            for p in paths[:40]:
                print(f"  {label}: {p}")
        old = lock.get("commit")
        if old and change and git("cat-file", "-e", f"{old}^{{commit}}", cwd=repo, ok=True) is not None:
            log = git("log", "--format=%h %cs %s", f"{old}..{commit}", "--", *UPSTREAM_WATCH, cwd=repo).strip()
            print("upstream commits:\n" + (log or "  (none touching pstack)"))
        print("next: python3 tools/jp.py build && python3 tools/jp.py check")
    finally:
        if temp:
            shutil.rmtree(temp, ignore_errors=True)


# ---------------------------------------------------------------- build


def plugin_manifests(version: str, lock: dict) -> dict[str, dict]:
    description = (
        "pstack by Lauren Tan (poteto), packaged for Claude Code, Codex, and Hermes. "
        f"Upstream {lock['upstream_version']} ({lock['commit'][:7]}), synced weekly."
    )
    author = {"name": "Jumpis", "url": "https://github.com/Jumpis"}
    keywords = ["pstack", "poteto-mode", "workflow", "principles", "subagents", "codex", "hermes"]
    common = {
        "name": "pstack",
        "version": version,
        "description": description,
        "author": author,
        "homepage": REPO_URL,
        "repository": REPO_URL,
        "license": "MIT",
        "keywords": keywords,
    }
    codex = dict(common)
    codex.update({
        "skills": "./skills/",
        "hooks": "./hooks/codex-hooks.json",
        "interface": {
            "displayName": "pstack (jum-pstack)",
            "shortDescription": "Rigorous agent workflows from pstack, kept in step with upstream weekly",
            "developerName": "Jumpis (packaging), Lauren Tan (pstack)",
            "category": "Developer Tools",
            "capabilities": ["Interactive", "Read", "Write"],
            "defaultPrompt": ["Work on this in poteto-mode."],
            "websiteURL": REPO_URL,
        },
    })
    claude = dict(common)
    claude["displayName"] = "pstack (jum-pstack)"
    return {"plugin.json": common, ".claude-plugin/plugin.json": claude, ".codex-plugin/plugin.json": codex}


def marketplaces(version: str, lock: dict) -> dict[str, dict]:
    claude = {
        "name": "jum-pstack",
        "owner": {"name": "Jumpis", "url": "https://github.com/Jumpis"},
        "description": "pstack for Claude Code, Codex, and Hermes, synced weekly from cursor/plugins.",
        "plugins": [{
            "name": "pstack",
            "source": "./plugins/pstack",
            "description": f"pstack {lock['upstream_version']} by Lauren Tan (poteto), jum-pstack build.",
            "version": version,
        }],
    }
    codex = {
        "name": "jum-pstack",
        "interface": {"displayName": "jum-pstack"},
        "plugins": [{
            "name": "pstack",
            "source": {"source": "local", "path": "./plugins/pstack"},
            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL", "products": ["CODEX"]},
            "category": "Developer Tools",
        }],
    }
    return {CLAUDE_MARKETPLACE: claude, CODEX_MARKETPLACE: codex}


def build_into(plugin_dir: Path, catalog_root: Path) -> int:
    if not VENDOR.is_dir() or not LOCK.exists():
        die("vendor/pstack or upstream.lock.json is missing; run: python3 tools/jp.py sync")
    version, lock = read_version(), read_json(LOCK)
    if not VERSION_RE.match(version):
        die(f"VERSION '{version}' is not YYYY.MDD.N; run: python3 tools/jp.py build --bump")
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    shutil.copytree(VENDOR, plugin_dir, ignore=shutil.ignore_patterns(*SKIP))
    for src in walk(OVERLAY):
        rel = src.relative_to(OVERLAY).as_posix()
        target = plugin_dir / rel
        if target.exists() or rel in MANIFESTS:
            die(f"overlay/{rel} collides with an upstream file. Decide which one to keep; never shadow upstream.")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    rewritten = 0
    for path in walk(plugin_dir):
        if path.suffix == ".md":
            text = path.read_text(encoding="utf-8")
            new, count = POINTER.subn(lambda m: POINTER_NEW.format(d=m.group("dir")), text)
            if count:
                path.write_text(new, encoding="utf-8")
                rewritten += count
    if not rewritten:
        die("no skill carries upstream's Claude Code adapter sentence; update POINTER in tools/jp.py")
    for rel, data in plugin_manifests(version, lock).items():
        write_json(plugin_dir / rel, data)
    for rel, data in marketplaces(version, lock).items():
        write_json(catalog_root / rel, data)
    return rewritten


def cmd_build(args: argparse.Namespace) -> None:
    if args.bump:
        print(f"VERSION {bump_version()}")
    count = build_into(OUT, ROOT)
    lock = read_json(LOCK)
    print(f"built plugins/pstack {read_version()} from upstream {lock['upstream_version']} "
          f"({lock['commit'][:7]}); {count} adapter pointers rewritten")


# ---------------------------------------------------------------- check


def adapter_index(path: Path) -> tuple[set[str], set[str]]:
    """Return (first-column keys of every table row, '## ' section titles)."""
    keys, sections = set(), set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            sections.add(line[3:].strip())
        elif line.startswith("|"):
            first = line.split("|")[1].strip()
            if first and not set(first) <= set("-: ") and first not in ("Cursor",):
                keys.add(first)
    return keys, sections


def frontmatter(path: Path) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", path.read_text(encoding="utf-8"), re.S)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        if re.match(r"^[A-Za-z][\w-]*:", line):
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip("'\"")
    return fields


def check_skills(root: Path, label: str) -> list[str]:
    problems = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        skill = folder / "SKILL.md"
        fields = frontmatter(skill) if skill.exists() else {}
        if fields.get("name") != folder.name or not fields.get("description"):
            problems.append(f"{label}/{folder.name}/SKILL.md needs frontmatter name: {folder.name} and a description")
    return problems


def check_version_bump(ref: str | None, version: str) -> list[str]:
    if ref is None:
        if git("rev-parse", "--verify", "-q", "origin/main", ok=True) is None:
            print("note: no origin/main yet, so the VERSION bump check was skipped")
            return []
        ref = "origin/main"
    old = git("show", f"{ref}:VERSION", ok=True)
    if old is None:
        return []
    paths = ["plugins/pstack", ".claude-plugin", ".agents"]
    committed = subprocess.run(["git", "diff", "--quiet", ref, "HEAD", "--", *paths], cwd=ROOT).returncode != 0
    pending = bool((git("status", "--porcelain", "--", *paths) or "").strip())
    if (committed or pending) and old.strip() == version:
        return [f"plugins/pstack changed since {ref} but VERSION is still {version}; run: python3 tools/jp.py build --bump"]
    return []


def cmd_check(args: argparse.Namespace) -> None:
    problems: list[str] = []
    version = read_version()

    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        build_into(temp / "plugins" / "pstack", temp)
        built, committed = snapshot(temp / "plugins" / "pstack"), snapshot(OUT)
        stale = sorted(k for k in built.keys() | committed.keys() if built.get(k) != committed.get(k))
        problems += [f"plugins/pstack/{k} is stale; run: python3 tools/jp.py build" for k in stale[:20]]
        for rel in (CLAUDE_MARKETPLACE, CODEX_MARKETPLACE):
            if not (ROOT / rel).exists() or (ROOT / rel).read_bytes() != (temp / rel).read_bytes():
                problems.append(f"{rel} is stale; run: python3 tools/jp.py build")

    upstream_keys, upstream_sections = adapter_index(VENDOR / UPSTREAM_ADAPTER)
    for rel in ADAPTERS:
        keys, sections = adapter_index(OVERLAY / rel)
        problems += [f"{rel}: missing section '## {s}' that upstream's claude-code.md has" for s in sorted(upstream_sections - sections)]
        problems += [f"{rel}: no row for {k} (upstream's claude-code.md maps it)" for k in sorted(upstream_keys - keys)]

    for path in walk(OUT):
        if path.suffix == ".md" and "In Claude Code, read [the Claude Code adapter]" in path.read_text(encoding="utf-8"):
            problems.append(f"{path.relative_to(ROOT)} still points only at the Claude Code adapter")
    problems += check_skills(OUT / "skills", "plugins/pstack/skills")
    problems += check_skills(HERMES_SKILLS, "hermes/skills")

    if not VERSION_RE.match(version):
        problems.append(f"VERSION '{version}' is not YYYY.MDD.N")
    for rel in MANIFESTS:
        path = OUT / rel
        if not path.exists() or read_json(path).get("version") != version:
            problems.append(f"plugins/pstack/{rel} version does not match VERSION {version}")
    claude_catalog = ROOT / CLAUDE_MARKETPLACE
    if claude_catalog.exists() and read_json(claude_catalog)["plugins"][0].get("version") != version:
        problems.append(f"{CLAUDE_MARKETPLACE} version does not match VERSION {version}")
    problems += check_version_bump(args.against, version)

    hook = OUT / "hooks" / "session-start.sh"
    if not os.access(hook, os.X_OK):
        problems.append("plugins/pstack/hooks/session-start.sh is not executable")
    elif subprocess.run(["sh", "-n", str(hook)]).returncode != 0:
        problems.append("plugins/pstack/hooks/session-start.sh has a shell syntax error")
    for rel in ("hooks/hooks.json", "hooks/codex-hooks.json"):
        text = (OUT / rel).read_text(encoding="utf-8") if (OUT / rel).exists() else ""
        if "session-start.sh" not in text:
            problems.append(f"plugins/pstack/{rel} does not run hooks/session-start.sh")

    ours = {f"plugins/pstack/{m}" for m in MANIFESTS} | {"plugins/pstack/hooks/hooks.json", "plugins/pstack/hooks/codex-hooks.json"}
    for path in walk(ROOT):
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if re.search(r"^(<{7}|>{7}) ", text, re.M):
            problems.append(f"{rel} has conflict markers")
        # Upstream ships JSONC (tsconfig), so only this repo's own JSON must parse strictly.
        if path.suffix == ".json" and (rel in ours or not rel.startswith(("vendor/", "plugins/"))):
            try:
                json.loads(text)
            except json.JSONDecodeError as error:
                problems.append(f"{rel} is not valid JSON: {error}")

    claude = shutil.which("claude")
    if claude:
        for target in (OUT, ROOT):
            result = subprocess.run([claude, "plugin", "validate", str(target)], capture_output=True, text=True)
            if result.returncode != 0:
                problems.append(f"claude plugin validate {target.relative_to(ROOT) or '.'}: "
                                f"{(result.stdout + result.stderr).strip()[:400]}")
    else:
        print("note: claude CLI not found, so `claude plugin validate` was skipped")

    if problems:
        print(f"check failed ({len(problems)}):")
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(1)
    lock = read_json(LOCK)
    print(f"ok: VERSION {version}, upstream {lock['upstream_version']} ({lock['commit'][:7]}), "
          f"{len(upstream_keys)} adapter rows covered in {len(ADAPTERS)} adapters")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync", help="vendor upstream's Claude Code tree")
    sync.add_argument("--upstream", help="path to a cursor/plugins checkout (default: clone it)")
    sync.add_argument("--commit", default="HEAD", help="upstream revision to sync (default: HEAD)")
    build = sub.add_parser("build", help="rebuild plugins/pstack and the catalogs")
    build.add_argument("--bump", action="store_true", help="bump VERSION first")
    check = sub.add_parser("check", help="verify everything a merge needs")
    check.add_argument("--against", help="ref whose VERSION must differ when plugins/pstack changed (default: origin/main)")
    args = parser.parse_args()
    {"sync": cmd_sync, "build": cmd_build, "check": cmd_check}[args.command](args)


if __name__ == "__main__":
    main()
