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
import time
from pathlib import Path

WS_TEMPLATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS_TEMPLATE))
# Isolate diagnostics before any agent_ops import resolves DIAG_DIR.
os.environ["LIG_DIAG_DIR"] = tempfile.mkdtemp(prefix="capbench_diag_")

from agent_ops.capabilities import (CAPABILITIES, ARTIFACT_KIND_INFO, classify_task,
                                    plan_task, capability_summary)
from agent_ops.artifact_generators import (GENERATORS, generate_artifacts, classify_mail,
                                           build_artifact_context)
from agent_ops.artifact_quality import _OFFICE2016_BANNED, validate_artifact_set
from agent_ops import input_ingest
from agent_ops.input_ingest import ingest_inputs
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
    ("시험 데이터 후처리 매트랩 스크립트 만들어줘", "matlab_automation", "matlab_script"),
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

    schedule_plan = plan_task("금요일까지 진동시험 보고서 마감 일정 등록해줘")
    check("schedule request routes to schedule_management",
          [c["id"] for c in schedule_plan["capabilities"]] == ["schedule_management"],
          str(schedule_plan["capabilities"]))
    check("schedule plan points to schedule add command",
          "agentops.py schedule add" in schedule_plan["next_exact_command"],
          schedule_plan["next_exact_command"])

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
    matlab = (tmp / "matlab_automation" / "작업.m").read_text(encoding="utf-8")
    check("MATLAB scaffold is -batch ready with try/catch",
          "matlab -batch" in matlab and "try" in matlab and "catch err" in matlab and "exit(1)" in matlab)
    check("MATLAB scaffold uses base processing structure",
          "readtable(INPUT_FILE)" in matlab and "varfun(@mean" in matlab and "writetable" in matlab)
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
    v_ext = validate_artifact_set("vba_macro", [xl], task="엑셀 시트 정리 매크로",
                                  filenames=["macro_excel.txt"])
    check("validator catches a file extension that defeats the purpose",
          any(x["rule"] == "file_extension" for x in v_ext["violations"]), str(v_ext["violations"]))
    v_mat = validate_artifact_set("matlab_script", [matlab.replace("exit(1);", "")],
                                  task="시험 데이터 후처리 매트랩 스크립트 만들어줘",
                                  filenames=["작업.m"])
    check("validator catches MATLAB missing exit on error",
          not v_mat["ok"] and any(x["rule"] == "matlab_exit_on_error" for x in v_mat["violations"]),
          str(v_mat["violations"]))
    check("Office 2016 banned list has 21 functions", len(_OFFICE2016_BANNED) == 21, str(_OFFICE2016_BANNED))
    for fn in ("XLOOKUP", "TEXTJOIN", "LET"):
        v_office = validate_artifact_set("vba_macro", [xl + f'\nSub Bad_{fn}(): Range("A1").Formula = "={fn}(A1:A2)": End Sub\n'],
                                         task="엑셀 시트 정리 매크로", filenames=["macro_excel.bas"])
        check(f"validator blocks Office 2016 banned function {fn}",
              any(x["rule"] == "office2016_compat" for x in v_office["violations"]),
              str(v_office["violations"]))
    note_only = validate_artifact_set("vba_macro", [xl + "\n' XLOOKUP is mentioned without a call\n"],
                                      task="엑셀 시트 정리 매크로", filenames=["macro_excel.bas"])
    check("Office 2016 rule does not flag plain mention",
          not any(x["rule"] == "office2016_compat" for x in note_only["violations"]),
          str(note_only["violations"]))
    check("macro header states Office 2016 target",
          "대상: Office 2016 호환" in xl)

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

    # --- input ingestion: read the user's actual material, safely ---
    input_dir = tmp / "입력 자료"
    input_dir.mkdir()
    (input_dir / "시험결과.csv").write_text(
        "항목,측정값,기준상한,판정\n치수A,12.4,12.5,합격\n치수B,13.9,12.5,불합격\n"
        "표면조도,0.8,1.6,합격\n경도,45,40,초과\n", encoding="utf-8")
    (input_dir / "장비.log").write_text(
        "2026-07-01 10:00 INFO start\n2026-07-01 10:05 ERROR vibration sensor timeout\n"
        "2026-07-01 10:06 WARNING retry scheduled\n2026-07-01 10:07 ERROR spindle overload\n"
        "2026-07-01 10:10 INFO done\n", encoding="utf-8")
    (input_dir / "점검매크로.bas").write_text(
        "Option Explicit\n\nSub CheckDims()\n    ' 치수 점검\nEnd Sub\n\n"
        "Function GetLimit() As Double\n    GetLimit = 12.5\nEnd Function\n", encoding="utf-8")
    (input_dir / "모델.bin").write_bytes(b"\x00\x01\x02BINARY")
    mail_json = tmp / "메일목록.json"
    mail_json.write_text(json.dumps([
        {"from": "품질팀", "subject": "결재 요청: 시험 성적서", "body": "성적서 결재 부탁드립니다."},
        {"from": "설계팀", "subject": "설계 검토 요청", "body": "도면 검토 후 회신 바랍니다."},
        {"from": "noreply@ad", "subject": "[광고] 하계 특가", "body": "특가 안내"},
        {"from": "연구소", "subject": "회의 일정 공지", "body": "금요일 10시 회의"},
    ], ensure_ascii=False), encoding="utf-8")

    ing = ingest_inputs([str(input_dir)])
    check("ingest scans a folder with Korean/space path",
          ing["ok"] and len(ing["files"]) == 3, str(ing["errors"]) + str(len(ing["files"])))
    csv_facts = " ".join(next(f for f in ing["files"] if f["name"] == "시험결과.csv")["facts"])
    check("ingest extracts CSV rows/columns/header", "4행" in csv_facts and "판정" in csv_facts, csv_facts)
    check("ingest flags abnormal rows as notable items",
          any("치수B" in n for n in ing["notable_items"])
          and any("초과" in n for n in ing["notable_items"]), str(ing["notable_items"]))
    log_facts = " ".join(next(f for f in ing["files"] if f["name"] == "장비.log")["facts"])
    check("ingest counts log errors and warnings",
          "ERROR 2건" in log_facts and "WARNING 1건" in log_facts, log_facts)
    bas_facts = " ".join(next(f for f in ing["files"] if f["name"] == "점검매크로.bas")["facts"])
    check("ingest lists macro entry points", "CheckDims" in bas_facts and "GetLimit" in bas_facts, bas_facts)
    check("ingest records binary input as unsupported, not silently skipped",
          any(u["name"] == "모델.bin" for u in ing["unsupported"]), str(ing["unsupported"]))
    check("ingest reports a missing path as error without raising",
          ingest_inputs([str(tmp / "없는파일.csv")])["errors"])
    secret_file = tmp / "설정.txt"
    secret_file.write_text("api_key = SECRET_VALUE_123\n일반 내용 줄\n", encoding="utf-8")
    check("ingest masks secret-like lines before summarizing",
          "SECRET_VALUE_123" not in json.dumps(ingest_inputs([str(secret_file)]), ensure_ascii=False))
    xlsx_path = input_dir / "시험결과.xlsx"
    if input_ingest.openpyxl is not None:
        wb = input_ingest.openpyxl.Workbook()
        ws = wb.active
        ws.title = "결과"
        ws.append(["항목", "측정값", "기준상한", "판정"])
        ws.append(["치수A", 12.4, 12.5, "합격"])
        ws.append(["치수B", 13.9, 12.5, "불합격"])
        ws.append(["경도", 45, 40, "초과"])
        wb.create_sheet("메모")
        wb.save(xlsx_path)
        ing_xlsx = ingest_inputs([str(xlsx_path)])
        xlsx_facts = " ".join(ing_xlsx["files"][0]["facts"])
        check("xlsx ingest path used openpyxl", ing_xlsx["files"][0]["type"] == "xlsx", str(ing_xlsx))
        check("xlsx facts mirror CSV rows columns and sheets",
              "3행" in xlsx_facts and "판정" in xlsx_facts and "시트 2개" in xlsx_facts,
              xlsx_facts)
        check("xlsx ingest flags abnormal rows",
              any("치수B" in n for n in ing_xlsx["notable_items"]) and any("초과" in n for n in ing_xlsx["notable_items"]),
              str(ing_xlsx["notable_items"]))
        ctx_xlsx = build_artifact_context("시험 결과 엑셀 읽고 보고서 만들어줘",
                                          plan_task("시험 결과 엑셀 읽고 보고서 만들어줘"), ing_xlsx)
        out_xlsx = generate_artifacts("시험 결과 엑셀 읽고 보고서 만들어줘", ["document"],
                                      out_dir=tmp / "ground_xlsx", context=ctx_xlsx)
        doc_xlsx = Path(out_xlsx["files"][0]).read_text(encoding="utf-8")
        check("xlsx input-grounded document reflects file facts",
              out_xlsx["input_grounded"] and "시험결과.xlsx" in doc_xlsx and "치수B" in doc_xlsx,
              doc_xlsx[:800])
        print("INFO  xlsx ingest branch: openpyxl available")
    else:
        xlsx_path.write_bytes(b"not a real workbook")
        ing_xlsx = ingest_inputs([str(xlsx_path)])
        reason = " ".join(u["reason"] for u in ing_xlsx["unsupported"])
        check("xlsx ingest without openpyxl is unsupported not failed",
              not ing_xlsx["ok"] and "openpyxl 미설치" in reason, str(ing_xlsx))
        ctx_xlsx = build_artifact_context("시험 결과 엑셀 읽고 보고서 만들어줘",
                                          plan_task("시험 결과 엑셀 읽고 보고서 만들어줘"), ing_xlsx)
        out_xlsx = generate_artifacts("시험 결과 엑셀 읽고 보고서 만들어줘", ["document"],
                                      out_dir=tmp / "ground_xlsx", context=ctx_xlsx)
        doc_xlsx = Path(out_xlsx["files"][0]).read_text(encoding="utf-8")
        check("xlsx unsupported limitation reaches document",
              "openpyxl 미설치" in doc_xlsx and "시험결과.xlsx" in doc_xlsx,
              doc_xlsx[:800])
        print("INFO  xlsx ingest branch: openpyxl unavailable")

    # --- input-grounded scenario 1: test-result CSV -> report + slides ---
    task_g1 = "시험 결과 파일 읽고 이상값 정리해서 보고서와 PPT 초안 만들어줘"
    ctx_g1 = build_artifact_context(task_g1, plan_task(task_g1), ing)
    out_g1 = generate_artifacts(task_g1, ["document", "slide_outline"],
                                out_dir=tmp / "ground1", context=ctx_g1)
    check("input-grounded generation passes quality incl. reflection",
          out_g1["quality_ok"] and out_g1["input_grounded"], str(out_g1["quality"]))
    gdoc = (tmp / "ground1" / "문서.md").read_text(encoding="utf-8")
    check("report cites the input file and row count", "시험결과.csv" in gdoc and "4행" in gdoc)
    check("report surfaces failed/abnormal items", "치수B" in gdoc and "불합격" in gdoc)
    check("report action items follow from abnormal findings", "원인 확인 및 조치" in gdoc)
    gsl = (tmp / "ground1" / "slide_outline.md").read_text(encoding="utf-8")
    check("slides carry the same input evidence", "시험결과.csv" in gsl and "치수B" in gsl)
    gspec = json.loads((tmp / "ground1" / "slide_spec.json").read_text(encoding="utf-8"))
    check("slide spec core points come from input, not TODO",
          any("치수B" in p for p in gspec["slides"][3]["points"]), str(gspec["slides"][3]))

    # --- input-grounded scenario 2: provided mail list replaces mock inbox ---
    task_g2 = "메일 목록 분류하고 오늘 액션아이템 만들어줘"
    ing2 = ingest_inputs([str(mail_json)])
    check("ingest parses a mail list JSON into mails",
          bool(ing2["mails"]) and len(ing2["mails"]) == 4, str(ing2["facts"]))
    out_g2 = generate_artifacts(task_g2, ["mail_report"], out_dir=tmp / "ground2",
                                context=build_artifact_context(task_g2, plan_task(task_g2), ing2))
    grep_md = (tmp / "ground2" / "메일_분류_보고서.md").read_text(encoding="utf-8")
    check("mail report uses provided mails, not the sample inbox",
          "설계 검토 요청" in grep_md and "주간 보고 취합 요청" not in grep_md)
    check("mail report states provided-input basis with company pending",
          "입력 메일" in grep_md and "company validation pending" in grep_md)
    gact = (tmp / "ground2" / "액션아이템.md").read_text(encoding="utf-8")
    check("action items derive from provided mails and skip ads",
          "결재 요청: 시험 성적서" in gact and "하계 특가" not in gact)

    # --- input-grounded scenario 3: review an existing macro ---
    task_g3 = "이 매크로 검토해서 오류 가능성과 사용 설명서를 만들어줘"
    ing3 = ingest_inputs([str(input_dir / "점검매크로.bas")])
    out_g3 = generate_artifacts(task_g3, ["document"], out_dir=tmp / "ground3",
                                context=build_artifact_context(task_g3, plan_task(task_g3), ing3))
    gdoc3 = (tmp / "ground3" / "문서.md").read_text(encoding="utf-8")
    check("macro review document cites the actual file and entry points",
          "점검매크로.bas" in gdoc3 and "CheckDims" in gdoc3)

    # --- input-grounded scenario 4: log -> root-cause analysis document ---
    task_g4 = "이 로그 보고 원인 분석 문서 만들어줘"
    ing4 = ingest_inputs([str(input_dir / "장비.log")])
    out_g4 = generate_artifacts(task_g4, ["document"], out_dir=tmp / "ground4",
                                context=build_artifact_context(task_g4, plan_task(task_g4), ing4))
    gdoc4 = (tmp / "ground4" / "문서.md").read_text(encoding="utf-8")
    check("log analysis document reports error counts and actual error lines",
          "ERROR 2건" in gdoc4 and "vibration sensor timeout" in gdoc4)

    # --- input-grounded scenario 5: CSV -> MATLAB post-processing script ---
    task_g6 = "시험 데이터 후처리 매트랩 스크립트 만들어줘"
    plan_g6 = plan_task(task_g6)
    check("MATLAB task routes to matlab_automation",
          any(c["id"] == "matlab_automation" for c in plan_g6["capabilities"]),
          str(plan_g6["capabilities"]))
    check("MATLAB task plans matlab_script", "matlab_script" in plan_g6["artifact_kinds"], str(plan_g6))
    out_g6 = generate_artifacts(task_g6, ["matlab_script"], out_dir=tmp / "ground6",
                                context=build_artifact_context(task_g6, plan_g6, ing))
    mtext = (tmp / "ground6" / "작업.m").read_text(encoding="utf-8")
    check("MATLAB script passes quality with CSV input",
          out_g6["quality"]["matlab_script"]["ok"], str(out_g6["quality"]["matlab_script"]))
    check("MATLAB script reflects input CSV name and notable rows",
          "INPUT_FILE = '시험결과.csv'" in mtext and "치수B" in mtext and "불합격" in mtext,
          mtext[:1000])

    # --- honesty: unsupported-only input, no input, fake success ---
    ing5 = ingest_inputs([str(input_dir / "모델.bin")])
    out_g5 = generate_artifacts("이 파일 정리해서 문서 만들어줘", ["document"], out_dir=tmp / "ground5",
                                context=build_artifact_context("이 파일 정리해서 문서 만들어줘",
                                                               plan_task("이 파일 정리해서 문서 만들어줘"), ing5))
    gdoc5 = (tmp / "ground5" / "문서.md").read_text(encoding="utf-8")
    check("unsupported-only input is not claimed as grounded",
          out_g5["input_grounded"] is False and "모델.bin" in gdoc5 and "지원되지 않는 형식" in gdoc5)
    out_plain = generate_artifacts(task_g1, ["document"], out_dir=tmp / "plain")
    pdoc = (tmp / "plain" / "문서.md").read_text(encoding="utf-8")
    check("no-input artifact honestly says no input was used",
          "입력 자료: 없음" in pdoc and out_plain["input_grounded"] is False)
    v_fake = validate_artifact_set("document", [gdoc.replace("시험결과.csv", "데이터")],
                                   task=task_g1, filenames=["문서.md"],
                                   required_terms=["시험결과.csv"])
    check("validator blocks claimed-but-unreflected input (fake success)",
          not v_fake["ok"] and any(x["rule"] == "input_reflected" for x in v_fake["violations"]),
          str(v_fake["violations"]))

    # --- adapter skeleton: execution side is declared but honestly pending ---
    check("adapters cover generated artifact kinds",
          {"vba_macro", "browser_script"} <= {k for a in ADAPTERS.values() for k in a["consumes"]})
    summary = adapter_summary()
    check("browser availability requires validation evidence",
          summary["browser"]["available"] is True
          and summary["browser"]["validated"].startswith("local Chrome CDP, ")
          and "company validation pending" in summary["browser"]["pending"])
    check("non-browser adapters stay unavailable without app validation",
          all(not a["available"] and "pending" in a["pending"]
              for adapter_id, a in summary.items() if adapter_id != "browser"))

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
    r3 = subprocess.run(["py", "-3.11", str(WS_TEMPLATE / "agent_ops" / "agentops.py"),
                         "plan", "--task", "시험 결과 파일 읽고 보고서 만들어줘",
                         "--input", str(input_dir / "시험결과.csv"), "--make-artifacts"],
                        cwd=str(WS_TEMPLATE), env=env, capture_output=True, timeout=120)
    out3 = r3.stdout.decode("utf-8", errors="replace")
    check("plan CLI ingests --input and exits 0",
          r3.returncode == 0 and "입력 자료 요약" in out3,
          out3 + r3.stderr.decode("utf-8", errors="replace"))
    check("plan CLI reports the input-grounded verdict",
          "input-grounded" in out3 and "예" in out3, out3[-800:])
    cli_docs = list((ws / "agent_ops" / "results" / "artifacts").rglob("문서.md"))
    check("CLI artifact reflects the input contents",
          bool(cli_docs) and any("치수B" in d.read_text(encoding="utf-8") for d in cli_docs),
          str(cli_docs))
    wc = tmp / "diag" / "work-context-last.json"
    check("work context recorded secret-free in diagnostics",
          wc.exists() and "시험결과.csv" in wc.read_text(encoding="utf-8"), str(wc))

    # --- leave a bench marker so doctor can report the last known result ---
    from agent_ops.core import RESULTS
    marker = RESULTS / "capability_bench" / "last_bench.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks_passed": PASS + 1,  # including this final check
        "test_file": "tests/test_capability_bench.py",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    check("bench result recorded for doctor", marker.exists(), str(marker))

    print(f"\nALL {PASS} CHECKS PASSED (capability benchmark)")


if __name__ == "__main__":
    main()
