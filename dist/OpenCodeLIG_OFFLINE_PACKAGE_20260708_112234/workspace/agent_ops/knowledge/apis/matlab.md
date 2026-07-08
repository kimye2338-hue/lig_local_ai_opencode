# MATLAB R2024a — 공식 API 참조

- 공식 출처: https://www.mathworks.com/help/matlab/ref/matlabwindows.html, https://www.mathworks.com/help/matlab/matlab_env/startup-options.html
- 검증상태: verified-from-official
- 확인일: 2026-07-06

## 핵심 객체/명령

### 명령줄 옵션
| 옵션 | 용도 |
|------|------|
| **-batch "statement"** | 비대화형 실행 (자동 종료) |
| **-r "statement"** | 대화형 실행 |
| **-nojvm** | Java Virtual Machine 비활성화 |
| **-logfile filename** | 출력을 파일로 기록 |
| **-sd folder** | 초기 작업 폴더 설정 |
| **-wait** | 완료까지 대기 (배치 스크립트용) |

## 최소 동작 예제

### Windows 배치 모드 스크립트
```batch
@echo off
REM MATLAB R2024a 최소 예제
matlab -batch "disp('Hello MATLAB'); disp(version);" -wait
pause
```

### MATLAB 스크립트 파일 (myscript.m)
```matlab
% MATLAB R2024a 최소 예제
disp('Starting MATLAB script...');
A = [1, 2; 3, 4];
result = A * 2;
disp('Result:');
disp(result);
save('output.mat', 'result');
exit(0);
```

명령줄: `matlab -batch "run('myscript.m')" -wait`

출처: MathWorks official documentation

## 자주 쓰는 작업

### 1. 비대화형 스크립트 실행
```batch
REM -batch 옵션: 성공시 exit code 0, 실패시 0이 아닌 값
matlab -batch "result = sqrt(16); disp(result);" -wait
```

### 2. 함수 실행 및 인자 전달
```batch
matlab -batch "myfunction(5, 'output.txt');" -wait
```

### 3. 작업 폴더 지정 및 로그 기록
```batch
matlab -sd "C:\work" -logfile "matlab_log.txt" -batch "main_script;" -wait
```

### 4. 함수 정의 및 실행
```matlab
% batch_processor.m
function batch_processor(inputfile)
    % 입력 파일 읽기
    data = readmatrix(inputfile);

    % 처리
    result = data * 2;

    % 결과 저장
    writematrix(result, 'output.csv');

    disp('Processing complete');
    exit(0);
end
```

명령줄: `matlab -batch "batch_processor('input.csv')" -wait`

### 5. 병렬 처리 (배치 작업)
```matlab
% parallel_job.m
parpool('local', 4);  % 4개 워커 풀 생성
A = randn(1000);
result = A * A';
save('large_result.mat', 'result');
delete(gcp('nocreate'));
exit(0);
```

## 주의/버전 유의점

- **-batch vs -r**: -batch는 자동 종료, -r은 대화형 (둘 다 사용하지 말 것)
- **Exit Code**: -batch 성공=0, 실패=1 이상 (배치 스크립트에서 확인 가능)
- **Workspace**: -batch 시작 시 빈 workspace, -r도 마찬가지
- **-wait 필수**: 배치 파일에서는 -wait로 MATLAB 완료 대기
- **JVM 비활성화**: -nojvm으로 시작 시간 단축하지만 Java 기능 불가
- **경로 지정**: -sd로 작업 폴더 설정, 상대경로는 해당 폴더 기준
- **함수 스크립트 변환**: 배치 실행시 .m은 스크립트 아닌 함수로 작성 권장 (workspace 오버헤드 감소)
