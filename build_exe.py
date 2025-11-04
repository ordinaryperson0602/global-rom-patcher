"""
ROM Tool - EXE 빌드 자동화 스크립트

이 스크립트는 PyInstaller를 사용하여 Python 소스 코드를 Windows EXE 파일로 변환합니다.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

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
    
    # 필수 파일 존재 확인
    print("📋 빌드 전 파일 확인:")
    agreement_file = "프로그램_사용자_동의서.txt"
    tools_folder = "Tools"
    icon_file = "icon.ico"
    
    if os.path.exists(agreement_file):
        print(f"  ✓ {agreement_file} 발견")
    else:
        print(f"  ✗ {agreement_file} 없음")
    
    if os.path.exists(tools_folder):
        print(f"  ✓ {tools_folder}/ 발견")
    else:
        print(f"  ✗ {tools_folder}/ 없음")
    
    if os.path.exists(icon_file):
        print(f"  ✓ {icon_file} 발견")
    else:
        print(f"  ✗ {icon_file} 없음")
    
    print()
    
    # PyInstaller 명령어 구성
    command = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",  # 폴더 구조로 패키징 (빠른 실행)
        "--console",
        "--name", EXE_NAME,
        "--icon", "icon.ico",  # 아이콘 파일 지정
        
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

def copy_required_files():
    """필수 파일 및 폴더를 dist 폴더로 복사 및 _internal 폴더 숨김 처리"""
    print()
    print("=" * 70)
    print("📦 필수 파일 복사 중...")
    print("=" * 70)
    
    dist_path = Path("dist") / EXE_NAME
    
    if not dist_path.exists():
        print(f"❌ dist 폴더를 찾을 수 없습니다: {dist_path}")
        return False
    
    # 복사할 파일 및 폴더 목록
    items_to_copy = [
        ("프로그램_사용자_동의서.txt", "file"),
        ("Tools", "folder")
    ]
    
    success = True
    for item_name, item_type in items_to_copy:
        src = Path(item_name)
        dst = dist_path / item_name
        
        if not src.exists():
            print(f"  ✗ {item_name} 소스 파일 없음")
            success = False
            continue
        
        try:
            if item_type == "file":
                shutil.copy2(src, dst)
                print(f"  ✓ {item_name} 복사 완료")
            elif item_type == "folder":
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                print(f"  ✓ {item_name}/ 복사 완료")
        except Exception as e:
            print(f"  ✗ {item_name} 복사 실패: {e}")
            success = False
    
    # _internal 폴더 숨김 처리
    internal_folder = dist_path / "_internal"
    if internal_folder.exists():
        try:
            subprocess.run(['attrib', '+h', str(internal_folder)], check=True, capture_output=True)
            print(f"  ✓ _internal 폴더 숨김 처리 완료")
        except Exception as e:
            print(f"  ⚠️ _internal 폴더 숨김 처리 실패: {e}")
    
    return success

def rename_dist_folder():
    """dist 폴더 이름을 최종 배포 폴더 이름으로 변경"""
    print()
    print("=" * 70)
    print("📝 폴더 이름 변경 중...")
    print("=" * 70)
    
    old_path = Path("dist") / EXE_NAME
    new_path = Path("dist") / DIST_FOLDER_NAME
    
    if not old_path.exists():
        print(f"❌ 폴더를 찾을 수 없습니다: {old_path}")
        return False
    
    try:
        # 기존 폴더가 있으면 삭제
        if new_path.exists():
            shutil.rmtree(new_path)
        
        # 폴더 이름 변경
        old_path.rename(new_path)
        print(f"  ✓ {EXE_NAME} → {DIST_FOLDER_NAME}")
        return True
    except Exception as e:
        print(f"  ✗ 폴더 이름 변경 실패: {e}")
        return False

def show_result():
    """빌드 결과 표시 및 _internal 폴더 숨김 처리"""
    print()
    print("=" * 70)
    print("📦 최종 빌드 결과")
    print("=" * 70)
    
    dist_path = Path("dist") / DIST_FOLDER_NAME
    
    if dist_path.exists():
        print(f"\n📁 빌드 결과 위치: {dist_path.absolute()}")
        print("\n포함된 파일:")
        
        # 주요 파일 목록
        main_files = [
            f"{EXE_NAME}.exe",
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
        folders = ["Tools", "_internal"]
        for folder in folders:
            folder_path = dist_path / folder
            if folder_path.exists():
                if folder == "_internal":
                    print(f"  ✓ {folder}/ (숨김 처리됨)")
                else:
                    print(f"  ✓ {folder}/")
            else:
                print(f"  ✗ {folder}/ (없음)")
        
        print("\n" + "=" * 70)
        print("📌 다음 단계:")
        print("=" * 70)
        print("1. 빌드된 프로그램 테스트:")
        print(f"   cd \"{dist_path}\"")
        print(f"   .\\\"{EXE_NAME}.exe\"")
        print()
        print("2. 배포용 압축 파일 생성:")
        print("   cd ..\\.. (프로젝트 루트로)")
        print(f"   Compress-Archive -Path 'dist\\{DIST_FOLDER_NAME}\\*' "
              f"-DestinationPath '{DIST_FOLDER_NAME}_{VERSION}.zip' -Force")
        print()
        print("3. GitHub Release 생성:")
        print("   - https://github.com/ordinaryperson0602/global-rom-patcher/releases")
        print("   - Releases → Create a new release")
        print(f"   - Tag: {VERSION}")
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

