"""Test-case coverage: the multi-hop Project→BRD→FRS→Test-Case chain.

Two layers:
- compute_testcase_coverage(): a PURE function over preloaded rows (no DB).
- build_tc_coverage(): loads active FRS + test cases + traceability + BRD must-BRs
  and serializes the GET /coverage payload (modules, brd_chain, outcomes, summary).

Coverage is recomputed live on every call — manual edits reflect immediately.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# ── Pure model ──────────────────────────────────────────────────────────────────

@dataclass
class TcCoverageEntry:
    frs_element_kind: str   # acceptance_scenario | functional_requirement | business_rule | screen | independent_test
    frs_row_key: str
    spec_row_key: str
    module_row_key: str
    is_negative: bool
    covered_by: list[str]
    is_covered: bool
    has_negative: bool


@dataclass
class TcCoverageReport:
    entries: list[TcCoverageEntry]
    per_spec: dict[str, dict] = field(default_factory=dict)
    per_module: dict[str, dict] = field(default_factory=dict)
    project_pct: float = 0.0
    uncovered: list[TcCoverageEntry] = field(default_factory=list)
    must_br_uncovered: list[str] = field(default_factory=list)
    # Specs with an uncovered BLOCKING-level element (acceptance scenario or
    # functional requirement). Drives the must-BR chain — minor uncovered
    # business rules / screens are excluded so they don't escalate to critical.
    spec_core_uncovered: set[str] = field(default_factory=set)


def compute_testcase_coverage(
    frs_elements: list[dict],
    tc_rows: list[dict],
    traces: list[dict],
    brd_must_brs: set[str],
    frs_spec_to_br: dict[str, set[str]],
) -> TcCoverageReport:
    """Pure coverage computation.

    frs_elements: [{kind, frs_row_key, spec_row_key, module_row_key, is_negative}]
    tc_rows:      active test cases (dicts with row_key, spec_row_key, test_type,
                  scenario_refs, fr_refs, br_refs, source_ref, source_kind)
    traces:       test_case_traceability rows (source_row_key == tc row_key)
    brd_must_brs: set of must-priority BRD BR row_keys
    frs_spec_to_br: {spec_row_key -> {BR row_keys}} from FRS→BR traceability
    """
    tc_by_key = {c["row_key"]: c for c in tc_rows}

    # Build coverage index from BOTH *_refs and traceability rows.
    covered: dict[str, set[str]] = defaultdict(set)
    for c in tc_rows:
        for k in (c.get("scenario_refs") or []):
            covered[k].add(c["row_key"])
        for k in (c.get("fr_refs") or []):
            covered[k].add(c["row_key"])
        for k in (c.get("br_refs") or []):
            covered[k].add(c["row_key"])
        if c.get("source_ref"):
            covered[c["source_ref"]].add(c["row_key"])
    for t in traces:
        # Only count traces whose source case is still ACTIVE (tc_by_key holds
        # active cases) — a deleted case's lingering traces must not count.
        if (t.get("source_table") == "test_cases"
                and t.get("source_row_key") in tc_by_key
                and t.get("target_kind") in (
                    "frs_acceptance_scenario", "frs_functional_requirement",
                    "frs_business_rule", "frs_screen")):
            covered[t["target_ref"]].add(t["source_row_key"])

    # Per-spec e2e/independent coverage: a spec's independent_test element is
    # covered by any e2e or source_kind='independent_test' case on that spec.
    e2e_specs: set[str] = {
        c["spec_row_key"] for c in tc_rows
        if c.get("test_type") == "e2e" or c.get("source_kind") == "independent_test"
    }

    entries: list[TcCoverageEntry] = []
    for el in frs_elements:
        if el["kind"] == "independent_test":
            tcs = sorted(c["row_key"] for c in tc_rows
                         if c["spec_row_key"] == el["spec_row_key"]
                         and (c.get("test_type") == "e2e" or c.get("source_kind") == "independent_test"))
        else:
            tcs = sorted(covered.get(el["frs_row_key"], set()))
        has_neg = any(tc_by_key.get(t, {}).get("test_type") == "negative" for t in tcs)
        entries.append(TcCoverageEntry(
            frs_element_kind=el["kind"], frs_row_key=el["frs_row_key"],
            spec_row_key=el["spec_row_key"], module_row_key=el["module_row_key"],
            is_negative=el.get("is_negative", False),
            covered_by=tcs, is_covered=bool(tcs), has_negative=has_neg,
        ))

    def _rollup(key_fn) -> dict[str, dict]:
        agg: dict[str, dict] = {}
        for e in entries:
            k = key_fn(e)
            a = agg.setdefault(k, {"total": 0, "covered": 0, "negative_ok": True})
            a["total"] += 1
            if e.is_covered:
                a["covered"] += 1
            if e.is_negative and not e.has_negative:
                a["negative_ok"] = False
        for a in agg.values():
            a["pct"] = round(100 * a["covered"] / a["total"], 1) if a["total"] else 100.0
        return agg

    per_spec = _rollup(lambda e: e.spec_row_key)
    per_module = _rollup(lambda e: e.module_row_key)
    project_pct = round(100 * sum(1 for e in entries if e.is_covered) / len(entries), 1) if entries else 100.0

    # A must-have BR is "fully tested" based ONLY on its specs' BLOCKING-level
    # elements — acceptance scenarios + functional requirements. Uncovered
    # business rules / screens are MINOR nudges (surfaced separately as
    # non-blocking findings) and must NOT escalate a must-BR to a critical blocker.
    core_kinds = {"acceptance_scenario", "functional_requirement"}
    spec_core_uncovered: set[str] = {
        e.spec_row_key for e in entries
        if e.frs_element_kind in core_kinds and not e.is_covered
    }

    must_br_uncovered: list[str] = []
    for br in sorted(brd_must_brs):
        specs = [s for s, brs in frs_spec_to_br.items() if br in brs]
        if not specs or any(s in spec_core_uncovered for s in specs):
            must_br_uncovered.append(br)

    return TcCoverageReport(
        entries=entries, per_spec=per_spec, per_module=per_module,
        project_pct=project_pct,
        uncovered=[e for e in entries if not e.is_covered],
        must_br_uncovered=must_br_uncovered,
        spec_core_uncovered=spec_core_uncovered,
    )


# ── Loader + serializer ──────────────────────────────────────────────────────

async def _frs_doc_id(project_id: uuid.UUID, db: AsyncSession, artifact_type: str) -> uuid.UUID | None:
    from app.models.artifact import ArtifactDocument
    doc = (
        await db.execute(select(ArtifactDocument).where(
            ArtifactDocument.project_id == project_id,
            ArtifactDocument.artifact_type == artifact_type,
        ))
    ).scalar_one_or_none()
    return doc.id if doc else None


async def gather_tc_coverage_inputs(project_id: uuid.UUID, db: AsyncSession) -> dict:
    """Load all rows the coverage computation needs."""
    from app.models.brd import BrdBusinessRequirement
    from app.models.frs import (
        FrsAcceptanceScenario, FrsBusinessRule, FrsFunctionalRequirement,
        FrsModule, FrsScreen, FrsSpec, FrsTraceability,
    )
    from app.models.test_cases import TestCase, TestCaseTraceability

    frs_id = await _frs_doc_id(project_id, db, "frs")
    tc_id = await _frs_doc_id(project_id, db, "test_cases")
    brd_id = await _frs_doc_id(project_id, db, "brd")

    async def _active(model, doc_id, cols):
        if doc_id is None:
            return []
        rows = (
            await db.execute(select(model).where(
                model.document_id == doc_id, model.is_current.is_(True), model.status == "active",
            ))
        ).scalars().all()
        return [{"row_key": r.row_key, **{c: getattr(r, c) for c in cols}} for r in rows]

    modules = await _active(FrsModule, frs_id, ["name"])
    specs = await _active(FrsSpec, frs_id, ["module_row_key", "title", "priority", "independent_test"])
    scenarios = await _active(FrsAcceptanceScenario, frs_id, ["spec_row_key", "is_negative"])
    frs_reqs = await _active(FrsFunctionalRequirement, frs_id, ["spec_row_key"])
    rules = await _active(FrsBusinessRule, frs_id, ["spec_row_key"])
    screens = await _active(FrsScreen, frs_id, ["spec_row_key"])
    tc_rows = await _active(TestCase, tc_id, [
        "spec_row_key", "module_row_key", "test_type", "source_kind", "source_ref",
        "scenario_refs", "fr_refs", "br_refs", "title",
    ])

    traces = []
    if tc_id is not None:
        rows = (
            await db.execute(select(TestCaseTraceability).where(TestCaseTraceability.document_id == tc_id))
        ).scalars().all()
        traces = [{"source_table": t.source_table, "source_row_key": t.source_row_key,
                   "target_kind": t.target_kind, "target_ref": t.target_ref} for t in rows]

    # FRS spec → BR map (from FRS traceability)
    frs_spec_to_br: dict[str, set[str]] = defaultdict(set)
    if frs_id is not None:
        rows = (
            await db.execute(select(FrsTraceability).where(
                FrsTraceability.document_id == frs_id,
                FrsTraceability.target_kind == "brd_business_requirement",
            ))
        ).scalars().all()
        for t in rows:
            # source_row_key may be a spec or a child; map child→spec via prefix
            src = t.source_row_key
            spec = next((s["row_key"] for s in specs if src == s["row_key"] or src.startswith(s["row_key"])), src)
            frs_spec_to_br[spec].add(t.target_ref)

    must_brs: set[str] = set()
    br_titles: dict[str, str] = {}
    if brd_id is not None:
        rows = (
            await db.execute(select(BrdBusinessRequirement.row_key, BrdBusinessRequirement.title).where(
                BrdBusinessRequirement.document_id == brd_id,
                BrdBusinessRequirement.is_current.is_(True),
                BrdBusinessRequirement.status == "active",
                BrdBusinessRequirement.priority == "must",
            ))
        ).all()
        must_brs = {r[0] for r in rows}
        br_titles = {r[0]: (r[1] or "") for r in rows}

    return {
        "modules": modules, "specs": specs, "scenarios": scenarios,
        "frs_reqs": frs_reqs, "rules": rules, "screens": screens,
        "tc_rows": tc_rows, "traces": traces,
        "frs_spec_to_br": {k: set(v) for k, v in frs_spec_to_br.items()},
        "must_brs": must_brs, "br_titles": br_titles,
    }


def _frs_elements(inp: dict) -> list[dict]:
    spec_mod = {s["row_key"]: s.get("module_row_key", "") for s in inp["specs"]}
    els: list[dict] = []
    for sc in inp["scenarios"]:
        sk = sc["spec_row_key"]
        els.append({"kind": "acceptance_scenario", "frs_row_key": sc["row_key"],
                    "spec_row_key": sk, "module_row_key": spec_mod.get(sk, ""),
                    "is_negative": bool(sc.get("is_negative"))})
    for fr in inp["frs_reqs"]:
        sk = fr["spec_row_key"]
        els.append({"kind": "functional_requirement", "frs_row_key": fr["row_key"],
                    "spec_row_key": sk, "module_row_key": spec_mod.get(sk, ""), "is_negative": False})
    for br in inp["rules"]:
        sk = br["spec_row_key"]
        els.append({"kind": "business_rule", "frs_row_key": br["row_key"],
                    "spec_row_key": sk, "module_row_key": spec_mod.get(sk, ""), "is_negative": False})
    for scr in inp["screens"]:
        sk = scr["spec_row_key"]
        els.append({"kind": "screen", "frs_row_key": scr["row_key"],
                    "spec_row_key": sk, "module_row_key": spec_mod.get(sk, ""), "is_negative": False})
    for s in inp["specs"]:
        if (s.get("independent_test") or "").strip():
            els.append({"kind": "independent_test", "frs_row_key": f"{s['row_key']}:independent_test",
                        "spec_row_key": s["row_key"], "module_row_key": s.get("module_row_key", ""),
                        "is_negative": False})
    return els


async def build_tc_coverage(project_id: uuid.UUID, db: AsyncSession) -> dict:
    """Compute coverage and serialize the GET /coverage payload."""
    inp = await gather_tc_coverage_inputs(project_id, db)
    elements = _frs_elements(inp)
    report = compute_testcase_coverage(
        elements, inp["tc_rows"], inp["traces"], inp["must_brs"], inp["frs_spec_to_br"],
    )

    spec_meta = {s["row_key"]: s for s in inp["specs"]}
    mod_meta = {m["row_key"]: m for m in inp["modules"]}
    entries_by_spec: dict[str, list[TcCoverageEntry]] = defaultdict(list)
    for e in report.entries:
        entries_by_spec[e.spec_row_key].append(e)
    specs_by_mod: dict[str, list[str]] = defaultdict(list)
    for sk, s in spec_meta.items():
        specs_by_mod[s.get("module_row_key", "")].append(sk)

    cases_by_spec: dict[str, list] = defaultdict(list)
    for c in inp["tc_rows"]:
        cases_by_spec[c["spec_row_key"]].append(c)

    # Outcome rollup per module
    outcomes: dict[str, dict] = {}
    for mk, sks in specs_by_mod.items():
        mod_cases = [c for sk in sks for c in cases_by_spec.get(sk, [])]
        type_dist: dict[str, int] = defaultdict(int)
        for c in mod_cases:
            type_dist[c.get("test_type", "functional")] += 1
        proven = sorted({br for sk in sks for br in inp["frs_spec_to_br"].get(sk, set())})
        uncovered_outcomes = sorted({
            e.frs_row_key for e in report.entries if e.module_row_key == mk and not e.is_covered
        })
        outcomes[mk] = {
            "outcomes_proven": proven,
            "risk_coverage": {"negative": type_dist.get("negative", 0), "edge": type_dist.get("edge_case", 0)},
            "type_distribution": dict(type_dist),
            "uncovered_outcomes": uncovered_outcomes,
        }

    modules_payload = []
    for mk in sorted(specs_by_mod):
        specs_payload = []
        for sk in sorted(specs_by_mod[mk]):
            sp = report.per_spec.get(sk, {"pct": 100.0})
            specs_payload.append({
                "spec_row_key": sk,
                "title": spec_meta.get(sk, {}).get("title", sk),
                "priority": spec_meta.get(sk, {}).get("priority", "P1"),
                "pct": sp.get("pct", 100.0),
                "negative_ok": sp.get("negative_ok", True),
                "elements": [{
                    "kind": e.frs_element_kind, "frs_row_key": e.frs_row_key,
                    "is_negative": e.is_negative, "covered_by": e.covered_by,
                } for e in entries_by_spec.get(sk, [])],
            })
        mp = report.per_module.get(mk, {"pct": 100.0})
        modules_payload.append({
            "module_row_key": mk,
            "title": mod_meta.get(mk, {}).get("name", mk),
            "pct": mp.get("pct", 100.0),
            "plan_count": len(specs_by_mod[mk]),
            "case_count": sum(len(cases_by_spec.get(sk, [])) for sk in specs_by_mod[mk]),
            "specs": specs_payload,
            "outcomes": outcomes.get(mk, {}),
        })

    brd_chain = []
    for br in sorted(inp["must_brs"]):
        specs = sorted(s for s, brs in inp["frs_spec_to_br"].items() if br in brs)
        tested = br not in report.must_br_uncovered
        reason = ""
        if not tested:
            if not specs:
                reason = "No FRS spec implements this BR"
            else:
                weak = [s for s in specs if s in report.spec_core_uncovered]
                reason = f"{', '.join(weak)} has an untested scenario or requirement"
        brd_chain.append({"br_row_key": br, "title": inp["br_titles"].get(br, ""),
                          "priority": "must",
                          "implementing_specs": specs, "tested": tested, "reason": reason})

    total = len(report.entries)
    covered = sum(1 for e in report.entries if e.is_covered)
    return {
        "project_pct": report.project_pct,
        "modules": modules_payload,
        "brd_chain": brd_chain,
        "outcomes": outcomes,
        "summary": {
            "total_elements": total, "covered": covered,
            "must_br_total": len(inp["must_brs"]),
            "must_br_tested": len(inp["must_brs"]) - len(report.must_br_uncovered),
            "must_br_untested": len(report.must_br_uncovered),
        },
    }
