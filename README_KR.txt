============================================================
 DicomReslice0p2 — DICOM 0.2mm 균일 재슬라이스 도구
 Developed by Team InterOral  (v1.0.0)
============================================================

이 프로그램은 DICOM 시리즈를 불러와 균일한 0.2mm 등방(isotropic) 간격으로
다시 슬라이스(리샘플)한 뒤, 새 DICOM 시리즈로 내보냅니다.
실제 변환은 PC에 설치된 3D Slicer가 수행하며, 이 앱은 그 작업을 자동으로
실행해 주는 Python 기반 GUI 입니다.

[준비물]
 - Windows PC
 - 3D Slicer 설치 (5.x, 검증은 5.12.0 에서 진행)
   다운로드: https://download.slicer.org/

[실행 방법]
 1. DicomReslice0p2.exe 더블 클릭.
 2. "DICOM folder": 변환할 DICOM 시리즈가 들어 있는 폴더 선택 (Browse…).
 3. "Slicer.exe": 자동으로 찾습니다. 비어 있거나 틀리면 직접 지정 (Browse…).
    (예: C:\Users\<사용자>\AppData\Local\slicer.org\3D Slicer 5.x\Slicer.exe)
 4. "Spacing (mm)": 기본 0.2. 필요 시 변경.
 5. "Run" 클릭. 로그가 흐르고, 끝나면 완료 메시지가 표시됩니다.

[출력]
 - 선택한 DICOM 폴더 아래에 corrected\ 폴더가 생기고, 그 안에 0.2mm 등방으로
   균일 리샘플된 새 DICOM 파일(IMG0001.dcm ...)이 저장됩니다.
 - 원본 환자 정보(이름/ID/생년월일/성별)와 Study 정보는 그대로 승계되며,
   SeriesDescription 에 "corrected 0.2 mm"가 붙은 새 Series(번호 9001)로 만들어집니다.
 - 원본 DICOM 파일은 변경되지 않습니다.
 - 실행 로그가 corrected\reslice_log_<날짜_시각>.txt 로 자동 저장됩니다
   (성공/실패 모두, 오류 내용 포함). 문제 발생 시 GitHub Issues에 이 파일을
   첨부해 주시면 원인 파악에 도움이 됩니다:
   https://github.com/TeamInterOral/DicomReslice0p2/issues

[동작 원리]
 - 무거운 처리(로드 → 리샘플 → DICOM 내보내기)는 설치된 3D Slicer가 담당합니다.
 - 앱은 Slicer를 백그라운드로 호출해 ResampleScalarVolume(linear 보간)로 지정
   간격에 맞춰 재표본화한 뒤, 결과를 새 DICOM 시리즈로 내보냅니다.
 - 같은 폴더에서 다시 실행해도, 이전에 만든 corrected 결과를 원본으로 잘못
   읽지 않도록 처리되어 있습니다(원본 시리즈를 자동 선택).

[참고/주의]
 - DICOM 폴더에 .dcm 이 아닌 파일이 섞여 있어도 무시하고 진행하지만,
   가능하면 순수한 DICOM 시리즈 폴더를 지정하는 것이 깔끔합니다.
 - 보간(interpolation)은 linear 를 사용합니다.
 - 이미 0.2mm 로 균일한 데이터라면 결과는 동일 격자에 재배치된 형태가 됩니다.
 - 변환에는 데이터 크기에 따라 수십 초~수 분이 걸릴 수 있습니다.
 - 다른 PC로 옮길 때는 DicomReslice0p2.exe 하나만 복사하면 됩니다
   (대상 PC에 3D Slicer 설치 필요).

[무결성 확인 — 선택]
 - 동봉된 DicomReslice0p2.exe.sha256 의 값과, 받은 exe 의 해시를 비교해
   파일이 변조되지 않았는지 확인할 수 있습니다.
   PowerShell:  Get-FileHash .\DicomReslice0p2.exe -Algorithm SHA256

[소스에서 직접 빌드 — 선택]
   pip install pyinstaller
   pyinstaller --noconsole --onefile --name DicomReslice0p2 --version-file version_info.txt dicom_reslice_app.py
   결과물: dist\DicomReslice0p2.exe

------------------------------------------------------------
 (c) Team InterOral
------------------------------------------------------------
