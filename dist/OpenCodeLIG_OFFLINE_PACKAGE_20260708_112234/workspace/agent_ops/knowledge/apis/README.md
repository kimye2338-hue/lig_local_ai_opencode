# 공식 API 참조 코퍼스

이 폴더의 마크다운은 사용자 소프트웨어의 **공식 문서 발췌**다. 목적: 매크로/스크립트를
만들 때 LLM이 API를 지어내지(환각) 않고 실제 객체/메서드/명령 이름으로 코딩하게 한다.

## 동작

- `agent_ops/api_reference.py`가 작업 프롬프트에서 소프트웨어를 감지
  (예: "엑셀 매크로" → excel) → 해당 `*.md` 발췌를 LLM system 컨텍스트로 주입.
- 파일이 없으면 주입을 조용히 생략(안전). 파일을 추가하면 재빌드 없이 자동 반영.

## 파일 규약

`excel_vba.md, outlook_vba.md, autocad.md, matlab.md, solidworks.md, fluent.md`
각 파일 구조(엄수):

```
# <소프트웨어> <버전> — 공식 API 참조
- 공식 출처: <official URL>
- 검증상태: verified-from-official | partial | needs-verification
- 확인일: YYYY-MM-DD
## 핵심 객체/명령
## 최소 동작 예제
## 자주 쓰는 작업
## 주의/버전 유의점
```

## 채우는 방법

- 공식 문서(Microsoft Learn / Autodesk / MathWorks / SolidWorks API Help / ANSYS /
  Hancom) 기반으로만 작성. 미검증 항목은 `검증상태`에 명시하고 API를 지어내지 말 것.
- 인터넷 되는 PC에서 Haiku 리서치로 초안 생성 → 공식 출처 URL 확인 → 이 폴더에 반입.
- 대상 버전: Excel/Outlook 2016, AutoCAD 2019, MATLAB R2024a, SolidWorks, ANSYS Fluent 2024R1.
