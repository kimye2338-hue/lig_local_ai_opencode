---
title: SolidWorks 2022 VBA API 레퍼런스
domain: solidworks
aliases: solidworks, 솔리드웍스, sldworks, 파트, 어셈블리, 도면, 매크로, vba, 돌출, 메이트, extrude
sources: [help.solidworks.com/2022/english/api/, CodeStack.net, thecadcoder.com]
verified: true
confidence: medium
version: "2022"
reviewed: 2026-07-07
---

# SolidWorks 2022 VBA API (오프라인 매크로 생성용)

> 대상: SolidWorks **2022**. 2022에 존재/유효한 API만 사용. 이후 추가 API 금지.

## ⚠️ 절대 규칙 (매크로 생성 전 항상 확인)

1. **내부 단위는 항상 SI(미터/라디안)** — 화면 표시 단위(mm 등)와 무관하게 API 인자는 전부
   미터·라디안. "10mm 돌출" → 코드는 `0.01`. (가장 흔한 버그: mm 값을 그대로 넣어 1000배 형상)
2. **필수 보일러플레이트**:
   ```vba
   Option Explicit
   Dim swApp As SldWorks.SldWorks
   Dim swModel As SldWorks.ModelDoc2
   Sub main()
       Set swApp = Application.SldWorks
       Set swModel = swApp.ActiveDoc
       If swModel Is Nothing Then MsgBox "열린 문서 없음": Exit Sub
   End Sub
   ```
3. **선택(Selection)이 먼저, 동작이 다음** — 대부분 피처 API는 스케치/면이 선택된 상태를 전제.
   `SelectByID2`/`MultiSelect2`로 명시 선택 후 호출. 선택 실패가 "조용한 실패"의 최대 원인.
4. **반환값 Nothing 체크** — `AddComponent5`/`AddMate5`/`FeatureExtrusion3` 등 생성 계열은 실패
   시 예외 대신 `Nothing` 반환. 반드시 `If x Is Nothing Then` 확인.
5. **파라미터 순서 검증** — FeatureCut4/FeatureFillet3 등 오버로드는 연도별 시그니처 차이 이력.
   실사용 전 SolidWorks 2022에서 `Tools > Macro > Record`로 정확한 인자를 재확인. Enum은 정수
   하드코딩 말고 **이름(Named Constant)**으로 참조.

## 핵심 객체 모델 & 진입점

- **ISldWorks** — 최상위. 매크로 내부 `Application.SldWorks`, 외부(Excel VBA) `GetObject(, "SldWorks.Application")`.
- **IModelDoc2** — 열린 문서 공통. `swApp.ActiveDoc`.
- **IPartDoc / IAssemblyDoc / IDrawingDoc** — 문서 타입별.
- **IFeatureManager** `swModel.FeatureManager` · **ISelectionMgr** `swModel.SelectionManager`
- **IModelDocExtension** `swModel.Extension` — SaveAs3, CustomPropertyManager, CreateMassProperty 등.

## 새 파트 + 스케치 + 돌출(Extrude)
```vba
Set swDoc = swApp.NewDocument(swApp.GetUserPreferenceStringValue(swDefaultTemplatePart), 0, 0, 0)
swDoc.Extension.SelectByID2 "Front Plane", "PLANE", 0,0,0, False, 0, Nothing, 0
Set swSk = swDoc.SketchManager
swSk.InsertSketch True
swSk.CreateCornerRectangle 0, 0.01, 0, 0.01, 0, 0   ' 미터
swDoc.ClearSelection2 True
swSk.InsertSketch True
Set swFeat = swDoc.FeatureManager.FeatureExtrusion3(True, False, False, _
   swEndCondBlind, swEndCondBlind, 0.02, 0, False, False, False, True, 0, 0, _
   False, False, False, False, True, False, True, swEndCondBlind, 0, False)  ' 0.02=20mm
```

## 컷 / 필렛 / 치수
- `swDoc.FeatureManager.FeatureCut4(...)` — FeatureExtrusion3와 유사(Thin/Draft 추가). ⚠️ 파라미터 재확인.
- 필렛: 엣지 선택 후 `FeatureManager.FeatureFillet3(swFeatureFilletConstant, 0.005, 0,0, Empty*6)`. ⚠️ 배열 순서 버전 민감.
- 치수: 스케치 엔티티 선택 후 `Set swDim = swModel.AddDimension2(0.05, 0.05, 0)`.

