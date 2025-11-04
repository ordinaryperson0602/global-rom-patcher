"""
ROM Tool - EXE 빌드 자동화 스크립트

이 스크립트는 PyInstaller를 사용하여 Python 소스 코드를 Windows EXE 파일로 변환합니다.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def print_banner():
    """빌드 시작 배너 출력"""
    print("=" * 70)
    print("🔨 ROM Tool - EXE 빌드 스크립트")
    print("=" * 70)
    print()

def check_requirements():
    """필수 요구사항 확인"""
    print("📋 필수 요구사항 확인 중...")
    
    # PyInstaller 설치 확인
    try:
        import PyInstaller
        print(f"  ✓ PyInstaller 설치됨 (버전: {PyInstaller.__version__})")
    except ImportError:
        print("  ✗ PyInstaller가 설치되지 않았습니다.")
        print("\n다음 명령어로 설치하세요:")
        print("  pip install pyinstaller")
        sys.exit(1)
    
    # 필수 파일 확인
    required_files = [
        "main.py",
        "프로그램_사용자_동의서.txt"
    ]
    
    required_dirs = [
        "Tools",
        "config",
        "core",
        "steps",
        "utils"
    ]
    
    for file in required_files:
        if not os.path.exists(file):
            print(f"  ✗ 필수 파일 없음: {file}")
            sys.exit(1)
        print(f"  ✓ {file}")
    
    for dir in required_dirs:
        if not os.path.isdir(dir):
            print(f"  ✗ 필수 폴더 없음: {dir}")
            sys.exit(1)
        print(f"  ✓ {dir}/")
    
    print()

def clean_build():
    """이전 빌드 결과 정리"""
    print("🧹 이전 빌드 결과 정리 중...")
    
    clean_dirs = ["build", "dist"]
    clean_files = ["*.spec"]
    
    for dir in clean_dirs:
        if os.path.exists(dir):
            shutil.rmtree(dir)
            print(f"  ✓ 삭제됨: {dir}/")
    
    for pattern in clean_files:
        for file in Path(".").glob(pattern):
            file.unlink()
            print(f"  ✓ 삭제됨: {file}")
    
    print()

def build_exe():
    """PyInstaller로 EXE 빌드"""
    print("🚀 EXE 빌드 시작...")
    print()
    
    # PyInstaller 명령어 구성
    command = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",  # 폴더 구조로 패키징 (빠른 실행)
        "--console",
        "--name", "ROM_Tool",
        "--icon=NONE",
        
        # 데이터 파일 추가
        "--add-data", "프로그램_사용자_동의서.txt;.",
        "--add-data", "Tools;Tools",
        "--add-data", "config;config",
        "--add-data", "core;core",
        "--add-data", "steps;steps",
        "--add-data", "utils;utils",
        
        # 숨겨진 import
        "--hidden-import=structlog",
        "--hidden-import=ctypes",
        "--hidden-import=re",
        "--hidden-import=pathlib",
        "--hidden-import=json",
        "--hidden-import=shutil",
        "--hidden-import=typing",
        
        # 메인 파일
        "main.py"
    ]
    
    print(f"실행 명령어: {' '.join(command)}")
    print()
    
    try:
        result = subprocess.run(command, check=True, capture_output=False)
        print()
        print("✅ 빌드 성공!")
        return True
    except subprocess.CalledProcessError as e:
        print()
        print(f"❌ 빌드 실패: {e}")
        return False

def show_result():
    """빌드 결과 표시"""
    print()
    print("=" * 70)
    print("📦 빌드 완료!")
    print("=" * 70)
    
    dist_path = Path("dist/ROM_Tool")
    
    if dist_path.exists():
        print(f"\n📁 빌드 결과 위치: {dist_path.absolute()}")
        print("\n포함된 파일:")
        
        # 주요 파일 목록
        main_files = [
            "ROM_Tool.exe",
            "프로그램_사용자_동의서.txt"
        ]
        
        for file in main_files:
            file_path = dist_path / file
            if file_path.exists():
                size = file_path.stat().st_size / (1024 * 1024)  # MB
                print(f"  ✓ {file} ({size:.2f} MB)")
            else:
                print(f"  ✗ {file} (없음)")
        
        # 폴더 확인
        folders = ["Tools", "config", "core", "steps", "utils"]
        for folder in folders:
            folder_path = dist_path / folder
            if folder_path.exists():
                print(f"  ✓ {folder}/")
            else:
                print(f"  ✗ {folder}/ (없음)")
        
        print("\n" + "=" * 70)
        print("📌 다음 단계:")
        print("=" * 70)
        print("1. 빌드된 프로그램 테스트:")
        print(f"   cd {dist_path}")
        print("   ROM_Tool.exe")
        print()
        print("2. 배포용 압축 파일 생성:")
        print(f"   Compress-Archive -Path '{dist_path}\\*' -DestinationPath 'ROM_Tool_v1.0.0.zip'")
        print()
        print("3. GitHub Release 생성:")
        print("   - GitHub 저장소 → Releases → Create a new release")
        print("   - 압축 파일 업로드")
        print()
    else:
        print("\n❌ dist 폴더를 찾을 수 없습니다.")
        print("빌드가 실패했을 수 있습니다.")

def main():
    """메인 실행 함수"""
    print_banner()
    check_requirements()
    clean_build()
    
    if build_exe():
        show_result()
    else:
        print("\n❌ 빌드 실패")
        sys.exit(1)

if __name__ == "__main__":
    main()

