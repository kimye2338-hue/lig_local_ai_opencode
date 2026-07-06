# SolidWorks 2022 VBA — 공식 API 참조

- 공식 출처(SOLIDWORKS 2022 API Help, help.solidworks.com/2022):
  - 시작점: https://help.solidworks.com/2022/English/api/sldworksapiprogguide/Welcome.htm
  - 매크로 기본: https://help.solidworks.com/2022/english/api/sldworksapiprogguide/GettingStarted/SOLIDWORKS_Macros.htm
  - 매크로 편집/디버그: https://help.solidworks.com/2022/english/api/sldworksapiprogguide/gettingstarted/edit_or_debug_solidworks_macro.htm
  - 64비트 VBA 주의: https://help.solidworks.com/2022/English/api/sldworksapiprogguide/Overview/VBA_and_SolidWorks_x64.htm
- 검증상태: verified-from-official (2022 전용, 사용자 제공 공식 URL)
- 확인일: 2026-07-06
- 대상 버전: **SolidWorks 2022, VBA 7 / 64-bit**

## ⚠️ 버전 제약 (이 소프트웨어 코드 생성 시 절대 규칙)

- **반드시 SOLIDWORKS 2022 공식 API Help 문서만 기준**으로 작성한다.
  2023/2024/2025 이후 버전 API나 C# 전용 문법을 쓰지 마라.
- **VBA 7 / 64-bit SOLIDWORKS 기준**: 외부 DLL 선언 시 `PtrSafe`, `LongPtr` 주의.
- 모든 코드에 `Option Explicit`, 에러 처리, `Nothing` 체크,
  `swFileLoadError_e` / `swFileSaveError_e` 등 에러값 확인 포함.
- 선택 기반 API 사용 전 `ClearSelection2` 고려. 문서 열 때 `OpenDoc6`의 반환
  `IModelDoc2`와 Errors/Warnings를 반드시 확인.
- 확실하지 않으면 지어내지 말고 스캐폴드로 남기고 사용자에게 확인 요청.

## 핵심 객체/명령

| 인터페이스 | 용도 | 공식 문서 |
|---|---|---|
| **ISldWorks** | 최상위 앱 객체(문서 열기/닫기/생성) | .../ISldWorks_methods.html |
| **IModelDoc2** | 파트/어셈블리/도면 공통 문서 객체(거의 모든 매크로의 중심) | .../IModelDoc2_members.html |
| **IModelDocExtension** | 확장 문서 기능(SelectByID2 등) | .../IModelDocExtension~SelectByID2.html |
| **IAssemblyDoc** | 어셈블리 전용 API | .../IAssemblyDoc_members.html |
| **IComponent2** | 어셈블리 컴포넌트(변환/억제/경로) | .../IComponent2_methods.html |
| **IFeatureManager** | 피처 생성/관리 | .../IFeatureManager_methods.html |
| **ISelectionMgr** | 선택 객체 관리 | .../ISelectionMgr_members.html |
| **MathTransform** | 좌표/변환(어셈블리 기준 좌표, 컴포넌트 변환) | sldworksapi MathTransform |

핵심 메서드: `OpenDoc6`(열기), `Save3`(저장), `CloseDoc`(닫기),
`SelectByID2`(선택), `ClearSelection2`(선택 해제), `ActivateDoc3`(활성화),
`ExportToDWG2`(IPartDoc: DXF/DWG 내보내기).

## 최소 동작 예제

