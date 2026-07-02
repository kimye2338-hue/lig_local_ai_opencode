# -*- coding: utf-8 -*-
"""Capability benchmark: representative office/engineering tasks must route to
the right capability and produce usable artifacts — without per-task code.

Run: py -3.11 tests\\test_capability_bench.py
Artifact quality bar per scaffold: openable, embeds the request, says how to
run/apply it, and states what is app/company validation pending.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WS_TEMPLATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS_TEMPLATE))
# Isolate diagnostics before any agent_ops import resolves DIAG_DIR.
os.environ["LIG_DIAG_DIR"] = tempfile.mkdtemp(prefix="capbench_diag_")

from agent_ops.capabilities import (CAPABILITIES, ARTIFACT_KIND_INFO, classify_task,
                                    plan_task, capability_summary)
from agent_ops.artifact_generators import GENERATORS, generate_artifacts, classify_mail
from agent_ops.artifact_quality import validate_artifact_set
from agent_ops.adapters import ADAPTERS, adapter_summary

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


# (task, capability that must rank in matches, artifact kind expected in plan)
BENCHMARKS = [
    ("SolidWorks 좌표축 바꿔주는 매크로 만들어줘", "office_cad_automation", "vba_macro"),
    ("Excel 매크로 만들어줘", "macro_generation", "vba_macro"),
    ("이 내용으로 문서 작성해줘", "document_generation", "document"),
    ("이 내용으로 PPT 만들어줘", "presentation_generation", "slide_outline"),
    ("웹페이지에서 메일 확인하고 분류 및 요약해줘", "web_mail_assistant", "mail_report"),
    ("크롬 브라우저 매크로 만들어줘", "browser_automation", "browser_script"),
]


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="capbench_"))

    # --- registry sanity: every declared artifact kind has a generator ---
    declared = {k for spec in CAPABILITIES.values() for k in spec["artifact_kinds"]}
    check("all declared artifact kinds have generators",
          declared <= set(GENERATORS), str(declared - set(GENERATORS)))
    check("every artifact kind has planning metadata (files/purpose)",
          declared <= set(ARTIFACT_KIND_INFO), str(declared - set(ARTIFACT_KIND_INFO)))
    check("capability summary is secret-free inventory",
          all("status" in v and "pending" in v for v in capability_summary().values()))

    # --- routing + artifact generation per benchmark ---
    for task, expect_cap, expect_kind in BENCHMARKS:
        caps = classify_task(task)
        check(f"routes to {expect_cap}: {task[:24]}", expect_cap in caps, str(caps))
        plan = plan_task(task)
        check(f"plan includes {expect_kind}", expect_kind in plan["artifact_kinds"],
              str(plan["artifact_kinds"]))
        out = generate_artifacts(task, [expect_kind], out_dir=tmp / expect_cap)
        check(f"{expect_kind} generated ok", out["ok"] and out["files"], str(out))
        text = "\n".join(Path(f).read_text(encoding="utf-8") for f in out["files"])
        check(f"{expect_kind} embeds the request", task in text)
        check(f"{expect_kind} states validation status",
              "pending" in text or "locally" in text, text[:300])
        check(f"{expect_kind} passes quality validator",
              out["quality"][expect_kind]["ok"],
              str(out["quality"][expect_kind]["violations"]))

    # --- composite tasks decompose into multiple capabilities (no per-task code) ---
    COMPOSITES = [
        ("시험 결과 파일 읽고 표 정리해서 보고서와 PPT 초안 만들어줘",
         {"file_ops", "spreadsheet_generation", "document_generation", "presentation_generation"},
         {"document", "slide_outline"}),
        ("SolidWorks 어셈블리 좌표계 정리 매크로와 사용 설명서를 만들어줘",
         {"office_cad_automation", "macro_generation", "document_generation"},
         {"vba_macro", "document"}),
        ("메일함 내용을 중요도별로 분류하고 오늘 처리할 액션아이템을 문서로 만들어줘",
         {"web_mail_assistant", "document_generation"},
         {"mail_report", "document"}),
        ("엑셀 데이터를 정리하는 매크로와 결과 보고서 템플릿을 만들어줘",
         {"spreadsheet_generation", "macro_generation", "document_generation"},
         {"vba_macro", "document"}),
        ("크롬에서 특정 페이지를 열고 내용 추출하는 자동화 스크립트를 만들어줘",
         {"browser_automation"},
         {"browser_script"}),
    ]
    composite_outs = []
    for i, (task, expect_caps, expect_kinds) in enumerate(COMPOSITES):
        plan = plan_task(task)
        got_caps = {c["id"] for c in plan["capabilities"]}
        check(f"composite {i+1} decomposes: {task[:20]}", expect_caps <= got_caps,
              f"missing {expect_caps - got_caps} in {got_caps}")
        check(f"composite {i+1} plans all artifact kinds",
              expect_kinds <= set(plan["artifact_kinds"]), str(plan["artifact_kinds"]))
        out = generate_artifacts(task, plan["artifact_kinds"], out_dir=tmp / f"comp{i+1}")
        composite_outs.append(out)
        check(f"composite {i+1} generates every kind", out["ok"] and len(out["files"]) >= len(expect_kinds),
              str(out))
        check(f"composite {i+1} artifacts all pass quality validator",
              out["quality_ok"], str(out["quality"]))

    # --- shared context: one run's artifacts belong to one job, visibly ---
    comp1 = composite_outs[0]
    run_id = comp1["context"]["run_id"]
    doc1 = (tmp / "comp1" / "문서.md").read_text(encoding="utf-8")
    sl1 = (tmp / "comp1" / "slide_outline.md").read_text(encoding="utf-8")
    check("report and slide outline share one run id", run_id in doc1 and run_id in sl1)
    check("report and slide outline share the same task summary",
          comp1["context"]["task_summary"] in doc1
          and comp1["context"]["task_summary"] in sl1,
          comp1["context"]["task_summary"])
    spec1 = json.loads((tmp / "comp1" / "slide_spec.json").read_text(encoding="utf-8"))
    check("slide spec carries the shared run context",
          spec1["context"]["run_id"] == run_id
          and spec1["context"]["related_artifacts"], str(spec1.get("context")))
    check("document lists its sibling artifacts", "slide_outline" in doc1)
    comp3 = composite_outs[2]
    md3 = [Path(f).read_text(encoding="utf-8") for f in comp3["files"] if f.endswith(".md")]
    check("mail report, action items, and document share one run id",
          len(md3) >= 3 and all(comp3["context"]["run_id"] in t for t in md3))

    # --- plan output is a work plan, not just routing ---
    plan = plan_task(COMPOSITES[0][0])
    for field in ("task_summary", "artifact_plan", "validation_plan",
                  "app_pending", "company_pending", "next_exact_command", "planner_mode"):
        check(f"plan exposes {field}", field in plan, str(sorted(plan)))
    check("artifact_plan names files, purpose, and source capability",
          bool(plan["artifact_plan"]) and all(
              e["kind"] and e["files"] and e["purpose"] and e["from_capabilities"]
              for e in plan["artifact_plan"]), str(plan["artifact_plan"]))
    check("next_exact_command is a runnable plan command",
          "agentops.py plan --task" in plan["next_exact_command"]
          and "--make-artifacts" in plan["next_exact_command"])
    check("validation_plan orders local -> user -> app/company",
          plan["validation_plan"][0].startswith("local")
          and plan["validation_plan"][1].startswith("user")
          and any(s.startswith("app:") for s in plan["validation_plan"]),
          str(plan["validation_plan"]))
    mail_plan = plan_task("웹메일 확인하고 분류 보고서 만들어줘")
    check("pending split separates company blockers from app blockers",
          bool(mail_plan["company_pending"])
          and all("company" in p for p in mail_plan["company_pending"])
          and all("company" not in p for p in mail_plan["app_pending"]),
          str(mail_plan["company_pending"]) + str(mail_plan["app_pending"]))

    # --- semantic planner hook: pluggable, but never able to break routing ---
    sem = plan_task("이 내용으로 문서 작성해줘",
                    planner=lambda t, m: [{"id": "presentation_generation",
                                           "confidence": "high",
                                           "matched_keywords": ["(semantic)"]}])
    check("semantic planner hook can re-route the plan",
          sem["planner_mode"] == "semantic"
          and sem["capabilities"][0]["id"] == "presentation_generation",
          str(sem["capabilities"]))

    def _planner_down(t, m):
        raise RuntimeError("planner down")
    sem_fail = plan_task("이 내용으로 문서 작성해줘", planner=_planner_down)
    check("broken semantic planner falls back to keyword routing",
          sem_fail["planner_mode"].startswith("deterministic_keyword")
          and any(c["id"] == "document_generation" for c in sem_fail["capabilities"]),
          sem_fail["planner_mode"])
    sem_bad = plan_task("이 내용으로 문서 작성해줘", planner=lambda t, m: [{"id": "no_such"}])
    check("invalid semantic proposal is rejected, keyword plan kept",
          "nothing usable" in sem_bad["planner_mode"]
          and any(c["id"] == "document_generation" for c in sem_bad["capabilities"]),
          sem_bad["planner_mode"])

    # --- routing evidence: plan explains WHY (keywords + confidence) ---
    plan = plan_task("SolidWorks 좌표축 바꿔주는 매크로 만들어줘")
    top = plan["capabilities"][0]
    check("plan carries matched keywords as evidence",
          plan["routing"] == "keyword_match" and top["matched_keywords"], str(top))
    check("multi-keyword match is high confidence", top["confidence"] == "high", str(top))

    # --- unknown task falls back to generic file/document capability ---
    caps = classify_task("아무 관련 없는 요청 xyz")
    check("unknown task gets default routing", "file_ops" in caps and "document_generation" in caps, str(caps))
    fb = plan_task("아무 관련 없는 요청 xyz")
    check("fallback plan is labeled low-confidence default",
          fb["routing"] == "default_fallback" and all(c["confidence"] == "low" for c in fb["capabilities"]),
          str(fb["capabilities"]))
    check("fallback summary admits uncertainty instead of overclaiming",
          "매칭되지 않았습니다" in fb["task_summary"] and "low" in fb["task_summary"],
          fb["task_summary"])
    check("fallback still gives a safe next command and document plan",
          "agentops.py" in fb["next_exact_command"]
          and "document" in fb["artifact_kinds"], str(fb["artifact_kinds"]))

    # --- artifact quality spot checks (not per-task hardcoding: generic kinds) ---
    sw = (tmp / "office_cad_automation" / "macro_solidworks.bas").read_text(encoding="utf-8")
    check("SolidWorks macro says how to run it", "매크로" in sw and "SolidWorks" in sw)
    check("SolidWorks macro warns before applying", "백업" in sw or "사본" in sw)
    check("SolidWorks macro has real host structure (ActiveDoc guard + doc types)",
          "ActiveDoc" in sw and "GetType" in sw and "On Error" in sw)
    xl_out = generate_artifacts("엑셀 시트 정리 매크로", ["vba_macro"], out_dir=tmp / "xl")
    xl = Path(xl_out["files"][0]).read_text(encoding="utf-8")
    check("Excel macro includes Alt+F11 import path", "Alt+F11" in xl)
    check("Excel macro has target constants and error handling",
          "TARGET_SHEET" in xl and "On Error" in xl and "ScreenUpdating" in xl)
    doc = (tmp / "document_generation" / "문서.md").read_text(encoding="utf-8")
    check("document has full structure (개요/목적/결론/액션 아이템)",
          all(s in doc for s in ["개요", "목적", "결론", "액션 아이템"]))
    spec = json.loads((tmp / "presentation_generation" / "slide_spec.json").read_text(encoding="utf-8"))
    check("slide spec has slides and pending flag",
          len(spec["slides"]) >= 3 and spec["pptx_generation"] == "dependency_or_app_pending")
    check("every slide declares its one-line message",
          all(s.get("message") for s in spec["slides"]), str(spec["slides"]))
    check("mail rule classifier separates spam from approvals",
          classify_mail({"from": "noreply@x", "subject": "[광고] 특가", "body": ""}) == "광고/스팸"
          and classify_mail({"from": "구매팀", "subject": "결재 요청", "body": ""}) == "결재/승인")
    mail_md = (tmp / "web_mail_assistant" / "메일_분류_보고서.md").read_text(encoding="utf-8")
    check("mail report is mock-labeled with company pending",
          "mock" in mail_md and "company validation pending" in mail_md)
    actions_md = (tmp / "web_mail_assistant" / "액션아이템.md").read_text(encoding="utf-8")
    check("mail assistant also emits actionable to-do list",
          "결재/승인" in actions_md and "광고/스팸" not in actions_md)
    check("browser scaffold forbids hardcoded credentials",
          "하드코딩하지 마세요" in (tmp / "browser_automation" / "browser_macro.py").read_text(encoding="utf-8"))
    check("unknown artifact kind reported, not raised",
          generate_artifacts("x", ["no_such_kind"], out_dir=tmp / "bad")["ok"] is False)

    # --- quality validator catches bad artifacts (not just blesses good ones) ---
    bad = validate_artifact_set("vba_macro", ["broken macro"], task="t")
    check("validator rejects an empty shell outright",
          not bad["ok"] and len(bad["violations"]) >= 4, str(bad))
    v_xl = validate_artifact_set("vba_macro", [xl.replace("TARGET_SHEET", "X")],
                                 task="엑셀 시트 정리 매크로", filenames=["macro_excel.bas"])
    check("validator catches missing Excel target constants",
          not v_xl["ok"] and any(x["rule"] == "xl_target_constants" for x in v_xl["violations"]),
          str(v_xl["violations"]))
    v_doc = validate_artifact_set("document", [doc.replace("결론", "끝")],
                                  task="이 내용으로 문서 작성해줘", filenames=["문서.md"])
    check("validator catches a missing document section",
          not v_doc["ok"] and any(x["rule"] == "section_conclusion" for x in v_doc["violations"]),
          str(v_doc["violations"]))
    v_todo = validate_artifact_set("document", [doc + "\n- TODO\n"],
                                   task="이 내용으로 문서 작성해줘", filenames=["문서.md"])
    check("validator flags a bare TODO without a hint",
          any(x["rule"] == "no_bare_todo" for x in v_todo["violations"]), str(v_todo["violations"]))
    small = dict(spec)
    small["slides"] = spec["slides"][:3]
    v_spec = validate_artifact_set("slide_outline", [json.dumps(small, ensure_ascii=False)],
                                   task=spec["task"], filenames=["slide_spec.json"])
    check("validator enforces minimum slide count in spec",
          any(x["rule"] == "spec_min_slides" for x in v_spec["violations"]), str(v_spec["violations"]))

    # --- enrichment: LLM fill is quality-gated and never lossy ---
    task_doc = "설비 점검 결과 보고서 작성해줘"

    def good_client(prompt: str) -> str:
        scaffold = prompt.split("\n\n", 1)[1]
        return scaffold.replace("TODO: 현재 상태/데이터 요약",
                                "점검 대상 12기 중 2기에서 진동 이상 감지 (상세 데이터 별첨)")
    en = generate_artifacts(task_doc, ["document"], out_dir=tmp / "enrich_ok",
                            enrich=True, llm_client=good_client)
    check("valid LLM fill is applied to the artifact",
          "문서.md" in en["enrichment"]["applied"], str(en["enrichment"]))
    filled = Path(en["files"][0]).read_text(encoding="utf-8")
    check("enriched file gains content but keeps status/pending",
          "진동 이상 감지" in filled and ("pending" in filled or "locally" in filled))
    en_bad = generate_artifacts(task_doc, ["document"], out_dir=tmp / "enrich_bad",
                                enrich=True, llm_client=lambda p: "그냥 잡담")
    check("invalid LLM output falls back to scaffold",
          not en_bad["enrichment"]["applied"] and en_bad["enrichment"]["fallback"]
          and "개요" in Path(en_bad["files"][0]).read_text(encoding="utf-8"),
          str(en_bad["enrichment"]))

    def _llm_down(prompt: str) -> str:
        raise TimeoutError("llm down")
    en_err = generate_artifacts(task_doc, ["document"], out_dir=tmp / "enrich_err",
                                enrich=True, llm_client=_llm_down)
    check("LLM error falls back safely, scaffold intact",
          en_err["enrichment"]["fallback"]
          and "개요" in Path(en_err["files"][0]).read_text(encoding="utf-8"),
          str(en_err["enrichment"]))
    en_none = generate_artifacts(task_doc, ["document"], out_dir=tmp / "enrich_none",
                                 enrich=True, llm_client=None)
    check("enrich without client is honestly skipped as company pending",
          "skipped" in en_none["enrichment"]["status"]
          and "company validation pending" in en_none["enrichment"]["status"],
          en_none["enrichment"]["status"])
    check("enrichment attempts are recorded in diagnostics",
          (Path(os.environ["LIG_DIAG_DIR"]) / "artifact-enrich-last.json").exists())

    # --- adapter skeleton: execution side is declared but honestly pending ---
    check("adapters cover generated artifact kinds",
          {"vba_macro", "browser_script"} <= {k for a in ADAPTERS.values() for k in a["consumes"]})
    check("no adapter claims availability without app validation",
          all(not a["available"] and "pending" in a["pending"] for a in adapter_summary().values()))

    # --- CLI: plan --make-artifacts end to end in an isolated workspace ---
    ws = tmp / "작업공간"
    ws.mkdir()
    env = dict(os.environ)
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                "AGENTOPS_ROOT": str(ws), "LIG_DIAG_DIR": str(tmp / "diag")})
    r = subprocess.run(["py", "-3.11", str(WS_TEMPLATE / "agent_ops" / "agentops.py"),
                        "plan", "--task", "Excel 매크로 만들어줘", "--make-artifacts"],
                       cwd=str(WS_TEMPLATE), env=env, capture_output=True, timeout=120)
    out_txt = r.stdout.decode("utf-8", errors="replace")
    check("plan CLI exits 0", r.returncode == 0, out_txt + r.stderr.decode("utf-8", errors="replace"))
    check("plan CLI routes and reports pending", "macro_generation" in out_txt and "pending" in out_txt, out_txt)
    check("plan CLI prints the next exact command", "next_exact_command" in out_txt, out_txt[:800])
    check("plan CLI reports artifact folder and quality verdict",
          "산출물 폴더" in out_txt and "품질 검사" in out_txt, out_txt[-800:])
    made = list((ws / "agent_ops" / "results" / "artifacts").rglob("*.bas"))
    check("plan CLI wrote artifact under results/artifacts", len(made) == 1, out_txt)
    r2 = subprocess.run(["py", "-3.11", str(WS_TEMPLATE / "agent_ops" / "agentops.py"), "plan"],
                        cwd=str(WS_TEMPLATE), env=env, capture_output=True, timeout=120)
    check("plan CLI without --task exits 2", r2.returncode == 2)

    print(f"\nALL {PASS} CHECKS PASSED (capability benchmark)")


if __name__ == "__main__":
    main()