## 조립품에 컴포넌트 삽입 + 메이트
```vba
Set swAsm = swDoc  ' AssemblyDoc
Set swComp = swAsm.AddComponent5("C:\parts\bracket.sldprt", _
   swAddComponentConfigOptions_CurrentSelectedConfig, "", False, "", 0,0,0)
If swComp Is Nothing Then MsgBox "삽입 실패": Exit Sub
' 두 원통면 MultiSelect2 후 동심 메이트:
Set swMate = swAsm.AddMate5(swMateCONCENTRIC, swMateAlignALIGNED, False, 0,0,0,0,0,0,0,0, False, False, 0, swAddMateError_ErrorUknown)
swAsm.ForceRebuild3 False
```
- 메이트 성립 조건: 최소 한쪽 컴포넌트가 Float(둘 다 Fixed면 실패). 동심은 거리 파라미터 0.

## 모델 → 도면 + 모델뷰 + BOM + 노트
```vba
modelPath = swDoc.GetPathName
Set swDrw = swApp.NewDocument(swApp.GetUserPreferenceStringValue(swDefaultTemplateDrawing), 0,0,0)
Set swView = swDrw.CreateDrawViewFromModelView3(modelPath, "*Front", 0.1, 0.1, 0)  ' "*Top"/"*Isometric"
' BOM: swDrw.InsertBomTable3("bom-standard.sldbomtbt", 0.05,0.05, swBOMConfigurationAnchor_TopLeft, swBomType_PartsOnly, "Default", False)
' 노트: swDrw.InsertNote("검토완료") 후 .SetTextPoint 0.05,0.05,0
```

## 내보내기 (STEP / PDF / DXF)
```vba
Dim errs As Long, warns As Long
swModel.Extension.SaveAs3 "C:\out\part.step", swSaveAsCurrentVersion, swSaveAsOptions_Silent, Nothing, Nothing, errs, warns
```
- ⚠️ STEP/IGES/STL 저장은 **대상이 ActiveDoc이어야** 성공 → 배치 시 `swApp.ActivateDoc3` 먼저.
- PDF는 뷰 전용(열람 전용) 문서에서 불가. 확장자만 바꿔 .pdf/.dxf 동일 호출.

## 폴더 일괄 처리(배치)
```vba
sFile = Dir("C:\batch\*.sldprt")
Do While sFile <> ""
    Set swDoc = swApp.OpenDoc6("C:\batch\" & sFile, swDocPART, swOpenDocOptions_Silent, "", errs, warns)
    ' ... 작업 ...
    swApp.CloseDoc swDoc.GetTitle
    sFile = Dir()
Loop
```

## 커스텀 프로퍼티 (읽기/쓰기)
```vba
Set swCP = swModel.Extension.CustomPropertyManager("")   ' "" = 문서 전체
swCP.Add3 "PartNumber", swCustomInfoText, "PN-1001", swCustomPropertyReplaceValue   ' Replace 없으면 덮어쓰기 안 됨
swCP.Get5 "PartNumber", False, valOut, resolvedOut, Nothing
' 구성별: For each in swModel.GetConfigurationNames → CustomPropertyManager(confName)
```

## 피처/컴포넌트 순회 · 질량 속성 · 저장
```vba
Set swFeat = swModel.FirstFeature
Do While Not swFeat Is Nothing
    Debug.Print swFeat.Name & " : " & swFeat.GetTypeName2
    Set swFeat = swFeat.GetNextFeature
Loop
vComps = swAsm.GetComponents(False)   ' 최상위만
Set swMass = swModel.Extension.CreateMassProperty   ' .Mass(kg) .Volume(m^3) .SurfaceArea(m^2) — 전부 SI
swModel.ForceRebuild3 False
swModel.Save3 swSaveAsOptions_Silent, errs, warns
```

## 자주 쓰는 Enum (이름으로 참조)
`swDocumentTypes_e`(swDocPART/ASSEMBLY/DRAWING) · `swSelectType_e`(swSelFACES/EDGES/...) ·
`swEndConditions_e`(swEndCondBlind/ThroughAll/MidPlane) · `swMateType_e`(swMateCOINCIDENT/CONCENTRIC/...) ·
`swMateAlign_e`(ALIGNED/ANTI_ALIGNED) · `swCustomInfoType_e`(swCustomInfoText/Number/...) ·
`swSaveAsOptions_e`(Silent/Copy) · `swOpenDocOptions_e`(Silent/ReadOnly).

## 신뢰도 메모
공식 API Help(2022) + CodeStack/TheCADCoder 교차확인. 파트/조립/도면/저장/프로퍼티/순회 코드는
예제 페이지에서 직접 확인. **Cut/Fillet/Dimension/BOM 파라미터 순서와 Enum 정수값은 미확인** →
실사용 전 매크로 레코딩으로 검증. 오프라인 환경에선 레코딩 검증이 가장 확실.