```vba
' SOLIDWORKS 2022 VBA (VBA 7 / 64-bit). 공식: OpenDoc6 / Save3 / CloseDoc.
Option Explicit

Sub Main()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2
    Dim fileErr As Long, fileWarn As Long
    Const swDocPART As Long = 1          ' swDocumentTypes_e.swDocPART
    Const swOpenSilent As Long = 1       ' swOpenDocOptions_e.swOpenDocOptions_Silent

    Set swApp = Application.SldWorks
    If swApp Is Nothing Then Exit Sub

    ' OpenDoc6: 문서 타입/옵션/설정명/에러/경고 인자. 반환 ModelDoc2와 에러 확인 필수.
    Set swModel = swApp.OpenDoc6("C:\parts\bracket.SLDPRT", swDocPART, _
                                 swOpenSilent, "", fileErr, fileWarn)
    If swModel Is Nothing Then
        Debug.Print "열기 실패 swFileLoadError_e=" & fileErr
        Exit Sub
    End If

    ' 열어도 항상 활성은 아님 — 필요 시 ActivateDoc3 로 명시 활성화.
    ' 작업 로직 ...

    ' Save3: 저장 옵션/에러/경고. swFileSaveError_e 확인.
    Dim saveErr As Long, saveWarn As Long
    Const swSaveAsOptions_Silent As Long = 1
    swModel.Save3 swSaveAsOptions_Silent, saveErr, saveWarn
    If saveErr <> 0 Then Debug.Print "저장 경고/에러 swFileSaveError_e=" & saveErr

    swApp.CloseDoc swModel.GetTitle
End Sub
```

## 자주 쓰는 작업

작업 전 항상: `Option Explicit` + `Nothing` 체크 + 에러값 확인. 공식 예제 페이지의
Preconditions/Postconditions까지 참고해 에러처리를 넣는다.

### 1. 선택 (SelectByID2, 사전 ClearSelection2)
```vba
swModel.ClearSelection2 True
' SelectByID2(name, type, x,y,z, append, mark, callout, selectOption)
Dim ok As Boolean
ok = swModel.Extension.SelectByID2("면1@bracket", "FACE", 0, 0, 0, False, 0, Nothing, 0)
```
공식: IModelDocExtension~SelectByID2. 여러 선택은 "Selection Lists Example(VB)" 참고.

### 2. 어셈블리 컴포넌트 순회 + 변환 (IAssemblyDoc / IComponent2 / MathTransform)
```vba
Dim swAssy As SldWorks.AssemblyDoc
Dim vComps As Variant, i As Long
Set swAssy = swModel                       ' 어셈블리 문서일 때
vComps = swAssy.GetComponents(False)        ' 최상위만 아닌 전체 = False
For i = 0 To UBound(vComps)
    Dim swComp As SldWorks.Component2
    Set swComp = vComps(i)
    If Not swComp Is Nothing Then
        Dim xform As SldWorks.MathTransform
        Set xform = swComp.Transform2         ' 어셈블리 기준 좌표 변환
        Debug.Print swComp.Name2
    End If
Next i
```
공식: IAssemblyDoc/IComponent2 멤버 문서. 어셈블리 기준 좌표는 Transform2 + MathTransform.

### 3. 하위 파트 각각 저장 (BOM/중복중량 작업 계열)
```vba
' 컴포넌트의 ModelDoc2 를 얻어 개별 저장. Nothing/에러 확인 필수.
Dim swCompModel As SldWorks.ModelDoc2
Set swCompModel = swComp.GetModelDoc2
If Not swCompModel Is Nothing Then
    Dim e As Long, w As Long
    swCompModel.Save3 1, e, w
End If
```

### 4. 열린 문서 경로 목록 / 문서 복사
공식 예제: "Get Paths of Open Documents Example (VB)", "Copy Document Example (VB)".

### 5. 파트 DXF/DWG 내보내기 (IPartDoc.ExportToDWG2)
공식: IPartDoc~IExportToDWG2. 판금/멀티바디는 "Get Features of Multibody Sheet Metal Part Example (VB)".

## 주의/버전 유의점

- **2022 전용**: 2023+ 신규 API/오버로드 금지. 메서드 시그니처는 위 공식 2022 URL로 확인.
- OpenDoc6는 열어도 활성 문서가 아닐 수 있음 → 필요 시 ActivateDoc2/ActivateDoc3.
- 64-bit VBA 7: 외부 API 선언에 `PtrSafe`/`LongPtr`. 32-bit 전용 선언 금지.
- 예찬님 작업(어셈블리 기준 좌표·컴포넌트 변환·BOM/중복중량·하위 파트 저장)은
  IAssemblyDoc, IComponent2, IModelDoc2, IModelDocExtension, MathTransform 문서를 함께 참고.
- 매크로는 UI 동작을 기록(Record Macros Example) → VBA/VSTA에서 수정하는 방식이 가장 쉬움.
