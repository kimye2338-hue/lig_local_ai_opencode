# MS Outlook 2016 VBA — 공식 API 참조

- 공식 출처: https://learn.microsoft.com/en-us/office/vba/api/outlook.mailitem, https://learn.microsoft.com/en-us/office/vba/api/outlook.application.createitem
- 검증상태: verified-from-official
- 확인일: 2026-07-06

## 핵심 객체/명령

| 객체/메서드 | 용도 |
|-------------|------|
| **Application.CreateItem(olMailItem)** | 새 메일 아이템 생성 |
| **MailItem** | 이메일 메시지 객체, 제목/본문/수신자 설정 |
| **MailItem.Subject** | 메일 제목 |
| **MailItem.Body / HTMLBody** | 메일 본문 (텍스트 또는 HTML) |
| **MailItem.Recipients** | 수신자 컬렉션 (To, Cc, Bcc) |
| **MailItem.Send()** | 메일 발송 |
| **MailItem.Display()** | 메일 창 표시 |
| **MailItem.Attachments** | 첨부파일 컬렉션 |

## 최소 동작 예제

```vb
' Outlook 2016 VBA 최소 예제
Sub SendSimpleEmail()
    Dim objOutlook As Object
    Dim objMailItem As Object

    ' Outlook 애플리케이션 얻기
    Set objOutlook = CreateObject("Outlook.Application")

    ' 새 MailItem 생성 (olMailItem = 0)
    Set objMailItem = objOutlook.CreateItem(0)

    ' 메일 작성
    With objMailItem
        .To = "recipient@example.com"
        .CC = "cc@example.com"
        .Subject = "Test Email"
        .Body = "This is a test message"
        .Send
    End With

    Set objMailItem = Nothing
    Set objOutlook = Nothing
End Sub
```
출처: Microsoft Learn - MailItem object

## 자주 쓰는 작업

### 1. 메일 생성 및 표시
```vb
Dim myItem As Object
Set myItem = Application.CreateItem(olMailItem)
myItem.Subject = "Mail to myself"
myItem.Display
```

### 2. 받은편지함 메일 접근
```vb
Dim myNamespace As Object
Dim myFolder As Object
Dim myItem As Object

Set myNamespace = Application.GetNamespace("MAPI")
Set myFolder = myNamespace.GetDefaultFolder(olFolderInbox)

' 두 번째 메일 접근
Set myItem = myFolder.Items(2)
myItem.Display
```

### 3. HTML 본문 설정
```vb
Dim myItem As Object
Set myItem = Application.CreateItem(olMailItem)
myItem.BodyFormat = olFormatHTML
myItem.HTMLBody = "<html><body><b>Bold Text</b></body></html>"
```

### 4. 수신자 추가 (자동 주소 확인)
```vb
With objMailItem
    .Recipients.Add "user@example.com"
    .Recipients.ResolveAll
    .Subject = "Test"
    .Body = "Message"
End With
```

### 5. 첨부파일 추가
```vb
objMailItem.Attachments.Add "C:\path\to\file.pdf"
```

## 주의/버전 유의점

- **CreateItem 상수**: olMailItem = 0 (상수명 또는 숫자 모두 사용 가능)
- **BodyFormat**: olFormatPlain (1) 또는 olFormatHTML (2)
- **Recipients.ResolveAll()**: Outlook 주소록에서 수신자 확인, 필수 호출
- **Late Binding**: CreateObject("Outlook.Application")은 형식 안전성이 낮지만 Outlook 설치 여부 확인 가능
- **Early Binding**: 프로젝트에서 "Microsoft Outlook 16.0 Object Library" 참조 추가 시 IntelliSense 지원
- **DeleteAfterSubmit**: 발송 후 초안폴더에 남기지 않으려면 `.DeleteAfterSubmit = True`
