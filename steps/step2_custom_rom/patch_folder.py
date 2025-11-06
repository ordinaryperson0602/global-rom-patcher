"""패치 폴더 생성 관련 함수들"""
import os
import shutil
import traceback
from pathlib import Path
from typing import Optional

from src.config import Colors
from src.config import ROM_TOOLS_DIR
from src.context import CopyProgressTracker
from src.logger import log_error
from utils.file_operations import get_total_files, remove_readonly_and_delete, copy_with_progress


def detect_rom_structure(rom_path: Path) -> str:
    """
    롬 구조 타입 감지
    
    Args:
        rom_path: 실제 image 폴더가 있는 경로
    
    Returns:
        'global': 글로벌롬 구조 (툴이 루트에)
        'china': 내수롬 구조 (툴이 tool/ 폴더에)
        'unknown': 알 수 없음
    """
    rom_path = Path(rom_path)
    
    # 1. tool/ 폴더 존재 확인
    tool_folder = rom_path / "tool"
    if tool_folder.exists() and tool_folder.is_dir():
        # fh_loader.exe가 tool/ 안에 있으면 내수롬 구조
        if (tool_folder / "fh_loader.exe").exists():
            return 'china'
    
    # 2. fh_loader.exe가 루트에 있으면 글로벌 구조
    if (rom_path / "fh_loader.exe").exists():
        return 'global'
    
    return 'unknown'


def convert_china_to_global_structure(rom_path: Path) -> bool:
    """
    내수롬 구조를 글로벌 구조로 변환
    
    작업:
    1. image/ 폴더와 스크립트 생성 파일만 보존
    2. 나머지 모든 파일/폴더 삭제
    3. Tools/RomTools의 표준 툴 복사
    
    Args:
        rom_path: 변환할 롬 경로 (실제 image가 있는 경로)
    
    Returns:
        성공 시 True
    """
    rom_path = Path(rom_path)
    
    # ROM_TOOLS_DIR 확인
    if not ROM_TOOLS_DIR.exists():
        print(f"{Colors.FAIL}[오류] Tools/RomTools 폴더를 찾을 수 없습니다!{Colors.ENDC}")
        print(f"  경로: {ROM_TOOLS_DIR}")
        return False
    
    print(f"\n{Colors.OKCYAN}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}[구조 변환] 내수롬 → 글로벌 (RSA 호환){Colors.ENDC}")
    print(f"{Colors.OKCYAN}{'='*60}{Colors.ENDC}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 1: 보존할 항목 확인
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    preserve_items = set()
    
    # 1-1. image/ 폴더 (필수)
    image_folder = rom_path / "image"
    if image_folder.exists():
        preserve_items.add("image")
    
    # 1-2. 스크립트가 생성한 파일들
    for file in rom_path.glob("CustomRomFile_Info_*.txt"):
        preserve_items.add(file.name)
    
    for file in rom_path.glob("RomFile_Info_*.txt"):
        preserve_items.add(file.name)
    
    # 1-3. 백업 파일들 (*.original, *.patched)
    for pattern in ["*.original", "*.patched"]:
        for file in rom_path.glob(pattern):
            preserve_items.add(file.name)
    
    print(f"\n[1/3] 보존할 항목: {len(preserve_items)}개")
    for item in sorted(preserve_items):
        print(f"  ✓ {item}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 2: 나머지 모두 삭제
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n[2/3] 불필요한 파일/폴더 삭제 중...")
    deleted_count = 0
    
    for item in rom_path.iterdir():
        if item.name not in preserve_items:
            try:
                if item.is_dir():
                    remove_readonly_and_delete(item)
                    deleted_count += 1
                else:
                    item.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"  {Colors.WARNING}⚠️  {item.name} 삭제 실패: {e}{Colors.ENDC}")
                log_error(f"구조 변환 중 삭제 실패: {item}", exception=e, context="convert_structure")
    
    print(f"  {Colors.OKGREEN}✓ {deleted_count}개 항목 삭제 완료{Colors.ENDC}")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 3: 표준 롬 툴 복사
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    print(f"\n[3/3] 표준 롬 툴 복사 중...")
    print(f"  출처: Tools/RomTools/")
    
    copied_count = 0
    for item in ROM_TOOLS_DIR.iterdir():
        target = rom_path / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, target)
                copied_count += 1
            else:
                shutil.copy2(item, target)
                copied_count += 1
        except Exception as e:
            print(f"  {Colors.WARNING}⚠️  {item.name} 복사 실패: {e}{Colors.ENDC}")
            log_error(f"구조 변환 중 복사 실패: {item}", exception=e, context="convert_structure")
    
    print(f"  {Colors.OKGREEN}✓ {copied_count}개 항목 복사 완료{Colors.ENDC}")
    
    print(f"\n{Colors.OKGREEN}{'='*60}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}✅ 구조 변환 완료! (글로벌 구조, RSA 호환){Colors.ENDC}")
    print(f"{Colors.OKGREEN}{'='*60}{Colors.ENDC}\n")
    
    return True


