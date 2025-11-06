"""
ROM Tool - EXE 빌드 자동화 스크립트

이 스크립트는 PyInstaller를 사용하여 Python 소스 코드를 Windows EXE 파일로 변환합니다.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# 프로젝트 루트 디렉토리로 이동
SCRIPT_DIR = Path(__file__).parent  # scripts/
PROJECT_ROOT = SCRIPT_DIR.parent    # 프로젝트 루트
os.chdir(PROJECT_ROOT)

# 버전 정보
VERSION = "v1.0.0"
EXE_NAME = f"GRP_{VERSION}"  # EXE 파일 이름
DIST_FOLDER_NAME = "Global_ROM_Patcher"  # 배포 폴더 이름

def print_banner():
    """빌드 시작 배너 출력"""
    print("=" * 70)
    print("🔨 Global ROM Patcher - EXE 빌드 스크립트")
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
        "assets/프로그램_사용자_동의서.txt"
    ]
    
    required_dirs = [
        "Tools",
        "src",
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
    clean_files = ["GRP_*.spec"]
    
    for dir in clean_dirs:
        if os.path.exists(dir):
            shutil.rmtree(dir)
            print(f"  ✓ 삭제됨: {dir}/")
    
    # .spec 파일은 scripts/ 폴더에 있을 수 있으므로 루트와 scripts 모두 확인
    for pattern in clean_files:
        for file in Path(".").glob(pattern):
            if file.name != "GRP_v1.0.0.spec":  # 원본 spec 파일은 보존
                file.unlink()
                print(f"  ✓ 삭제됨: {file}")
    
    print()

def build_exe():
    """PyInstaller로 EXE 빌드"""
    print("🚀 EXE 빌드 시작...")
    print()
    
    # 필수 파일 존재 확인
    print("📋 빌드 전 파일 확인:")
    agreement_file = "assets/프로그램_사용자_동의서.txt"
    tools_folder = "Tools"
    icon_file = "assets/icon.ico"
    python_embedded_folder = os.path.join("Tools", "python_embedded")
    
    if os.path.exists(agreement_file):
        print(f"  ✓ {agreement_file} 발견")
    else:
        print(f"  ✗ {agreement_file} 없음")
    
    if os.path.exists(tools_folder):
        print(f"  ✓ {tools_folder}/ 발견")
    else:
        print(f"  ✗ {tools_folder}/ 없음")
    
    if os.path.exists(python_embedded_folder):
        # python_embedded 폴더 크기 확인
        total_size = sum(
            os.path.getsize(os.path.join(dirpath, filename))
            for dirpath, _, filenames in os.walk(python_embedded_folder)
            for filename in filenames
        )
        print(f"  ✓ {python_embedded_folder}/ 발견 ({total_size / 1024 / 1024:.1f} MB)")
        print(f"    → Python 설치 불필요! (Embeddable Python 포함)")
    else:
        print(f"  ⚠️ {python_embedded_folder}/ 없음")
        print(f"    → Python이 시스템에 설치되어 있어야 합니다.")
        print(f"    → 권장: python setup_python_embedded.py 실행")
    
    if os.path.exists(icon_file):
        print(f"  ✓ {icon_file} 발견")
    else:
        print(f"  ✗ {icon_file} 없음")
    
    print()
    
    # PyInstaller 명령어 구성
    command = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",  # 단일 EXE 파일로 패키징
        "--console",
        "--name", EXE_NAME,
        "--icon", "assets/icon.ico",  # 아이콘 파일 지정
        
        # 데이터 파일 포함
        "--add-data", "Tools;Tools",  # Tools 폴더 포함 (~136 MB)
        "--add-data", "assets/프로그램_사용자_동의서.txt;assets",  # 동의서 파일 포함
        
        # 최적화 옵션
        "--optimize", "2",  # Python 최적화 레벨 2 (더 작은 크기, 더 빠른 실행)
        "--strip",  # 디버그 심볼 제거 (크기 감소)
        "--noupx",  # UPX 비활성화 (압축 해제 시간 단축)
        
        # 숨겨진 import (필수만)
        "--hidden-import=structlog",
        "--hidden-import=src",
        "--hidden-import=src.config",
        "--hidden-import=src.logger",
        "--hidden-import=src.progress",
        
        # 불필요한 모듈 제외
        "--exclude-module=tkinter",
        "--exclude-module=matplotlib",
        "--exclude-module=numpy",
        "--exclude-module=pandas",
        "--exclude-module=PIL",
        "--exclude-module=PyQt5",
        "--exclude-module=wx",
        
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

def copy_required_files():
    """--onefile 모드에서는 모든 파일이 EXE에 포함되므로 이 함수는 사용되지 않음"""
    print()
    print("=" * 70)
    print("📦 단일 EXE 파일 생성 중...")
    print("=" * 70)
    print("  ✓ Tools 폴더 EXE에 포함됨 (~136 MB)")
    print("  ✓ 프로그램_사용자_동의서.txt EXE에 포함됨")
    print("  ✓ Python 의존성 모두 포함됨 (~110 MB)")
    print()
    print("⚠️ 참고: 첫 실행 시 임시 폴더에 압축 해제 (~250 MB, 15~30초 소요)")
    return True

def rename_dist_folder():
    """EXE 파일을 배포 폴더로 이동"""
    print()
    print("=" * 70)
    print("📝 배포 폴더 구성 중...")
    print("=" * 70)
    
    exe_path = Path("dist") / f"{EXE_NAME}.exe"
    new_folder = Path("dist") / DIST_FOLDER_NAME
    
    if not exe_path.exists():
        print(f"❌ EXE 파일을 찾을 수 없습니다: {exe_path}")
        return False
    
    try:
        # 배포 폴더 생성
        if new_folder.exists():
            shutil.rmtree(new_folder)
        new_folder.mkdir(parents=True)
        
        # EXE 파일 이동
        shutil.move(str(exe_path), str(new_folder / f"{EXE_NAME}.exe"))
        print(f"  ✓ EXE 파일을 {DIST_FOLDER_NAME}/ 폴더로 이동")
        return True
    except Exception as e:
        print(f"  ✗ 폴더 구성 실패: {e}")
        return False

def show_result():
    """빌드 결과 표시"""
    print()
    print("=" * 70)
    print("📦 최종 빌드 결과")
    print("=" * 70)
    
    dist_path = Path("dist") / DIST_FOLDER_NAME
    exe_path = dist_path / f"{EXE_NAME}.exe"
    
    if exe_path.exists():
        print(f"\n📁 빌드 결과 위치: {dist_path.absolute()}")
        print("\n생성된 파일:")
        
        size = exe_path.stat().st_size / (1024 * 1024)  # MB
        print(f"  ✓ {EXE_NAME}.exe ({size:.2f} MB)")
        print(f"    → Tools 폴더 포함 (~136 MB)")
        print(f"    → Python 의존성 포함 (~110 MB)")
        print(f"    → 프로그램_사용자_동의서.txt 포함")
        
        print("\n" + "=" * 70)
        print("📌 다음 단계:")
        print("=" * 70)
        print("1. 빌드된 프로그램 테스트:")
        print(f"   cd \"{dist_path}\"")
        print(f"   .\\\"{EXE_NAME}.exe\"")
        print()
        print("   ⚠️ 첫 실행 시 15~30초 대기 (압축 해제)")
        print()
        print("2. 배포:")
        print(f"   → 이 EXE 파일 하나만 배포하면 됩니다!")
        print(f"   → Python 설치 불필요, 별도 파일 없이 실행 가능")
        print()
        print("3. GitHub Release 생성:")
        print("   - https://github.com/ordinaryperson0602/global-rom-patcher/releases")
        print("   - Releases → Create a new release")
        print(f"   - Tag: {VERSION}")
        print(f"   - {EXE_NAME}.exe 파일 업로드")
        print()
    else:
        print("\n❌ EXE 파일을 찾을 수 없습니다.")
        print("빌드가 실패했을 수 있습니다.")

def main():
    """메인 실행 함수"""
    print_banner()
    check_requirements()
    clean_build()
    
    # 1. PyInstaller 빌드
    if not build_exe():
        print("\n❌ 빌드 실패")
        input("\n스크립트를 닫으려면 Enter를 누르세요...")
        sys.exit(1)
    
    # 2. 필수 파일 복사
    if not copy_required_files():
        print("\n⚠️ 일부 파일 복사 실패")
    
    # 3. 폴더 이름 변경 (버전 추가)
    if not rename_dist_folder():
        print("\n❌ 폴더 이름 변경 실패")
        input("\n스크립트를 닫으려면 Enter를 누르세요...")
        sys.exit(1)
    
    # 4. 결과 표시
    show_result()
    
    # 성공 시에도 Enter 대기
    print()
    input("스크립트를 닫으려면 Enter를 누르세요...")

if __name__ == "__main__":
    main()

