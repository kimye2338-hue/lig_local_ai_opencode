# -*- coding: utf-8 -*-
"""레퍼런스 지식베이스 검색·주입 — 도메인 라우팅 → MOC 지도 → relevance 발췌.

개인 기억(USERDATA/memory)과 분리된 '큐레이션된 사실' 층. 공학 도메인·규격·소프트스킬을
`knowledge/domains|standards|skills/*.md`에 두고, 작업이 가리키는 도메인을 감지해
① 도메인 MOC(하위주제 지도) ② 관련 노트의 작업 관련 섹션을 system 컨텍스트로 주입한다.

팩트체크 인지: 각 노트 프론트매터의 verified/confidence/sources 를 읽어, verified 우선
주입하고 draft는 '미검증' 꼬리표를 단다. 파일이 없어도 안전(주입 생략).

검색 설계(약한 모델용):
  1) 도메인 라우팅: 프롬프트 → 관련 도메인(파일명/title/aliases/domain 키워드 매칭)
  2) MOC 주입: knowledge/_moc/<도메인>.md 가 있으면 지도로 먼저(Aider repo-map 패턴)
  3) relevance 발췌: 매칭 노트에서 작업 관련 섹션만 예산 내(api_reference와 동일 방식)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

KB_DIR = Path(__file__).resolve().parent / "knowledge"
# 공학 도메인 / 규격 / 소프트스킬. (기존 skills/=프로세스 스킬, domain/=한국 비즈니스
# 맥락은 별도 주입기가 담당하므로 여기 포함하지 않는다.)
_NOTE_DIRS = ("domains", "standards", "lifeskills")
_MOC_DIR = KB_DIR / "_moc"


def _tokens(s: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+|[가-힣]{2,}", (s or "").lower()) if len(t) >= 2}


def _parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    """--- yaml --- 프론트매터를 얕게 파싱(외부 의존 없이). (meta, body) 반환."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    head = text[3:end]
    body = text[end + 4:].lstrip("\n")
    meta: Dict[str, str] = {}
    for line in head.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip().lower()] = v.strip().strip("[]").strip()
    return meta, body


def _iter_notes():
    """(path, meta, body) for every reference note."""
    for sub in _NOTE_DIRS:
        d = KB_DIR / sub
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            meta, body = _parse_frontmatter(text)
            yield p, meta, body


def _note_keywords(path: Path, meta: Dict[str, str]) -> set:
    """노트를 가리키는 키워드 = 파일명 + title + domain + aliases."""
    kw = _tokens(path.stem)
    kw |= _tokens(meta.get("title", ""))
    kw |= _tokens(meta.get("domain", ""))
    kw |= _tokens(meta.get("aliases", ""))
    return kw


def detect_domains(prompt: str, top: int = 2) -> List[Path]:
    """프롬프트와 키워드가 겹치는 노트를 관련도 순으로 반환(상위 top)."""
    ptok = _tokens(prompt)
    if not ptok:
        return []
    scored: List[Tuple[int, Path]] = []
    for path, meta, _body in _iter_notes():
        overlap = len(ptok & _note_keywords(path, meta))
        if overlap:
            scored.append((overlap, path))
    scored.sort(key=lambda x: -x[0])
    return [p for _n, p in scored[:top]]


def _excerpt(body: str, max_chars: int, prompt: str) -> str:
    """노트 본문에서 작업 관련 섹션만(api_reference와 동일 relevance 방식)."""
    if len(body) <= max_chars:
        return body
    blocks = re.split(r"(?m)^(?=## )", body)
    intro = blocks[0] if blocks else ""
    ptok = _tokens(prompt)
    scored = sorted(((len(ptok & _tokens(b[:400])), b) for b in blocks[1:]), key=lambda x: -x[0])
    out = intro
    for ov, b in scored:
        if ov <= 0 or len(out) + len(b) > max_chars:
            continue
        out += b
    return out[:max_chars]


def _moc_for(domain: str) -> Optional[str]:
    """도메인 MOC(지도) 본문 — 있으면."""
    if not domain:
        return None
    p = _MOC_DIR / f"{domain}.md"
    if p.exists():
        try:
            _m, body = _parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
            return body
        except Exception:
            return None
    return None


