"""STEP 2: 롬파일 분석 및 백업 - 실제 코드"""
# 표준 라이브러리
import os
import re
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

# 로컬 모듈
from config.colors import Colors
from config.paths import AVBTOOL_PY, ROM_DIR_STR
from config.constants import UIConstants, FolderConstants, FileConstants, ValidationConstants
from config.messages import ErrorMessages, InfoMessages, TitleMessages
from core.progress import init_step_progress, update_sub_task, global_print_progress, global_end_progress
from core.context import CopyProgressTracker
from core.logger import log_error
from utils.ui import show_popup, show_popup_yesno
from utils.command import run_command
from utils.file_operations import remove_readonly_and_delete, get_total_files, copy_with_progress
from utils.region_check import check_region_patterns, check_region_in_image

# 모듈 레벨 복사 진행률 추적기
_copy_tracker = CopyProgressTracker()


# ============================================================================
# Helper Functions for run_step_2 (리팩토링)
# ============================================================================

def _check_rom_folders() -> Tuple[Optional[str], Optional[str]]:
    """롬 폴더 확인 및 _RAW 백업 처리
    
    Returns:
        (rom_path, rom_name) 또는 (None, None) if error
    """
    try:
        items = os.listdir(ROM_DIR_STR)
    except FileNotFoundError:
        show_popup(
            TitleMessages.ERROR,
            f"경로를 찾을 수 없습니다: {ROM_DIR_STR}\n폴더가 존재하는지 확인하십시오.",
            exit_on_close=False, icon=UIConstants.ICON_ERROR
        )
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None, None
    except Exception as e:
        show_popup(
            TitleMessages.ERROR,
            f"폴더 접근 중 오류 발생: {ROM_DIR_STR}\n{e}",
            exit_on_close=False, icon=UIConstants.ICON_ERROR
        )
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None, None
    
    rom_folders = [item for item in items if os.path.isdir(os.path.join(ROM_DIR_STR, item))]
    
    # _RAW 백업 상태 확인
    print(f"\n[정보] 기존 롬파일 백업(_RAW) 상태 확인 중...")
    raw_pairs_found = []
    for folder_name in list(rom_folders):
        if folder_name.endswith(FolderConstants.RAW_SUFFIX):
            continue
        raw_name = f"{folder_name}{FolderConstants.RAW_SUFFIX}"
        if raw_name in rom_folders:
            raw_pairs_found.append((folder_name, raw_name))
    
    if len(raw_pairs_found) > 1:
        show_popup(
            TitleMessages.ERROR,
            f"{ROM_DIR_STR}에 _RAW 백업 쌍이 2개 이상 존재합니다.\n1개의 쌍만 남기거나, _RAW 폴더를 모두 정리해주세요.",
            exit_on_close=False, icon=UIConstants.ICON_ERROR
        )
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None, None
    
    # _RAW 백업이 있으면 롤백 처리
    if len(raw_pairs_found) == 1:
        if not _handle_raw_backup_rollback(raw_pairs_found[0]):
            return None, None
    
    # 최종 롬 폴더 선택
    rom_folders_no_raw = [f for f in rom_folders if not f.endswith(FolderConstants.RAW_SUFFIX)]
    
    if len(rom_folders_no_raw) == 0:
        # _RAW만 있는 경우 자동 복원
        raw_only_folders = [f for f in rom_folders if f.endswith(FolderConstants.RAW_SUFFIX)]
        
        if len(raw_only_folders) == 1:
            from core.logger import info
            
            raw_folder_name = raw_only_folders[0]
            original_name = raw_folder_name[:-len(FolderConstants.RAW_SUFFIX)]  # _RAW 제거
            raw_path = os.path.join(ROM_DIR_STR, raw_folder_name)
            original_path = os.path.join(ROM_DIR_STR, original_name)
            
            info("_RAW만 발견됨, 자동 복원 시작", raw_folder=raw_folder_name, target=original_name)
            
            print(f"\n{Colors.WARNING}[정보] 원본 롬 폴더가 없고 _RAW 백업만 발견되었습니다.{Colors.ENDC}")
            print(f"  - 백업 폴더: {raw_folder_name}")
            print(f"  - 자동으로 원본으로 복원합니다: {original_name}\n")
            
            try:
                os.rename(raw_path, original_path)
                info("_RAW 복원 완료", restored_folder=original_name)
                print(f"{Colors.OKGREEN}✓ 복원 완료: {original_name}{Colors.ENDC}")
                
                # 복원된 폴더를 사용
                rom_name = original_name
                rom_path = original_path
                return rom_path, rom_name
            except Exception as e:
                error_msg = f"_RAW 폴더 복원 실패: {e}"
                print(f"{Colors.FAIL}✗ {error_msg}{Colors.ENDC}")
                from core.logger import log_error
                log_error(error_msg, exception=e, context="STEP 2 - _RAW 복원")
                show_popup("NG", error_msg, exit_on_close=False, icon=UIConstants.ICON_ERROR)
                print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
                input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
                return None, None
        else:
            # _RAW도 없거나 2개 이상
            show_popup("NG", f"{ROM_DIR_STR}에 롬파일 폴더가 없습니다.",
                      exit_on_close=False, icon=UIConstants.ICON_ERROR)
            print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
            input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
            return None, None
    elif len(rom_folders_no_raw) > 1:
        show_popup("NG", f"{ROM_DIR_STR}에 롬파일이 2개 이상 존재합니다. \n하나만 남기고 다시 시도하십시오.",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None, None
    
    rom_name = rom_folders_no_raw[0]
    rom_path = os.path.join(ROM_DIR_STR, rom_name)
    
    return rom_path, rom_name


def _handle_raw_backup_rollback(raw_pair: Tuple[str, str]) -> bool:
    """_RAW 백업이 있을 때 롤백 처리
    
    Args:
        raw_pair: (rom_name, raw_name) 튜플
        
    Returns:
        True if success or skipped, False if error
    """
    rom_name_to_check, raw_name_to_check = raw_pair
    rom_path_to_check = os.path.join(ROM_DIR_STR, rom_name_to_check)
    raw_path_to_check = os.path.join(ROM_DIR_STR, raw_name_to_check)
    
    print(f"[경고] 원본 롬폴더({rom_name_to_check})와 백업 폴더({raw_name_to_check})가 모두 존재합니다.")
    
    user_choice = show_popup_yesno(
        TitleMessages.CONFIRM,
        f"이전 패치 흔적이 발견되었습니다.\n\n"
        f"이전 패치 폴더 {rom_name_to_check}를 삭제한 뒤,\n"
        f"원본 백업 폴더 {raw_name_to_check}를 복구하여 계속 패치를 진행하시겠습니까?"
    )
    
    if user_choice == 6:  # YES
        print("[정보] 사용자가 'YES'를 선택했습니다. 롤백을 진행합니다.")
        
        max_retries = 3
        for retry_count in range(max_retries):
            try:
                if retry_count > 0:
                    print(f"\n{Colors.WARNING}[재시도 {retry_count}/{max_retries}]{Colors.ENDC}")
                    print(f"{Colors.OKCYAN}Windows 탐색기에서 해당 폴더를 닫고 Enter를 누르십시오...{Colors.ENDC}")
                    input()
                
                print(f"  - 삭제 시도: {rom_path_to_check}")
                remove_readonly_and_delete(Path(rom_path_to_check))
                print(f"  - 이름 변경: {raw_name_to_check} → {rom_name_to_check}")
                os.rename(raw_path_to_check, rom_path_to_check)
                print(f"{Colors.OKGREEN}[성공] 롤백이 완료되었습니다!{Colors.ENDC}")
                return True
            except Exception as e:
                if retry_count < max_retries - 1:
                    print(f"{Colors.WARNING}폴더가 사용 중일 수 있습니다. 다음을 시도하십시오:{Colors.ENDC}")
                    print(f"  1. Windows 탐색기에서 '{rom_name_to_check}' 폴더 닫기")
                    print(f"  2. 작업 관리자 → 'Windows 탐색기' 다시 시작")
                else:
                    print(f"\n{Colors.FAIL}[오류] {max_retries}번 재시도 후에도 실패했습니다.{Colors.ENDC}")
                    show_popup("NG - 롤백 실패",
                              f"롤백 작업 중 오류가 발생했습니다.\n{e}\n\n"
                              f"해결 방법:\n"
                              f"1. Windows 탐색기 재시작\n"
                              f"2. '{rom_name_to_check}' 폴더 수동 삭제\n"
                              f"3. '{raw_name_to_check}' 이름을 '{rom_name_to_check}'로 변경\n"
                              f"4. 프로그램 재실행",
                              exit_on_close=False, icon=UIConstants.ICON_ERROR)
                    print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
                    input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
                    return False
    else:  # NO
        print("[정보] 사용자가 'NO'를 선택했습니다.")
        show_popup("작업 중단", "사용자가 롤백을 취소하고 작업을 중단했습니다.",
                  exit_on_close=False, icon=UIConstants.ICON_INFO)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return False


def _find_actual_rom_path(rom_path: str) -> Optional[str]:
    """중첩 폴더 구조 확인 (최대 3단계)
    
    Returns:
        실제 롬 경로 또는 None if error
    """
    max_depth = 3
    current_path = rom_path
    
    for depth in range(max_depth):
        image_path = os.path.join(current_path, FolderConstants.IMAGE_DIR)
        if os.path.exists(image_path) and os.path.isdir(image_path):
            if depth > 0:
                print(f"{Colors.OKGREEN}  ✓ {depth}단계 중첩 구조 발견: image 폴더 위치 확인{Colors.ENDC}")
            return current_path
        else:
            try:
                subdirs = [d for d in os.listdir(current_path) 
                          if os.path.isdir(os.path.join(current_path, d))]
                
                if len(subdirs) == 1:
                    nested_folder = subdirs[0]
                    current_path = os.path.join(current_path, nested_folder)
                    print(f"{Colors.OKCYAN}  → {depth + 1}단계 하위 폴더: {nested_folder}{Colors.ENDC}")
                elif len(subdirs) == 0:
                    show_popup("NG", f"image 폴더를 찾을 수 없고, 하위 폴더도 없습니다.\n경로: {current_path}",
                              exit_on_close=False, icon=UIConstants.ICON_ERROR)
                    print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
                    input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
                    return None
                else:
                    show_popup("NG", f"image 폴더가 없고, 하위 폴더가 {len(subdirs)}개 있습니다.\n구조를 확인할 수 없습니다.\n경로: {current_path}",
                              exit_on_close=False, icon=UIConstants.ICON_ERROR)
                    print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
                    input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
                    return None
            except Exception as e:
                show_popup("NG", f"폴더 구조 분석 실패:\n{e}",
                          exit_on_close=False, icon=UIConstants.ICON_ERROR)
                print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
                input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
                return None
    
    # 최대 깊이까지 검사했는데도 image 폴더를 못 찾음
    show_popup("NG", f"최대 {max_depth}단계까지 검사했으나 image 폴더를 찾을 수 없습니다.\n경로: {rom_path}",
              exit_on_close=False, icon=UIConstants.ICON_ERROR)
    print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
    input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
    return None


def _verify_model_compatibility(rom_name: str, target_model: str) -> bool:
    """롬 이름에서 모델 번호 확인 (1차 검증)
    
    Returns:
        True if compatible, False if error
    """
    print(f"\n--- 검증 1: 롬파일 이름으로 모델 확인 (1차 검증) ---")
    print(f"  - 기기 모델: {target_model}")
    print(f"  - 롬 폴더명: {rom_name}")
    
    # 모델 체크 (Full Match)
    if target_model in rom_name:
        print(f"{Colors.OKGREEN}  ✓ 롬파일 이름에 기기 모델({target_model})이 정확하게 포함되어 있습니다. [OK]{Colors.ENDC}")
        return True
    
    # 모델 체크 (Partial Match for China ROM)
    if target_model.endswith("FU"):
        partial_model = target_model[:-2]
        if partial_model in rom_name:
            print(f"{Colors.WARNING}  ! 롬파일 이름에 '{partial_model}'이 포함되어 있습니다. (중국 롬 가능성){Colors.ENDC}")
            print(f"{Colors.WARNING}  ! 주의: '{target_model}' 대신 '{partial_model}' 사용 중{Colors.ENDC}")
            return True
    
    # 모델 불일치
    show_popup("NG - 모델 불일치",
              f"롬파일 이름이 기기 모델과 일치하지 않습니다!\n\n"
              f"기기 모델: {target_model}\n"
              f"롬 폴더명: {rom_name}\n\n"
              f"올바른 롬파일을 준비해주세요.",
              exit_on_close=False, icon=UIConstants.ICON_ERROR)
    print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
    input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
    return False


def _analyze_vbmeta_prop(vbmeta_path: str, target_model: str) -> Optional[Tuple[str, str, str]]:
    """vbmeta.img에서 Prop 분석 (2차 모델 검증 포함)
    
    Returns:
        (model, rom_version, country_code) 또는 None if error
    """
    from core.logger import info, log_validation
    
    print(f"\n--- 검증 2: vbmeta Prop 분석 (2차 검증) ---")
    info("vbmeta Prop 분석 시작", vbmeta_path=vbmeta_path, target_model=target_model)
    
    if not os.path.exists(vbmeta_path):
        log_validation("vbmeta.img 존재 여부", False, f"파일 없음: {vbmeta_path}")
        show_popup("NG", f"vbmeta.img가 없습니다:\n{vbmeta_path}",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    log_validation("vbmeta.img 존재 여부", True, f"파일 크기: {os.path.getsize(vbmeta_path)} bytes")
    
    cmd = [sys.executable, str(AVBTOOL_PY), "info_image", "--image", vbmeta_path]
    success, stdout, stderr = run_command(cmd, check=False)
    
    if not success:
        show_popup("NG", f"vbmeta.img 분석 실패:\n{stderr}",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    # fingerprint 파싱
    fingerprint_lines = []
    for line in stdout.split('\n'):
        if 'Prop: com.android.build' in line and 'fingerprint' in line:
            # 형식: Prop: ... -> 'value'
            match = re.search(r"-> '(.+?)'", line)
            if match:
                fingerprint_lines.append(match.group(1))
    
    info(f"추출된 fingerprint 개수: {len(fingerprint_lines)}")
    if fingerprint_lines:
        info(f"첫 번째 fingerprint: {fingerprint_lines[0]}")
    
    if not fingerprint_lines:
        log_validation("fingerprint 파싱", False, "fingerprint를 찾을 수 없음")
        show_popup("NG", "vbmeta Prop에서 fingerprint를 찾을 수 없습니다.",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    # PRC 확인 (NG 조건)
    has_prc = any('PRC' in fp for fp in fingerprint_lines)
    info(f"PRC 검사 결과: {has_prc}", fingerprints=fingerprint_lines)
    
    if has_prc:
        log_validation("국가 코드 (PRC 확인)", False, "PRC 발견 - 중국 롬")
        show_popup("NG", "vbmeta Prop에서 'PRC'(중국 롬)가 발견되었습니다.\n글로벌 롬(ROW)을 사용해주세요.",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    log_validation("국가 코드 (PRC 확인)", True, "PRC 없음 - ROW 롬")
    
    # 정보 추출
    first_fp = fingerprint_lines[0]
    parts = first_fp.split('/')
    
    model = parts[1] if len(parts) > 1 else "Unknown"
    rom_version = parts[3].split(':')[0] if len(parts) > 3 else "Unknown"
    country_code = "ROW"  # PRC가 없으면 ROW
    
    info(f"추출된 정보", model=model, rom_version=rom_version, country_code=country_code)
    
    print(f"  - 모델: {model}")
    print(f"  - 롬 버전: {rom_version}")
    print(f"  - 국가 코드: {country_code}")
    
    # 2차 모델 검증
    model_match = (model == target_model)
    log_validation("모델 번호 일치 (vbmeta Prop)", model_match, 
                   f"기기: {target_model}, Prop: {model}")
    
    if not model_match:
        show_popup("NG - 모델 불일치 (vbmeta Prop)",
                  f"vbmeta Prop에서 추출한 모델이 기기 모델과 일치하지 않습니다!\n\n"
                  f"기기 모델: {target_model}\n"
                  f"Prop 모델: {model}\n\n"
                  f"올바른 롬파일을 사용해주세요.",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    print(f"{Colors.OKGREEN}  ✓ vbmeta Prop 모델이 기기 모델과 일치합니다. [OK]{Colors.ENDC}")
    info("vbmeta Prop 분석 완료", success=True)
    return model, rom_version, country_code


def _analyze_vendor_boot_hex(vendor_boot_path: str) -> Optional[str]:
    """vendor_boot.img에서 Hex 지역 코드 분석
    
    Returns:
        hex_region_code 또는 None if error
    """
    from core.logger import info, log_validation
    
    print(f"\n--- 검증 3: vendor_boot Hex 지역 코드 ---")
    info("vendor_boot Hex 분석 시작", vendor_boot_path=vendor_boot_path)
    
    if not os.path.exists(vendor_boot_path):
        log_validation("vendor_boot.img 존재 여부", False, f"파일 없음: {vendor_boot_path}")
        show_popup("NG", f"vendor_boot.img가 없습니다:\n{vendor_boot_path}",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    file_size = os.path.getsize(vendor_boot_path)
    log_validation("vendor_boot.img 존재 여부", True, f"파일 크기: {file_size} bytes")
    
    with open(vendor_boot_path, 'rb') as f:
        binary_data = f.read()
    
    info("바이너리 데이터 읽기 완료", size=len(binary_data))
    
    # 패턴 검사 (반환 순서: PRC, IPRC, ROW, IROW)
    found_prc, found_iprc, found_row, found_irow = check_region_patterns(binary_data)
    
    info(
        "Hex 패턴 검사 결과",
        found_prc=found_prc,
        found_iprc=found_iprc,
        found_row=found_row,
        found_irow=found_irow
    )
    
    # Mixed ROW+IROW 확인 (NG 조건)
    if found_row and found_irow:
        log_validation("vendor_boot Hex (혼합 패턴)", False, "ROW + IROW 혼재")
        show_popup("NG - vendor_boot 혼합 패턴",
                  "vendor_boot.img에 ROW와 IROW 패턴이 혼재되어 있습니다.\n비정상적인 롬 파일입니다.",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    # PRC 확인 (NG 조건)
    if found_prc or found_iprc:
        log_validation(
            "vendor_boot Hex (PRC 확인)",
            False,
            f"PRC={'발견' if found_prc else '없음'}, IPRC={'발견' if found_iprc else '없음'}"
        )
        show_popup(
            "NG",
            "vendor_boot에서 'PRC'(중국 롬)가 발견되었습니다.\n글로벌 롬(ROW)을 사용해주세요.",
            exit_on_close=False,
            icon=UIConstants.ICON_ERROR
        )
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    log_validation("vendor_boot Hex (PRC 확인)", True, "PRC 패턴 없음")
    
    # ROW 확인
    if found_row:
        hex_region_code = "ROW"
    elif found_irow:
        hex_region_code = "IROW"
    else:
        log_validation("vendor_boot Hex 지역 코드", False, "지역 코드 없음")
        show_popup("NG", "vendor_boot에서 지역 코드를 찾을 수 없습니다.",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    info(f"vendor_boot Hex 분석 완료", hex_region_code=hex_region_code, success=True)
    log_validation("vendor_boot Hex 지역 코드", True, f"감지된 코드: {hex_region_code}")
    
    print(f"  - Hex 지역 코드: {hex_region_code}")
    print(f"{Colors.OKGREEN}  ✓ vendor_boot Hex 패턴이 정상입니다. [OK]{Colors.ENDC}")
    return hex_region_code


def _extract_rollback_index(image_path: str, image_name: str) -> Optional[str]:
    """이미지에서 롤백 인덱스 추출
    
    Returns:
        rollback_index 또는 None if error
    """
    if not os.path.exists(image_path):
        show_popup("NG", f"{image_name}가 없습니다:\n{image_path}",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    cmd = [sys.executable, str(AVBTOOL_PY), "info_image", "--image", image_path]
    success, stdout, stderr = run_command(cmd, check=False)
    
    if not success:
        show_popup("NG", f"{image_name} 분석 실패:\n{stderr}",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    match = re.search(r"Rollback Index:\s+(\d+)", stdout)
    if not match:
        show_popup("NG", f"{image_name}에서 Rollback Index를 찾을 수 없습니다.",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None
    
    return match.group(1)


def _create_raw_backup(original_rom_path: str, raw_backup_path: str) -> bool:
    """_RAW 백업 폴더 생성
    
    Returns:
        True if success, False if error
    """
    print(f"\n[8단계] 원본 롬파일 백업 생성 중...")
    print(f"  원본: {original_rom_path}")
    print(f"  백업: {raw_backup_path}")
    
    try:
        total_files = get_total_files(original_rom_path)
        _copy_tracker.reset()
        _copy_tracker.set_total(total_files)
        
        def copy_func(src, dst) -> None:
            """파일 복사 wrapper"""
            copy_with_progress(src, dst, _copy_tracker)
        
        shutil.copytree(
            original_rom_path,
            raw_backup_path,
            copy_function=copy_func
        )
        
        print(f"\n{Colors.OKGREEN}원본 롬파일 백업 완료!{Colors.ENDC}")
        return True
        
    except Exception as e:
        show_popup("NG - 백업 실패", f"원본 롬파일 백업 중 오류가 발생했습니다:\n{e}",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return False


def save_rom_info_to_file(model: str, rom_version: str, hex_code: str, country_code: str,
                          vbmeta_system_rollback: str, boot_rollback: str, step1_output_dir: str) -> None:
    """롬파일 정보를 txt 파일로 저장"""
    print(f"\n[정보] 검증 결과를 .txt 파일로 저장합니다...")
    
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%H%M%S")
    output_filename = f"RomFile_Info_{model}_{date_str}_{time_str}.txt"
    
    if step1_output_dir and os.path.isdir(step1_output_dir):
        output_filepath = os.path.join(step1_output_dir, output_filename)
    else:
        output_filepath = output_filename
    
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    content = (
        f"=== 장치 분석 정보 ===\n"
        f"분석 시간: {timestamp}\n"
        f"{'='*20}\n"
        f"1. 모델 번호 (vbmeta Prop): {model}\n"
        f"2. 롬 버전 (vbmeta Prop): {rom_version}\n"
        f"3. 지역 코드 (vendor_boot Hex): {hex_code}\n"
        f"4. 국가 코드 (vbmeta Prop): {country_code}\n"
        f"5. vbmeta_system 롤백 인덱스: {vbmeta_system_rollback}\n"
        f"6. boot 롤백 인덱스: {boot_rollback}\n"
    )
    
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[성공] 검증 정보를 '{output_filepath}' 파일에 저장했습니다.")
    except Exception as e:
        error_msg = f"정보 파일 저장 중 오류 발생: {e}"
        print(f"[경고] {error_msg}")
        log_error(error_msg, exception=e, context="STEP 2 - ROM 정보 파일 저장")
# ============================================================================
# Main Function (리팩토링: 597줄 → 152줄)
# ============================================================================

def run_step_2(target_model_number: str, step1_output_dir: str) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
    """STEP 2 메인 로직 (리팩토링 버전)"""
    
    step2_total_steps = 8
    task_names = [
        "롬파일 경로 확인",
        "롬파일 이름 확인",
        "vbmeta Prop 확인",
        "vendor_boot Hex 확인",
        "vbmeta_system 롤백 확인",
        "boot 롤백 확인",
        "검증 정보 저장",
        "롬파일 백업"
    ]
    init_step_progress(2, step2_total_steps, task_names)
    
    print("="*50 + "\n롬파일 검증 프로그램(STEP 2)을 시작합니다.\n" + "="*50)
    
    # [작업 1] 롬 폴더 확인 및 _RAW 백업 처리
    update_sub_task(0, 'in_progress')
    global_print_progress(0, step2_total_steps, "STEP 2")
    print(f"\n[1단계] {ROM_DIR_STR} 경로의 롬파일 확인 중...")
    
    rom_path, rom_name = _check_rom_folders()
    if not rom_path:
        return None, None
    
    # 중첩 폴더 구조 확인
    print(f"\n[정보] 롬파일 폴더 구조 확인 중...")
    original_rom_path = rom_path  # 백업용 경로 저장
    actual_rom_path = _find_actual_rom_path(rom_path)
    if not actual_rom_path:
        return None, None
    rom_path = actual_rom_path
    
    # image 폴더 확인
    image_dir = os.path.join(rom_path, FolderConstants.IMAGE_DIR)
    if not os.path.exists(image_dir):
        show_popup("NG", f"{FolderConstants.IMAGE_DIR} 폴더가 없습니다:\n{rom_path}",
                  exit_on_close=False, icon=UIConstants.ICON_ERROR)
        print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다...{Colors.ENDC}")
        input("\nEnter 키를 누르면 메인 메뉴로 돌아갑니다...")
        return None, None
    
    print(f"{Colors.OKGREEN}[PASS] 롬파일 경로 확인 완료{Colors.ENDC}")
    update_sub_task(0, 'done')
    global_print_progress(1, step2_total_steps, "STEP 2")
    
    # [작업 2] 롬파일 이름으로 모델 확인 (1차 검증)
    update_sub_task(1, 'in_progress')
    global_print_progress(1, step2_total_steps, "STEP 2")
    
    if not _verify_model_compatibility(rom_name, target_model_number):
        return None, None
    
    print(f"{Colors.OKGREEN}[PASS] 롬파일 이름 검증 완료{Colors.ENDC}")
    update_sub_task(1, 'done')
    global_print_progress(2, step2_total_steps, "STEP 2")
    
    # [작업 3] vbmeta Prop 분석 (2차 모델 검증)
    update_sub_task(2, 'in_progress')
    global_print_progress(2, step2_total_steps, "STEP 2")
    
    vbmeta_path = os.path.join(image_dir, "vbmeta.img")
    vbmeta_result = _analyze_vbmeta_prop(vbmeta_path, target_model_number)
    if not vbmeta_result:
        return None, None
    
    model, rom_version, country_code = vbmeta_result
    print(f"{Colors.OKGREEN}[PASS] vbmeta Prop 검증 완료{Colors.ENDC}")
    update_sub_task(2, 'done')
    global_print_progress(3, step2_total_steps, "STEP 2")
    
    # [작업 4] vendor_boot Hex 지역 코드 분석
    update_sub_task(3, 'in_progress')
    global_print_progress(3, step2_total_steps, "STEP 2")
    
    vendor_boot_path = os.path.join(image_dir, "vendor_boot.img")
    hex_region_code = _analyze_vendor_boot_hex(vendor_boot_path)
    if not hex_region_code:
        return None, None
    
    print(f"{Colors.OKGREEN}[PASS] vendor_boot Hex 검증 완료{Colors.ENDC}")
    update_sub_task(3, 'done')
    global_print_progress(4, step2_total_steps, "STEP 2")
    
    # [작업 5] vbmeta_system 롤백 인덱스 추출
    update_sub_task(4, 'in_progress')
    global_print_progress(4, step2_total_steps, "STEP 2")
    print(f"\n--- 검증 4: vbmeta_system 롤백 인덱스 ---")
    
    vbmeta_system_path = os.path.join(image_dir, "vbmeta_system.img")
    vbmeta_system_rollback = _extract_rollback_index(vbmeta_system_path, "vbmeta_system.img")
    if not vbmeta_system_rollback:
        return None, None
    
    print(f"  - vbmeta_system 롤백 인덱스: {vbmeta_system_rollback}")
    print(f"{Colors.OKGREEN}  ✓ vbmeta_system 롤백 인덱스 추출 완료{Colors.ENDC}")
    update_sub_task(4, 'done')
    global_print_progress(5, step2_total_steps, "STEP 2")
    
    # [작업 6] boot 롤백 인덱스 추출
    update_sub_task(5, 'in_progress')
    global_print_progress(5, step2_total_steps, "STEP 2")
    print(f"\n--- 검증 5: boot 롤백 인덱스 ---")
    
    boot_path = os.path.join(image_dir, "boot.img")
    boot_rollback = _extract_rollback_index(boot_path, "boot.img")
    if not boot_rollback:
        return None, None
    
    print(f"  - boot 롤백 인덱스: {boot_rollback}")
    print(f"{Colors.OKGREEN}  ✓ boot 롤백 인덱스 추출 완료{Colors.ENDC}")
    update_sub_task(5, 'done')
    global_print_progress(6, step2_total_steps, "STEP 2")
    
    # [작업 7] 검증 정보 저장
    update_sub_task(6, 'in_progress')
    global_print_progress(6, step2_total_steps, "STEP 2")
    
    save_rom_info_to_file(
        model, rom_version, hex_region_code, country_code,
        vbmeta_system_rollback, boot_rollback, step1_output_dir
    )
    
    update_sub_task(6, 'done')
    global_print_progress(7, step2_total_steps, "STEP 2")
    
    # [작업 8] _RAW 백업 생성
    update_sub_task(7, 'in_progress')
    global_print_progress(7, step2_total_steps, "STEP 2")
    
    raw_backup_path = original_rom_path + FolderConstants.RAW_SUFFIX
    if not _create_raw_backup(original_rom_path, raw_backup_path):
        return None, None
    
    update_sub_task(7, 'done')
    global_print_progress(8, step2_total_steps, "STEP 2")
    
    print("\n" + "="*50 + "\n프로그램(STEP 2)을 완료했습니다.\n" + "="*50)
    global_end_progress()
    
    rom_rollback_indices = {
        'boot': boot_rollback,
        'vbmeta_system': vbmeta_system_rollback
    }
    
    return rom_path, rom_rollback_indices
