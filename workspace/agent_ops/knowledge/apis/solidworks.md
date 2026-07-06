# SolidWorks API — 공식 API 참조

- 공식 출처: https://help.solidworks.com (ISldWorks, IModelDoc2 interfaces), https://help.solidworks.com/2019/english/api/sldworksapi/
- 검증상태: partial
- 확인일: 2026-07-06

## 핵심 객체/명령

### ISldWorks 인터페이스 (최상위)
| 메서드/속성 | 용도 |
|------------|------|
| **CreateDocument(template, options, x, y)** | 새 문서 생성 |
| **OpenDocument(path, docType, options)** | 기존 문서 열기 |
| **ActiveDoc** | 현재 활성 문서 반환 (IModelDoc2) |
| **ActivateDoc3(docName, options)** | 특정 문서 활성화 |

### IModelDoc2 인터페이스 (문서 객체)
| 메서드/속성 | 용도 |
|------------|------|
| **GetTitle()** | 문서 제목 (파일명 제외) 반환 |
| **SaveAs3(filename, saveType, options)** | 다른 이름으로 저장 |
| **Save()** | 현재 파일명으로 저장 |
| **Close()** | 문서 닫기 |
| **GetPathName()** | 전체 파일 경로 반환 |

## 최소 동작 예제

### VBA 최소 예제 (Early Binding)
```vb
' SolidWorks 2019+ VBA 최소 예제
' 참조: SolidWorks 2019 Type Library 추가 필요

Sub BasicSolidWorksOps()
    Dim swApp As SldWorks.SldWorks
    Dim swModel As SldWorks.ModelDoc2
    
    ' SolidWorks 애플리케이션 객체 얻기
    Set swApp = Application.SldWorks
    
    ' 또는 CreateObject로 새 인스턴스 시작
    ' Set swApp = CreateObject("SldWorks.Application")
    ' swApp.Visible = True
    
    ' 현재 활성 문서 열기
    Set swModel = swApp.ActiveDoc
    
    ' 문서 열기 (전체 경로 필요)
    Set swModel = swApp.OpenDocument("C:\path\to\drawing.sldprt", 1, 0)
    
    ' 문서 정보 출력
    If Not swModel Is Nothing Then
        MsgBox "Document: " & swModel.GetTitle()
        MsgBox "Path: " & swModel.GetPathName()
        
        ' 다른 이름으로 저장
        swModel.SaveAs3 "C:\output\new_name.sldprt", 0, 0
        
        ' 문서 닫기
        swModel.Close
    End If
End Sub
```

출처: SolidWorks API Help (Open Document, Get Document Information examples)

## 자주 쓰는 작업

### 1. 문서 열기 및 활성화
```vb
Dim swApp As Object
Dim swModel As Object

Set swApp = CreateObject("SolidWorks.Application")
Set swModel = swApp.OpenDocument("C:\part.sldprt", 1, 0)
' docType: 1=part, 2=assembly, 3=drawing
```

### 2. 현재 활성 문서 정보 조회
```vb
If Not swApp.ActiveDoc Is Nothing Then
    Set swModel = swApp.ActiveDoc
    Debug.Print swModel.GetTitle()
    Debug.Print swModel.GetPathName()
End If
```

### 3. 문서 저장
```vb
' 현재 파일명으로 저장
swModel.Save

' 다른 이름으로 저장 (SLDPRT 형식, 옵션 0)
swModel.SaveAs3 "C:\new_location\part.sldprt", 0, 0
```

### 4. 모든 열린 문서 목록 조회
```vb
' GetNames returns array of document names
Dim docNames As Variant
docNames = swApp.GetDocumentNames

For i = 0 To UBound(docNames)
    Debug.Print docNames(i)
Next i
```

### 5. 문서 닫기
```vb
' 저장 안 함
swModel.Close False

' 저장 후 닫기
swModel.Close True
```

## 주의/버전 유의점

- **참조 라이브러리**: Early binding 사용 시 "SolidWorks [버전] Type Library" 추가 필수
- **Late Binding**: `CreateObject("SolidWorks.Application")`은 형식 검사 없지만 Intellisense 불가
- **파일 경로**: 항상 전체 경로(절대경로) 필요, 상대경로 미지원
- **Document Type**: OpenDocument 두 번째 인자 - 1=part, 2=assembly, 3=drawing
- **ActiveDoc**: 사용자가 다른 문서로 전환하면 ActiveDoc 반환값 변경
- **버전 호환성**: 구 SolidWorks 버전은 ISldWorks 인터페이스만 지원, IModelDoc2 사용 시 최신 버전 필요
- **COM 접근**: SolidWorks는 COM 객체이므로 VBA, VB.NET, C# 등에서 활용 가능