def context_for_prompt(prompt: str, max_chars: int = 2600) -> Optional[str]:
    """작업에 맞는 레퍼런스 지식을 system 주입 문자열로. 없으면 None.

    verified 노트 우선, draft는 '미검증' 꼬리표. MOC(지도)를 앞에 붙여 모델이
    '무엇이 있는지' 먼저 알게 한다."""
    notes = detect_domains(prompt, top=2)
    if not notes:
        return None
    seed_kb_vault()  # 첫 사용 시 knowledge/ 를 Obsidian vault 로 자동 준비(무개입)
    chunks: List[str] = []
    budget = max_chars
    seen_moc: set = set()
    for path in notes:
        try:
            meta, body = _parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        domain = meta.get("domain", "") or path.stem
        moc = _moc_for(domain)
        if moc and domain not in seen_moc:
            seen_moc.add(domain)
            m = moc[:min(len(moc), 500)]
            chunks.append(f"[지도: {domain}]\n{m}")
            budget -= len(m)
        verified = str(meta.get("verified", "")).lower() in ("true", "yes", "1")
        tag = "" if verified else " (미검증 draft — 확인 필요)"
        conf = meta.get("confidence", "")
        piece = _excerpt(body, max(500, budget // max(1, len(notes))), prompt)
        header = f"[{domain}{tag}{' · 신뢰도 ' + conf if conf else ''}]"
        chunks.append(f"{header}\n{piece}")
        budget -= len(piece)
        if budget <= 0:
            break
    if not chunks:
        return None
    intro = ("아래는 사내 레퍼런스 지식베이스 발췌다(공학 도메인·규격·실무). 사실·수치·규격은 "
             "여기 근거만 쓰고, 없거나 '미검증'이면 지어내지 말고 확인을 요청하라.\n\n")
    return intro + "\n\n---\n\n".join(chunks)


def seed_kb_vault() -> None:
    """knowledge/ 를 Obsidian vault 로 시드(.obsidian 없을 때만). 사용자가 레퍼런스
    지식 그래프를 Obsidian으로 브라우징할 수 있게 — 개인 기억 vault와 별개."""
    try:
        obs = KB_DIR / ".obsidian"
        if obs.exists():
            return
        import json
        obs.mkdir(parents=True, exist_ok=True)
        (obs / "core-plugins.json").write_text(json.dumps({
            "file-explorer": True, "global-search": True, "switcher": True,
            "graph": True, "backlink": True, "outgoing-link": True,
            "tag-pane": True, "page-preview": True, "outline": True,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        (obs / "community-plugins.json").write_text("[]", encoding="utf-8")
        (obs / "app.json").write_text(json.dumps({
            "useMarkdownLinks": False, "newLinkFormat": "shortest",
            "defaultViewMode": "preview",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        welcome = KB_DIR / "0-지식베이스-안내.md"
        if not welcome.exists():
            welcome.write_text(
                "# OpenCodeLIG 레퍼런스 지식베이스\n\n"
                "AI 조수의 **큐레이션된 사실 지식**(공학 도메인·규격·소프트웨어·소프트스킬).\n"
                "개인 기억(OpenCodeLIG_USERDATA)과 별개다.\n\n"
                "- `_moc/` 도메인 지도(무엇이 있는지) — 그래프 뷰로 연결이 보임\n"
                "- `domains/ standards/ lifeskills/ apis/` 주제 노트([[링크]]로 연결)\n"
                "- 각 노트 프론트매터의 verified/confidence/sources 로 신뢰도 확인\n\n"
                "여기서 직접 고치면 모델이 다음 작업에 그 근거를 씁니다.\n",
                encoding="utf-8")
    except Exception:
        pass


def kb_status() -> Dict[str, int]:
    """도메인/규격/스킬 노트 수 + verified 수(doctor/진단용)."""
    total = 0
    verified = 0
    for _p, meta, _b in _iter_notes():
        total += 1
        if str(meta.get("verified", "")).lower() in ("true", "yes", "1"):
            verified += 1
    mocs = len(list(_MOC_DIR.glob("*.md"))) if _MOC_DIR.is_dir() else 0
    return {"notes": total, "verified": verified, "mocs": mocs}


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) > 1:
        print(context_for_prompt(" ".join(sys.argv[1:])) or "(관련 지식 없음)")
    else:
        print(json.dumps(kb_status(), ensure_ascii=False, indent=2))
