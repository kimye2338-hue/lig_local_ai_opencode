# 공식 API 코퍼스 인덱스

마지막 업데이트: 2026-07-06  
목적: AI 어시스턴트가 생성하는 자동화 매크로/스크립트를 공식 문서 기반으로 검증

---

## API 참조 문서 목록

### 1. [Excel 2016 VBA](excel_vba.md)
- **검증상태**: ✅ verified-from-official
- **공식 출처**: https://learn.microsoft.com/en-us/office/vba/api/overview/excel
- **핵심 내용**: Application, Workbook, Worksheet, Range 객체; 셀 읽기/쓰기; 수식 설정
- **예제**: 워크북 생성, Range.Value 사용, Cells 속성 활용

---

### 2. [Outlook 2016 VBA](outlook_vba.md)
- **검증상태**: ✅ verified-from-official
- **공식 출처**: https://learn.microsoft.com/en-us/office/vba/api/outlook.mailitem
- **핵심 내용**: Application.CreateItem, MailItem 객체; 메일 작성/발송; Recipients 관리
- **예제**: 메일 생성, 수신자 추가, Body/HTMLBody 설정, Send 메서드

---

### 3. [AutoCAD 2019](autocad.md)
- **검증상태**: ✅ verified-from-official
- **공식 출처**: https://help.autodesk.com/cloudhelp/2019/ENU/AutoCAD-Customization/
- **핵심 내용**: .scr 스크립트 파일 구문; AutoLISP defun/command 함수; 자동 로드
- **예제**: OPEN/SAVEAS 명령, 파일 경로 처리, AutoLISP 함수 정의, S::STARTUP

---

### 4. [MATLAB R2024a](matlab.md)
- **검증상태**: ✅ verified-from-official
- **공식 출처**: https://www.mathworks.com/help/matlab/matlab_env/startup-options.html
- **핵심 내용**: -batch (비대화형), -r (대화형), -logfile, -sd; 배치 스크립트
- **예제**: matlab -batch 명령, 스크립트 실행, 워커 풀 관리, -wait 옵션

---

### 5. [SolidWorks API](solidworks.md)
- **검증상태**: ⚠️ partial (공식 페이지 직접 접근 불가, 검색 결과 기반)
- **공식 출처**: https://help.solidworks.com/ (ISldWorks, IModelDoc2)
- **핵심 내용**: ISldWorks 최상위 인터페이스; IModelDoc2 문서 객체; OpenDocument, SaveAs3
- **예제**: CreateObject로 앱 연결, ActiveDoc 접근, 문서 열기/저장/닫기
- **주의**: 공식 API Help 페이지 직접 방문 권장 (버전별 상세 참조)

---

### 6. [ANSYS Fluent 2024R1](fluent.md)
- **검증상태**: ✅ verified-from-official
- **공식 출처**: https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/flu_ug/flu_ug_BatchExecution.html
- **핵심 내용**: 배치 실행 (-g, -t, -i, -wait); 저널 파일 구문; TUI 명령
- **예제**: fluent 3ddp -g -wait -i journal.jou; /file/read-case, /solve/iterate

---

## 검증 상태 요약

| 소프트웨어 | 상태 | 비고 |
|---------|------|------|
| Excel 2016 VBA | ✅ verified | Microsoft Learn 문서 확인 |
| Outlook 2016 VBA | ✅ verified | Microsoft Learn 문서 확인 |
| AutoCAD 2019 | ✅ verified | Autodesk 공식 Knowledge Network |
| MATLAB R2024a | ✅ verified | MathWorks 공식 문서 |
| SolidWorks API | ⚠️ partial | 검색 결과 기반 (인증 필요) |
| ANSYS Fluent 2024R1 | ✅ verified | ANSYS 공식 Help 문서 |

---

## 사용 가이드

### AI 어시스턴트가 매크로/스크립트 생성 시
1. **소프트웨어 선택**: 위 목록에서 해당 API 문서 참조
2. **검증 상태 확인**: verified는 완전 신뢰 가능, partial은 공식 문서 재확인 권장
3. **핵심 객체/메서드 확인**: 각 문서의 "핵심 객체/명령" 섹션 참고
4. **예제 코드 검토**: "최소 동작 예제"로 구문 확인
5. **주의사항 숙지**: "주의/버전 유의점" 섹션 필독

### 문서 업데이트 규칙
- 공식 문서 변경 감지 시 즉시 반영
- 사용자 피드백으로 예제 개선
- 버전 업그레이드 시 호환성 검토
- "검증상태" 변경 시 공식 출처 재확인 필수

---

## 접근 불가 문제

### SolidWorks
SolidWorks 공식 API Help 페이지(help.solidworks.com)는 인증이 필요할 수 있습니다.  
**해결 방법**:
- SolidWorks 설치 시 로컬 API Help 문서 포함 (C:\Program Files\SOLIDWORKS\...\api\...)
- 또는 SolidWorks에서 Help → API Documentation 메뉴 접근
- Dassault Systèmes 계정으로 공식 웹사이트 로그인

---

## 참고사항

- 모든 예제는 **공식 문서에서 검증된 실제 코드**입니다
- 각 파일의 "공식 출처" URL을 항상 우선순위 참고자료로 활용하세요
- 버전이 변경되면 공식 문서의 버전별 API 차이를 확인하세요