def create_patch_folder(rom_path: str, selected_path: str, is_nested: bool) -> Optional[str]:
    """
    패치용 롬파일 폴더 생성 (원본은 유지)
    
    Args:
        rom_path: 실제 image 폴더가 있는 경로
        selected_path: 사용자가 선택한 원본 경로
        is_nested: 중첩 구조 여부
    
    Returns:
        패치용 경로 (_PATCH)
    """
    print(f"\n{Colors.BOLD}[준비] 패치용 롬파일 복사 중...{Colors.ENDC}")
    
    # _PATCH 경로는 선택한 경로 기준으로 생성
    patch_path = f"{selected_path}_PATCH"
    
    # 기존 _PATCH 폴더 존재 확인
    if os.path.exists(patch_path):
        print(f"\n{Colors.WARNING}{'='*60}{Colors.ENDC}")
        print(f"{Colors.WARNING}⚠️  기존 패치 흔적이 발견되었습니다!{Colors.ENDC}")
        print(f"{Colors.WARNING}{'='*60}{Colors.ENDC}")
        print(f"  위치: {patch_path}")
        print(f"\n{Colors.OKCYAN}기존 패치 폴더를 삭제하고 새로 생성하여 계속 진행하시겠습니까?{Colors.ENDC}")
        
        while True:
            response = input(f"{Colors.WARNING}삭제 후 재생성 (y/n): {Colors.ENDC}").strip().lower()
            if response == 'y':
                print(f"\n{Colors.WARNING}기존 패치 폴더를 강제 삭제합니다...{Colors.ENDC}")
                try:
                    # 읽기 전용 파일도 강제로 삭제
                    remove_readonly_and_delete(Path(patch_path))
                    print(f"{Colors.OKGREEN}✓ 삭제 완료{Colors.ENDC}")
                except Exception as e:
                    print(f"{Colors.FAIL}✗ 패치 폴더 삭제 실패: {e}{Colors.ENDC}")
                    log_error(f"패치 폴더 강제 삭제 실패: {e}", exception=e, context="create_patch_folder")
                    return None
                break
            elif response == 'n':
                print(f"\n{Colors.OKCYAN}작업을 취소합니다.{Colors.ENDC}")
                return None
            else:
                print(f"{Colors.FAIL}'y' 또는 'n'을 입력하세요.{Colors.ENDC}")
    
    # 패치용 폴더 생성
    print(f"\n{Colors.BOLD}[복사 시작]{Colors.ENDC}")
    if is_nested:
        print(f"  원본: {rom_path} (중첩 구조 - 내부 폴더만 복사)")
        print(f"  패치용: {patch_path}")
        print(f"  {Colors.OKCYAN}중첩된 내부 폴더만 복사하여 정상 구조로 생성합니다.{Colors.ENDC}")
    else:
        print(f"  원본: {rom_path} (유지됨)")
        print(f"  패치용: {patch_path}")
    
    try:
        print(f"\n{Colors.BOLD}[정보] 복사할 총 파일 개수를 세는 중...{Colors.ENDC}")
        total_files = get_total_files(rom_path)
        print(f"  총 {total_files}개의 파일을 복사합니다.\n")
        
        # 복사 진행률 추적기 초기화
        copy_tracker = CopyProgressTracker()
        copy_tracker.set_total(total_files)
        
        # copy_with_progress wrapper (copytree는 (src, dst) 2개 인자만 받음)
        def copy_func(src, dst) -> None:
            """파일 복사 wrapper"""
            copy_with_progress(src, dst, copy_tracker)
        
        # 중첩 구조: rom_path (내부 폴더)만 복사
        # 정상 구조: rom_path 전체 복사
        shutil.copytree(rom_path, patch_path, copy_function=copy_func)
        print()  # 줄바꿈
        
        print(f"\n{Colors.OKGREEN}✓ 패치용 폴더 생성 완료!{Colors.ENDC}")
        if is_nested:
            print(f"  {Colors.OKCYAN}중첩 구조가 정상 구조로 변환되었습니다.{Colors.ENDC}")
            print(f"  {patch_path}/image (바로 접근 가능)")
        else:
            print(f"  원본 폴더는 그대로 유지됩니다.")
        
        copy_tracker.reset()
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 구조 감지 및 자동 변환 (내수롬 → 글로벌)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        structure_type = detect_rom_structure(Path(patch_path))
        
        if structure_type == 'china':
            print(f"\n{Colors.WARNING}{'='*60}{Colors.ENDC}")
            print(f"{Colors.WARNING}⚠️  내수롬 구조 감지 (RSA 비호환){Colors.ENDC}")
            print(f"{Colors.WARNING}{'='*60}{Colors.ENDC}")
            print(f"\n{Colors.BOLD}글로벌 구조로 자동 변환합니다:{Colors.ENDC}")
            print(f"  • image/ 폴더 → 보존")
            print(f"  • tool/ 폴더 → 삭제 (표준 툴로 교체)")
            print(f"  • 기타 파일 → 삭제")
            print(f"  • Tools/RomTools/ → 복사")
            print(f"\n{Colors.OKCYAN}이 작업은 RSA 호환성을 위해 필수입니다.{Colors.ENDC}")
            
            if not convert_china_to_global_structure(Path(patch_path)):
                print(f"{Colors.FAIL}✗ 구조 변환 실패{Colors.ENDC}")
                return None
        
        elif structure_type == 'global':
            print(f"\n{Colors.OKGREEN}✓ 글로벌 구조 감지 (RSA 호환){Colors.ENDC}")
        
        elif structure_type == 'unknown':
            print(f"\n{Colors.WARNING}⚠️  알 수 없는 롬 구조입니다.{Colors.ENDC}")
            print(f"  fh_loader.exe를 찾을 수 없습니다.")
        
        return patch_path
    
    except Exception as e:
        print(f"\n{Colors.FAIL}✗ 패치용 폴더 생성 실패: {e}{Colors.ENDC}")
        log_error(f"패치용 폴더 생성 실패: {e}", exception=e, context="STEP 2-Custom - 패치 폴더 생성")
        return None

