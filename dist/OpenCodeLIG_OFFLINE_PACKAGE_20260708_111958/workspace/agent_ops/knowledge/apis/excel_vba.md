# MS Excel 2016 VBA — 공식 API 참조

- 공식 출처: https://learn.microsoft.com/en-us/office/vba/api/overview/excel
- 검증상태: verified-from-official
- 확인일: 2026-07-06

## 핵심 객체/명령

| 객체 | 용도 |
|------|------|
| **Application** | Excel 애플리케이션 자체, 전역 메서드/속성 접근 |
| **Workbook** | 워크북 파일 열기/저장/관리 |
| **Worksheet** | 시트 접근, Range 반환 |
| **Range** | 셀/셀 범위 읽기/쓰기, 수식 설정 |

## 최소 동작 예제

```vb
' Excel 2016 VBA 최소 예제
Sub BasicExcelOps()
    Dim wb As Workbook
    Dim ws As Worksheet
    Dim r As Range

    ' 새 워크북 생성
    Set wb = Workbooks.Add
    Set ws = wb.Sheets(1)

    ' 셀에 값 쓰기 (Range 이용)
    ws.Range("A1").Value = "Hello"

    ' Cells 속성으로도 접근 가능 (1,1 = A1)
    ws.Cells(1, 2).Value = "World"

    ' 셀 값 읽기
    Dim val As String
    val = ws.Range("A1").Value

    ' 파일 저장
    wb.SaveAs "C:\temp\test.xlsx"
    wb.Close
End Sub
```
출처: Microsoft Learn - Excel object model, Range object

## 자주 쓰는 작업

### 1. 워크북/시트 접근
```vb
' 활성 워크북의 첫 시트
Set ws = ActiveWorkbook.Sheets(1)

' 이름으로 시트 접근
Set ws = Workbooks("myfile.xlsx").Sheets("Sheet1")
```

### 2. 범위 읽기/쓰기
```vb
' 단일 셀
ws.Range("A1").Value = 42
Dim cellVal As Variant
cellVal = ws.Range("A1").Value

' 범위 (A1:B5)
ws.Range("A1:B5").Value = 100

' Cells로 동적 접근
ws.Cells(2, 1).Formula = "=Sum(B1:B5)"
```

### 3. 셀 서식 설정
```vb
' 폰트, 색상, 정렬
With ws.Range("A1")
    .Font.Bold = True
    .Interior.Color = RGB(255, 0, 0)
    .HorizontalAlignment = xlCenter
End With
```

### 4. 범위 반복
```vb
Dim r As Range
For Each r In ws.Range("A1:D10")
    If r.Value < 0 Then
        r.ClearContents
    End If
Next r
```

### 5. 수식 삽입
```vb
ws.Range("C1").Formula = "=A1+B1"
ws.Range("D1").FormulaR1C1 = "=R1C1+R1C2"
```

## 주의/버전 유의점

- **워크북 경로**: 파일명에 공백이 있으면 Workbooks("My File.xlsx")처럼 인용부호로 감싼다
- **Cells vs Range**: Cells(row, col)은 동적 인덱싱에 유리, Range("A1:B5")는 명시적이고 읽기 좋음
- **Offset 사용**: `ws.Range("A1").Offset(1, 1)` = B2 (상대 위치 이동)
- **Union 메서드**: 비연속 범위 `Application.Union(Range("A1"), Range("C1"))`
- **ScreenUpdating**: 반복 작업 시 `Application.ScreenUpdating = False`로 성능 향상
