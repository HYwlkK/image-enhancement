"""Validate the requirements baseline and the stage-one task register."""
from pathlib import Path
from collections import Counter
from urllib.parse import unquote
from zipfile import ZipFile
from xml.etree import ElementTree
import json
import re

ROOT = Path(__file__).resolve().parents[1]
RESULTS = []


def check(name, condition):
    RESULTS.append({"check": name, "passed": bool(condition)})
    if not condition:
        raise ValueError(name)


def main():
    requirements = (ROOT / "requirements.md").read_text(encoding="utf-8")
    functional = set(re.findall(r"\| (FR-\d{2}) P", requirements))
    quality = set(re.findall(r"\| (NFR-\d{2})", requirements))
    acceptance = set(re.findall(r"\| (AT-\d{2})", requirements))
    check("10 functional requirements", len(functional) == 10)
    check("6 quality requirements", len(quality) == 6)
    check("14 planned acceptance cases", len(acceptance) == 14)

    registry = json.loads((ROOT / "docs/planning/task-registry.json").read_text(encoding="utf-8"))
    task_ids = {f"T{number:02d}" for number in range(1, 17)}
    check("16 registered task IDs", set(registry) == task_ids)
    owners = Counter(task["owner"] for task in registry.values())
    check("4 tasks for each of 4 roles", len(owners) == 4 and set(owners.values()) == {4})
    numbers = [task["number"] for task in registry.values()]
    check("unique issue numbers", len(set(numbers)) == 16)

    dependency_graph = {}
    for tid, task in registry.items():
        paths = list((ROOT / "docs/planning/issues").glob(tid + "_*.md"))
        check(tid + " has one task document", len(paths) == 1)
        text = paths[0].read_text(encoding="utf-8")
        check(tid + " links its registered issue", task["url"] in text)
        check(tid + " has acceptance criteria", "## 验收标准" in text and "- [ ] " in text)
        check(tid + " has a milestone", task["milestone"] in text)
        effort = re.search(r"预估：(\d+)小时", text)
        check(tid + " has a 2 to 8 hour estimate", effort and 2 <= int(effort.group(1)) <= 8)
        dependencies = re.search(r"依赖：([^\n]+)", text)
        dependency_graph[tid] = set(re.findall(r"T\d{2}", dependencies.group(1))) if dependencies else set()
        check(tid + " has valid dependencies", dependency_graph[tid] <= task_ids and tid not in dependency_graph[tid])

    def visit(tid, active, done):
        if tid in active:
            raise ValueError("Cyclic task dependency: " + tid)
        if tid in done:
            return
        active.add(tid)
        for dependency in dependency_graph[tid]:
            visit(dependency, active, done)
        active.remove(tid)
        done.add(tid)

    done = set()
    for tid in task_ids:
        visit(tid, set(), done)
    check("task dependencies have no cycles", True)

    mapping = (ROOT / "docs/planning/任务映射与证据.md").read_text(encoding="utf-8")
    rows = [line for line in mapping.splitlines() if re.match(r"\| T\d{2} \|", line)]
    check("16 evidence rows", len(rows) == 16)
    check("evidence cells have no placeholder labels", not any(word in mapping for word in ["待建立", "待产生", "待运行", "待本人", "账号待"]))
    for task in registry.values():
        check("evidence links issue " + str(task["number"]), task["url"] in mapping)

    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for link in re.findall(r"\]\(([^)\s]+)\)", text):
            if link.startswith(("https://", "http://", "mailto:", "#")):
                continue
            target = unquote(link.split("#", 1)[0])
            if target:
                check(str(path.relative_to(ROOT)) + " links " + target, (path.parent / target).exists())

    documents = list((ROOT / "第一阶段").glob("*.docx"))
    check("3 phase-one Word documents", len(documents) == 3)
    for path in documents:
        with ZipFile(path) as package:
            check(path.name + " is a valid ZIP package", package.testzip() is None)
            tree = ElementTree.fromstring(package.read("word/document.xml"))
            text = "".join(tree.itertext())
            check(path.name + " has readable document content", len(text) > 100)

    check("MIT license retained", (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"))
    check("document workflow exists", (ROOT / ".github/workflows/docs.yml").exists())


if __name__ == "__main__":
    try:
        main()
    finally:
        (ROOT / "docs-validation.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Passed {len(RESULTS)} document checks.")
