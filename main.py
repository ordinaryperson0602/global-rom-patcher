#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
통합 롬파일 패치 도구 - 완전 리팩토링 버전
STEP 1: 기기 정보 추출
STEP 2: 롬파일 분석 및 백업
STEP 3: 롬파일 패치 (ARB, KSU)
STEP 4: 패치 검증

추가 유틸리티:
- 기기 정보 백업
- 국가코드 변경 (CN→KR)
- OTA 펌웨어 업데이트
"""
# 표준 라이브러리
import ctypes
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

# 로컬 모듈
from src.config import Colors
from src.config import (
    CURRENT_DIR, ADB_EXE, EDL_NG_EXE, AVBTOOL_PY, LOADER_FILES, KNOWN_SIGNING_KEYS,
    TEMP_WORK_DIR, VERIFY_TEMP_DIR, STEP_DATA_FILE
)
from src.config import UIConstants, APP_VERSION, APP_NAME, APP_AUTHOR, APP_LAST_UPDATED
from src.config import ErrorMessages, TitleMessages
from src.logger import init_logger, close_logger
from src.data_manager import save_step_data, load_step_data, check_step_prerequisites
from utils.ui import show_popup, is_admin, get_platform_executable, disable_quickedit_mode, restore_console_mode

# UI 모듈 import
from src.menu import show_custom_rom_step_menu

# STEP 모듈 import
from steps.step1_extract import run_step_1
from steps.step2_analyze import run_step_2
from steps.step3_patch import run_step_3
from steps.step4_verify import run_step_4


# 설정 관리

from src.config_manager import get_config

app_config = get_config()

# Logger는 core.logger에서 관리


# 헬퍼 함수


def request_admin_privileges() -> None:
    """관리자 권한 요청 (Windows 전용)"""
    if platform.system() != "Windows":
        return
    
    if is_admin():
        return
    
    # 초기화 전이므로 print 사용
    print(f"{Colors.WARNING}프로그램 실행을 위해 관리자 권한이 필요합니다.{Colors.ENDC}")
    try:
        params = subprocess.list2cmdline(sys.argv)
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        if ret <= 32:
            print(f"\n{Colors.FAIL}[오류] 관리자 권한 상승에 실패했습니다.{Colors.ENDC}")
    except Exception as e:
        print(f"\n{Colors.FAIL}[오류] 관리자 권한으로 재시작 중 예외 발생: {e}{Colors.ENDC}")
    finally:
        sys.exit()


def check_all_tools() -> bool:
    """필수 툴 검사"""
    print("--- [종합] 필수 파일 검사 ---")
    
    required_files = {
        ADB_EXE: "ADB 실행 파일",
        EDL_NG_EXE: "EDL-NG 실행 파일",
        AVBTOOL_PY: "AVBTool 프로그램",
    }
    
    for model, loader_path in LOADER_FILES.items():
        required_files[loader_path] = f"{model} 로더"
    
    required_files[get_platform_executable("magiskboot")] = "MagiskBoot 실행 파일"
    required_files[get_platform_executable("fetch")] = "Fetch 실행 파일"
    
    for hash_val, key_path in KNOWN_SIGNING_KEYS.items():
        required_files[key_path] = f"서명 키 ({hash_val[:10]}...)"
    
    required_paths = {Path(k): v for k, v in required_files.items()}
    
    loader_paths = [Path(p) for p in LOADER_FILES.values()]
    
    missing_files = []
    found_loader = False
    
    for file_path, description in required_paths.items():
        is_loader = file_path in loader_paths
        
        if not file_path.exists():
            if is_loader:
                continue
            missing_files.append(f"- {description} (예상 위치: {file_path})")
        else:
            if is_loader:
                found_loader = True
    
    if not found_loader:
        missing_files.append("- 'xbl_s_devprg_ns_MODEL.melf' 형태의 로더 파일 (최소 1개 필요)")
    
    if missing_files:
        print(f"\n{Colors.FAIL}{'='*60}{Colors.ENDC}")
        print(f"{Colors.FAIL}[!!!] 오류: 필수 파일이 누락되었습니다.{Colors.ENDC}")
        print(f"{Colors.FAIL}\n".join(missing_files) + f"{Colors.ENDC}")
        print(f"{Colors.FAIL}{'='*60}\n{Colors.ENDC}")
        return False
    
    print(f"  > {Colors.OKGREEN}모든 필수 도구/파일이 확인되었습니다.{Colors.ENDC}\n")
    return True


def cleanup_temp_dirs() -> None:
    """임시 디렉토리 정리"""
    print("\n[정보] 임시 폴더 정리 중...")
    dirs_to_clean = [TEMP_WORK_DIR, VERIFY_TEMP_DIR]
    for temp_dir in dirs_to_clean:
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
                print(f"  - '{temp_dir.name}' 폴더 삭제 완료.")
            except Exception as e:
                print(f"  - [경고] '{temp_dir.name}' 폴더 삭제 실패: {e}")


def show_main_menu(dev_mode: bool = False) -> tuple[str, bool]:
    """메인 메뉴 표시
    
    Args:
        dev_mode: 개발자 모드 활성화 여부
    
    Returns:
        (선택한 작업, 개발자 모드 상태)
    """
    # 헤더
    dev_badge = " [DEV MODE]" if dev_mode else ""
    print(f"\n{'━' * 60}")
    print(f"       롬파일 도구 - 메인 메뉴{dev_badge}")
    print(f"{'━' * 60}\n")
    
    # [롬파일 패치] 카테고리
    print("[롬파일 패치]")
    print("  1. RSA 공식 롬파일 자동 패치 🔄")
    
    if dev_mode:
        print("  2. RSA 공식 롬파일 자동 패치 단동 (STEP 선택) 🔧")
        print("  3. 사용자 지정 롬파일 자동 패치 🔄")
        print("  4. 사용자 지정 롬파일 자동 패치 단동 (STEP 선택) 🔧")
    else:
        print("  2. 사용자 지정 롬파일 자동 패치 🔄")
    
    # [국가코드 변경] 카테고리
    print("\n[국가코드 변경]")
    if dev_mode:
        print("  5. 국가코드 자동 패치 (CN→KR) 🔄")
        print("  6. 국가코드 자동 패치 단동 (STEP 선택) 🔧")
    else:
        print("  3. 국가코드 자동 패치 (CN→KR) 🔄")
    
    # [시스템 관리] 카테고리
    print("\n[시스템 관리]")
    if dev_mode:
        print("  7. 기기 정보 백업 💾")
        # print("  8. OTA를 이용한 펌웨어 업데이트 (🚨High Risk🚨)")  # 임시 비활성화 (배포용)
        # print("  9. OTA를 이용한 펌웨어 업데이트 단동 (STEP 선택) 🔧")  # 임시 비활성화 (배포용)
        
        print("\n[개발자 도구]")
        print("  8. 개발자 모드 비활성화")
    else:
        print("  4. 기기 정보 백업 💾")
        # print("  5. OTA를 이용한 펌웨어 업데이트 (🚨High Risk🚨)")  # 임시 비활성화 (배포용)
    
    # 종료
    print("\n  0. 종료\n")
    print(f"{'━' * 60}")
    
    # 입력 받기
    valid_choices = ['0', '1', '2', '3', '4']
    if dev_mode:
        valid_choices.extend(['5', '6', '7', '8'])
    
    while True:
        choice = input(f"\n{Colors.WARNING}실행할 작업 번호를 입력하십시오: {Colors.ENDC}").strip()
        
        # 개발자 모드 활성화 체크 (숨겨진 기능)
        if app_config.check_dev_password(choice) and not dev_mode:
            print(f"\n{Colors.OKGREEN}✓ 개발자 모드가 활성화되었습니다.{Colors.ENDC}")
            app_config.enable_dev_mode(choice)
            return ('refresh', True)
        
        if choice in valid_choices:
            return (choice, dev_mode)
        else:
            max_num = '8' if dev_mode else '4'
            print(f"{Colors.FAIL}잘못된 입력입니다. 0~{max_num} 사이의 숫자를 입력하십시오.{Colors.ENDC}")


def show_step_menu() -> int:
    """STEP 선택 메뉴"""
    print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}       실행할 STEP을 선택하십시오{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")
    print(f"{Colors.OKCYAN}1. STEP 1: 기기 정보 추출{Colors.ENDC}")
    print(f"   → ADB를 통해 기기 정보를 추출하고 EDL로 파티션을 백업")
    print(f"\n{Colors.OKCYAN}2. STEP 2: 롬파일 분석 및 복사{Colors.ENDC}")
    print(f"   → 롬파일의 롤백 인덱스를 확인하고 패치 준비")
    print(f"\n{Colors.OKCYAN}3. STEP 3: 롬파일 패치{Colors.ENDC}")
    print(f"   → 롬파일에 ARB 및 KernelSU 패치 적용")
    print(f"\n{Colors.OKCYAN}4. STEP 4: 패치 검증{Colors.ENDC}")
    print(f"   → 패치된 롬파일의 무결성 검증")
    print(f"\n{Colors.WARNING}0. 메인 메뉴로 돌아가기{Colors.ENDC}\n")
    print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    
    while True:
        choice = input(f"\n{Colors.WARNING}실행할 작업 번호를 입력하십시오 (0-4): {Colors.ENDC}").strip()
        if choice in ['0', '1', '2', '3', '4']:
            return int(choice)
        else:
            print(f"{Colors.FAIL}잘못된 입력입니다. 0~4 사이의 숫자를 입력하십시오.{Colors.ENDC}")


def main_continuous() -> None:
    """연속 동작 모드"""
    # 관리자 권한과 툴 체크는 main()에서 이미 수행됨
    
    target_model = None
    device_indices = None
    step1_output_dir = None
    rom_path = None
    rom_path_raw = None
    rom_indices = None
    want_root = False
    indices_to_patch = {}
    current_step_name = "STEP 0 (준비)"
    
    try:
        current_step_name = "STEP 1 (기기 정보 추출)"
        print(f"{Colors.BOLD}\n--- STEP 1: 기기 정보 추출 시작 ---{Colors.ENDC}")
        target_model, device_indices, step1_output_dir = run_step_1()
        if not target_model or not device_indices:
            print(f"\n{Colors.WARNING}[정보] 작업이 취소되었거나 완료할 수 없습니다.{Colors.ENDC}")
            return
        
        print(f"{Colors.OKGREEN}STEP 1 완료. 모델: {target_model}, 기기 RB: {device_indices}{Colors.ENDC}")
        
        current_step_name = "STEP 2 (롬파일 분석/백업)"
        print(f"{Colors.BOLD}\n--- STEP 2: 롬파일 분석 및 복사 시작 ---{Colors.ENDC}")
        rom_path, rom_indices = run_step_2(target_model, step1_output_dir)
        if not rom_path or not rom_indices:
            raise Exception("STEP 2 실패: 롬파일을 분석/복사할 수 없습니다.")
        
        rom_path_raw = f"{rom_path}_RAW"
        
        print(f"{Colors.OKGREEN}STEP 2 완료. 롬 경로: {rom_path}, 롬 RB: {rom_indices}{Colors.ENDC}")
        
        current_step_name = "STEP 3 (롬파일 패치)"
        print(f"{Colors.BOLD}\n--- STEP 3: 롬파일 패치 시작 ---{Colors.ENDC}")
        result = run_step_3(rom_path, device_indices, rom_indices)
        
        if result is None:
            # 사용자가 ARB 패치를 취소함
            print(f"{Colors.WARNING}작업이 취소되었습니다. 메인 메뉴로 돌아갑니다.{Colors.ENDC}")
            return
        
        want_root, indices_to_patch = result
        print(f"{Colors.OKGREEN}STEP 3 완료. 루팅 선택: {want_root}, 패치된 RB: {indices_to_patch}{Colors.ENDC}")
        
        current_step_name = "STEP 4 (패치 검증)"
        print(f"{Colors.BOLD}\n--- STEP 4: 패치 검증 시작 ---{Colors.ENDC}")
        run_step_4(rom_path, want_root, indices_to_patch, rom_indices)
        print(f"{Colors.OKGREEN}STEP 4 완료.{Colors.ENDC}")
        
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}===== 모든 작업이 성공적으로 완료되었습니다! ===={Colors.ENDC}\n")
        input(f"{Colors.WARNING}Enter 키를 눌러 메뉴로 돌아가기...{Colors.ENDC}")
    
    except Exception as e:
        error_msg = str(e)
        print(f"\n{Colors.FAIL}{Colors.BOLD}[!!!] 프로그램 실행 중 치명적인 오류 발생: {error_msg}{Colors.ENDC}")
        
        # Traceback을 로그 파일에만 기록 (콘솔에는 표시 안 함)
        import traceback
        from core.logger import log_error
        log_error(error_msg, exception=e, context=current_step_name)
        
        # 팝업은 각 STEP에서 이미 표시했으므로 여기서는 표시하지 않음 (중복 방지)
        
        if current_step_name == "STEP 3 (롬파일 패치)" and rom_path and rom_path_raw:
            print(f"\n{Colors.WARNING}--- STEP 3 오류 감지. 롬파일 롤백 시도... ---{Colors.ENDC}")
            try:
                if not os.path.isdir(rom_path_raw):
                    print(f"{Colors.FAIL}[오류] 롤백 실패: 백업 폴더(_RAW)를 찾을 수 없습니다!{Colors.ENDC}")
                else:
                    if os.path.isdir(rom_path):
                        shutil.rmtree(rom_path)
                    os.rename(rom_path_raw, rom_path)
                    print(f"{Colors.OKGREEN}[성공] 롬파일이 롤백되었습니다.{Colors.ENDC}")
            except Exception as rollback_e:
                print(f"{Colors.FAIL}[!!!] 치명적 롤백 오류: {rollback_e}{Colors.ENDC}")
                show_popup(
                    "롤백 오류 - NG",
                    f"STEP 3 롤백 실패!\n{rollback_e}\n\n수동으로 {rom_path_raw} 폴더를\n{os.path.basename(rom_path)}(으)로 변경하세요!",
                    icon=UIConstants.ICON_ERROR
                )
    
    finally:
        cleanup_temp_dirs()


def execute_step_1() -> bool:
    """STEP 1 독립 실행"""
    print(f"{Colors.BOLD}\n--- STEP 1: 기기 정보 추출 시작 ---{Colors.ENDC}")
    target_model, device_indices, step1_output_dir = run_step_1()
    
    if not target_model or not device_indices:
        print(f"\n{Colors.WARNING}[정보] STEP 1이 취소되었거나 완료할 수 없습니다.{Colors.ENDC}")
        return False
    
    step_data = {
        "model": target_model,
        "device_indices": device_indices,
        "output_dir": step1_output_dir
    }
    save_step_data(1, step_data)
    
    print(f"{Colors.OKGREEN}STEP 1 완료.{Colors.ENDC}")
    return True


def execute_step_2() -> bool:
    """STEP 2 독립 실행"""
    if not check_step_prerequisites(2):
        return False
    
    step1_data = load_step_data(1)
    if not step1_data:
        print(f"{Colors.FAIL}[오류] STEP 1 데이터를 로드할 수 없습니다.{Colors.ENDC}")
        return False
    
    target_model = step1_data["model"]
    step1_output_dir = step1_data["output_dir"]
    
    print(f"{Colors.BOLD}\n--- STEP 2: 롬파일 분석 및 복사 시작 ---{Colors.ENDC}")
    rom_path, rom_indices = run_step_2(target_model, step1_output_dir)
    
    if not rom_path or not rom_indices:
        print(f"\n{Colors.FAIL}[오류] STEP 2 실패.{Colors.ENDC}")
        return False
    
    step_data = {
        "rom_path": rom_path,
        "rom_path_raw": f"{rom_path}_RAW",
        "rom_indices": rom_indices
    }
    save_step_data(2, step_data)
    
    print(f"{Colors.OKGREEN}STEP 2 완료.{Colors.ENDC}")
    return True


def execute_step_3() -> bool:
    """STEP 3 독립 실행"""
    if not check_step_prerequisites(3):
        return False
    
    step1_data = load_step_data(1)
    step2_data = load_step_data(2)
    
    if not step1_data or not step2_data:
        print(f"{Colors.FAIL}[오류] 이전 STEP 데이터를 로드할 수 없습니다.{Colors.ENDC}")
        return False
    
    device_indices = step1_data["device_indices"]
    rom_path = step2_data["rom_path"]
    rom_path_raw = step2_data["rom_path_raw"]
    rom_indices = step2_data["rom_indices"]
    
    print(f"{Colors.BOLD}\n--- STEP 3: 롬파일 패치 시작 ---{Colors.ENDC}")
    
    try:
        result = run_step_3(rom_path, device_indices, rom_indices)
        
        if result is None:
            # 사용자가 ARB 패치를 취소함
            print(f"{Colors.WARNING}작업이 취소되었습니다.{Colors.ENDC}")
            return False
        
        want_root, indices_to_patch = result
        
        step_data = {
            "want_root": want_root,
            "indices_to_patch": indices_to_patch
        }
        save_step_data(3, step_data)
        
        print(f"{Colors.OKGREEN}STEP 3 완료.{Colors.ENDC}")
        return True
    
    except Exception as e:
        error_msg = str(e)
        print(f"\n{Colors.FAIL}[오류] STEP 3 실패: {error_msg}{Colors.ENDC}")
        
        # 에러 팝업
        show_popup(
            "STEP 3 패치 실패",
            f"롬파일 패치 중 오류가 발생했습니다.\n\n오류: {error_msg}",
            icon=UIConstants.ICON_ERROR
        )
        
        if rom_path and rom_path_raw and os.path.isdir(rom_path_raw):
            print(f"\n{Colors.WARNING}--- 롬파일 롤백 시도... ---{Colors.ENDC}")
            try:
                if os.path.isdir(rom_path):
                    shutil.rmtree(rom_path)
                os.rename(rom_path_raw, rom_path)
                print(f"{Colors.OKGREEN}롤백 완료!{Colors.ENDC}")
            except Exception as rollback_error:
                print(f"{Colors.FAIL}롤백 실패: {rollback_error}{Colors.ENDC}")
        
        return False


def execute_step_4() -> bool:
    """STEP 4 독립 실행"""
    if not check_step_prerequisites(4):
        return False
    
    step2_data = load_step_data(2)
    step3_data = load_step_data(3)
    
    if not step2_data or not step3_data:
        print(f"{Colors.FAIL}[오류] 이전 STEP 데이터를 로드할 수 없습니다.{Colors.ENDC}")
        return False
    
    rom_path = step2_data["rom_path"]
    rom_indices = step2_data["rom_indices"]
    want_root = step3_data["want_root"]
    indices_to_patch = step3_data["indices_to_patch"]
    
    print(f"{Colors.BOLD}\n--- STEP 4: 패치 검증 시작 ---{Colors.ENDC}")
    
    try:
        run_step_4(rom_path, want_root, indices_to_patch, rom_indices)
        print(f"{Colors.OKGREEN}STEP 4 완료.{Colors.ENDC}")
        return True
    except Exception as e:
        error_msg = str(e)
        print(f"\n{Colors.FAIL}[오류] STEP 4 실패: {error_msg}{Colors.ENDC}")
        
        # 에러 팝업
        show_popup(
            "STEP 4 검증 실패",
            f"패치 검증 중 오류가 발생했습니다.\n\n오류: {error_msg}",
            icon=UIConstants.ICON_ERROR
        )
        
        return False


# 추가 유틸리티 함수 (NEW!)


def execute_backup_device() -> bool:
    """기기 정보 백업"""
    from utils.backup_device import run_backup
    return run_backup()


def execute_country_code_auto() -> bool:
    """국가코드 자동 변경 (CN→KR)"""
    from utils.country_code import run_auto_country_change
    return run_auto_country_change()


def execute_country_code_manual() -> bool:
    """국가코드 수동 변경 (STEP별)"""
    from utils.country_code import run_manual_country_change_menu
    print(f"{Colors.BOLD}\n--- 국가코드 수동 변경 (STEP별) ---{Colors.ENDC}")
    print(f"{Colors.WARNING}⚠️  개발자 모드 기능 - STEP별 실행{Colors.ENDC}")
    print(f"{Colors.WARNING}이 기능은 디버깅/테스트용입니다.{Colors.ENDC}")
    return run_manual_country_change_menu()


def execute_ota_update_auto() -> bool:
    """OTA 펌웨어 업데이트 (자동)"""
    print(f"{Colors.BOLD}\n--- OTA 펌웨어 업데이트 (자동) ---{Colors.ENDC}")
    print(f"{Colors.WARNING}[알림] 이 기능은 아직 구현 중입니다.{Colors.ENDC}")
    print(f"  > payload.bin을 자동으로 언팩하고 플래싱합니다.")
    input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
    # 향후 구현 예정: payload.bin 자동 추출 및 플래싱 (utils/ota_update.py)
    return False


def execute_ota_update_manual() -> bool:
    """OTA 업데이트 (수동, 디버깅용)"""
    print(f"{Colors.BOLD}\n--- OTA 업데이트 (수동, 디버깅) ---{Colors.ENDC}")
    print(f"{Colors.WARNING}[알림] 이 기능은 아직 구현 중입니다.{Colors.ENDC}")
    print(f"  > 세부 옵션을 설정하여 OTA 업데이트를 진행합니다.")
    input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
    # 향후 구현 예정: 수동 OTA 업데이트 옵션 (utils/ota_update.py)
    return False


def execute_custom_rom_auto() -> bool:
    """사용자 지정 롬파일 자동 패치 (연속 모드)"""
    from steps.step2_custom_rom import (
        check_and_prepare_rsa_folder,
        run_step_2_custom,
        input_rsa_folder_name,
        move_to_rsa_folder,
        show_rsa_flash_guide
    )
    from steps.step1_extract import run_step_1
    from steps.step3_patch import run_step_3_custom
    from steps.step4_verify import run_step_4
    
    target_model = None
    device_indices = None
    patch_path = None
    rom_type = None
    current_step_name = "STEP 0 (준비)"
    
    try:
        # STEP 0: RSA 폴더 확인
        current_step_name = "STEP 0 (RSA 확인)"
        rsa_available, rsa_dir = check_and_prepare_rsa_folder()
        if not rsa_available:
            print(f"\n{Colors.WARNING}RSA 폴더를 준비할 수 없어 작업을 중단합니다.{Colors.ENDC}")
            input(f"\n{Colors.WARNING}Enter 키를 눌러 메뉴로 돌아가기...{Colors.ENDC}")
            return False
        
        # STEP 1: 기기 정보 추출
        current_step_name = "STEP 1 (기기 정보 추출)"
        print(f"{Colors.BOLD}\n--- STEP 1: 기기 정보 추출 시작 ---{Colors.ENDC}")
        target_model, device_indices, step1_output_dir = run_step_1()
        if not target_model or not device_indices:
            print(f"\n{Colors.WARNING}[정보] 작업이 취소되었거나 완료할 수 없습니다.{Colors.ENDC}")
            input(f"\n{Colors.WARNING}Enter 키를 눌러 메뉴로 돌아가기...{Colors.ENDC}")
            return False
        
        print(f"{Colors.OKGREEN}STEP 1 완료. 모델: {target_model}, 기기 RB: {device_indices}{Colors.ENDC}")
        
        # STEP 2-Custom: 사용자 지정 롬파일 분석 및 패치용 폴더 생성
        current_step_name = "STEP 2-Custom (사용자 지정 롬파일 분석)"
        patch_path, rom_type, rom_info, rom_indices = run_step_2_custom(target_model, step1_output_dir)
        if not patch_path or not rom_type:
            print(f"\n{Colors.WARNING}[정보] 작업이 취소되었거나 완료할 수 없습니다.{Colors.ENDC}")
            input(f"\n{Colors.WARNING}Enter 키를 눌러 메뉴로 돌아가기...{Colors.ENDC}")
            return False
        
        print(f"{Colors.OKGREEN}STEP 2-Custom 완료. 롬 타입: {rom_type.upper()}{Colors.ENDC}")
        print(f"  패치용 폴더: {patch_path}")
        if rom_indices:
            print(f"  롬 RB: {rom_indices}")
        
        # STEP 3-Custom: 롬파일 패치 (롬 타입별 조건부)
        current_step_name = "STEP 3-Custom (롬파일 패치)"
        print(f"{Colors.BOLD}\n--- STEP 3-Custom: 롬파일 패치 시작 ---{Colors.ENDC}")
        
        result = run_step_3_custom(patch_path, rom_type, device_indices, rom_indices)
        
        if result is None:
            # 사용자가 ARB 패치를 취소함
            print(f"{Colors.WARNING}작업이 취소되었습니다. 메인 메뉴로 돌아갑니다.{Colors.ENDC}")
            return
        
        want_root, indices_to_patch = result
        print(f"{Colors.OKGREEN}STEP 3-Custom 완료. 루팅 선택: {want_root}{Colors.ENDC}")
        
        # STEP 4: 패치 검증
        current_step_name = "STEP 4 (패치 검증)"
        print(f"{Colors.BOLD}\n--- STEP 4: 패치 검증 시작 ---{Colors.ENDC}")
        run_step_4(patch_path, want_root, indices_to_patch, rom_indices)
        
        print(f"{Colors.OKGREEN}STEP 4 완료.{Colors.ENDC}")
        
        # STEP 5: RSA 폴더로 이동 (잘라내기)
        current_step_name = "STEP 5 (RSA 폴더로 이동)"
        rsa_folder_name = input_rsa_folder_name(target_model, rom_type)
        
        if not rsa_folder_name:
            print(f"\n{Colors.WARNING}RSA 폴더 이름 입력이 취소되었습니다.{Colors.ENDC}")
            print(f"패치된 롬파일 위치: {patch_path}")
            input(f"\n{Colors.WARNING}Enter 키를 눌러 메뉴로 돌아가기...{Colors.ENDC}")
            return False
        
        if move_to_rsa_folder(patch_path, rsa_dir, rsa_folder_name):
            rsa_folder_path = os.path.join(rsa_dir, rsa_folder_name)
            show_rsa_flash_guide(rsa_folder_path)
            return True
        else:
            print(f"\n{Colors.WARNING}RSA 폴더로 이동하지 못했습니다.{Colors.ENDC}")
            print(f"패치된 롬파일 위치: {patch_path}")
            input(f"\n{Colors.WARNING}Enter 키를 눌러 메뉴로 돌아가기...{Colors.ENDC}")
            return False
    
    except Exception as e:
        error_msg = str(e)
        print(f"\n{Colors.FAIL}{'='*60}{Colors.ENDC}")
        print(f"{Colors.FAIL}{Colors.BOLD}[오류 - NG] {current_step_name} 실패{Colors.ENDC}")
        print(f"{Colors.FAIL}오류 내용: {error_msg}{Colors.ENDC}")
        print(f"{Colors.FAIL}{'='*60}{Colors.ENDC}")
        
        # Traceback을 로그 파일에만 기록 (콘솔에는 표시 안 함)
        from core.logger import log_error
        log_error(error_msg, exception=e, context=current_step_name)
        
        # 에러 팝업
        show_popup(
            "사용자 지정 롬 패치 실패",
            f"작업 실행 중 오류가 발생했습니다.\n\n"
            f"단계: {current_step_name}\n"
            f"오류: {error_msg}\n\n"
            f"자세한 내용은 로그 파일을 확인하세요.",
            icon=UIConstants.ICON_ERROR
        )
        input(f"\n{Colors.WARNING}Enter 키를 눌러 메뉴로 돌아가기...{Colors.ENDC}")
        return False


# show_custom_rom_step_menu는 ui/menu.py로 이동됨


# Custom ROM Manual Mode - Helper Functions


def _load_custom_rom_saved_data() -> dict:
    """저장된 Custom ROM 데이터 로드"""
    from core.data_manager import load_custom_rom_step_data
    
    custom_rom_data = {
        'rsa_available': False,
        'rsa_dir': '',
        'target_model': None,
        'device_indices': None,
        'step1_output_dir': None,
        'patch_path': None,
        'rom_type': None,
        'rom_info': None,
        'want_root': False,
        'indices_to_patch': {},
        'rom_indices': None,
        'rsa_folder_name': None,
    }
    
    print(f"\n{Colors.BOLD}[정보] 저장된 데이터 확인 중...{Colors.ENDC}")
    for step_num in [0, 1, 2, 3, 5]:
        loaded_data = load_custom_rom_step_data(step_num)
        if loaded_data:
            if step_num == 0:
                custom_rom_data['rsa_available'] = loaded_data.get('rsa_available', False)
                custom_rom_data['rsa_dir'] = loaded_data.get('rsa_dir', '')
            elif step_num == 1:
                custom_rom_data['target_model'] = loaded_data.get('model')
                custom_rom_data['device_indices'] = loaded_data.get('device_indices')
                custom_rom_data['step1_output_dir'] = loaded_data.get('output_dir')
            elif step_num == 2:
                custom_rom_data['patch_path'] = loaded_data.get('patch_path')
                custom_rom_data['rom_type'] = loaded_data.get('rom_type')
                custom_rom_data['rom_info'] = loaded_data.get('rom_info')
                custom_rom_data['rom_indices'] = loaded_data.get('rom_indices')
            elif step_num == 3:
                custom_rom_data['want_root'] = loaded_data.get('want_root', False)
                custom_rom_data['indices_to_patch'] = loaded_data.get('indices_to_patch', {})
            elif step_num == 5:
                custom_rom_data['rsa_folder_name'] = loaded_data.get('rsa_folder_name')
    
    if any([custom_rom_data['target_model'], custom_rom_data['patch_path']]):
        print(f"{Colors.OKGREEN}✓ 이전 실행 데이터를 복원했습니다.{Colors.ENDC}")
    else:
        print(f"{Colors.OKCYAN}처음 실행합니다.{Colors.ENDC}")
    
    return custom_rom_data


def _execute_custom_rom_step0(custom_rom_data: dict) -> None:
    """STEP 0: RSA 폴더 확인"""
    from steps.step2_custom_rom import check_and_prepare_rsa_folder
    from core.data_manager import save_custom_rom_step_data
    
    rsa_available, rsa_dir = check_and_prepare_rsa_folder()
    custom_rom_data['rsa_available'] = rsa_available
    custom_rom_data['rsa_dir'] = rsa_dir
    
    save_custom_rom_step_data(0, {
        'rsa_available': rsa_available,
        'rsa_dir': rsa_dir
    })
    
    if rsa_available:
        print(f"\n{Colors.OKGREEN}✓ STEP 0 완료!{Colors.ENDC}")
    else:
        print(f"\n{Colors.FAIL}✗ STEP 0 실패. RSA 폴더를 준비할 수 없습니다.{Colors.ENDC}")


def _execute_custom_rom_step1(custom_rom_data: dict) -> None:
    """STEP 1: 기기 정보 추출"""
    from steps.step1_extract import run_step_1
    from core.data_manager import save_custom_rom_step_data
    
    print(f"{Colors.BOLD}\n--- STEP 1: 기기 정보 추출 ---{Colors.ENDC}")
    target_model, device_indices, step1_output_dir = run_step_1()
    
    if target_model and device_indices:
        custom_rom_data['target_model'] = target_model
        custom_rom_data['device_indices'] = device_indices
        custom_rom_data['step1_output_dir'] = step1_output_dir
        
        save_custom_rom_step_data(1, {
            'model': target_model,
            'device_indices': device_indices,
            'output_dir': step1_output_dir
        })
        
        print(f"\n{Colors.OKGREEN}✓ STEP 1 완료!{Colors.ENDC}")
    else:
        print(f"\n{Colors.WARNING}STEP 1이 완료되지 않았습니다.{Colors.ENDC}")


def _execute_custom_rom_step2(custom_rom_data: dict) -> None:
    """STEP 2: 사용자 지정 롬파일 분석 및 패치용 폴더 생성"""
    from steps.step2_custom_rom import run_step_2_custom
    from core.data_manager import save_custom_rom_step_data
    
    if not custom_rom_data['target_model']:
        print(f"\n{Colors.FAIL}[오류] STEP 1을 먼저 실행하세요.{Colors.ENDC}")
        input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
        return
    
    patch_path, rom_type, rom_info, rom_indices = run_step_2_custom(
        custom_rom_data['target_model'],
        custom_rom_data['step1_output_dir']
    )
    
    if patch_path and rom_type:
        custom_rom_data['patch_path'] = patch_path
        custom_rom_data['rom_type'] = rom_type
        custom_rom_data['rom_info'] = rom_info
        custom_rom_data['rom_indices'] = rom_indices
        
        save_custom_rom_step_data(2, {
            'patch_path': patch_path,
            'rom_type': rom_type,
            'rom_info': rom_info,
            'rom_indices': rom_indices
        })
        
        print(f"\n{Colors.OKGREEN}✓ STEP 2-Custom 완료!{Colors.ENDC}")
        print(f"  패치용 폴더: {patch_path}")
        if rom_indices:
            print(f"  롬 RB: {rom_indices}")
    else:
        print(f"\n{Colors.WARNING}STEP 2-Custom이 완료되지 않았습니다.{Colors.ENDC}")


def _execute_custom_rom_step3(custom_rom_data: dict) -> bool:
    """STEP 3: 롬파일 패치
    
    Returns:
        True if successful, False if cancelled/error
    """
    from steps.step3_patch import run_step_3_custom
    from core.data_manager import save_custom_rom_step_data
    
    if not custom_rom_data['patch_path']:
        print(f"\n{Colors.FAIL}[오류] STEP 2-Custom을 먼저 실행하세요.{Colors.ENDC}")
        input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
        return False
    
    print(f"{Colors.BOLD}\n--- STEP 3-Custom: 롬파일 패치 ---{Colors.ENDC}")
    
    result = run_step_3_custom(
        custom_rom_data['patch_path'],
        custom_rom_data['rom_type'],
        custom_rom_data['device_indices'],
        custom_rom_data['rom_indices']
    )
    
    if result is None:
        print(f"{Colors.WARNING}작업이 취소되었습니다.{Colors.ENDC}")
        return False
    
    want_root, indices_to_patch = result
    custom_rom_data['want_root'] = want_root
    custom_rom_data['indices_to_patch'] = indices_to_patch
    
    save_custom_rom_step_data(3, {
        'want_root': want_root,
        'indices_to_patch': indices_to_patch
    })
    
    print(f"\n{Colors.OKGREEN}✓ STEP 3-Custom 완료!{Colors.ENDC}")
    return True


def _execute_custom_rom_step4(custom_rom_data: dict) -> None:
    """STEP 4: 패치 검증"""
    from steps.step4_verify import run_step_4
    
    if not custom_rom_data['patch_path'] or not custom_rom_data['indices_to_patch']:
        print(f"\n{Colors.FAIL}[오류] STEP 3을 먼저 실행하세요.{Colors.ENDC}")
        input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
        return
    
    print(f"{Colors.BOLD}\n--- STEP 4: 패치 검증 ---{Colors.ENDC}")
    
    run_step_4(
        custom_rom_data['patch_path'],
        custom_rom_data['want_root'],
        custom_rom_data['indices_to_patch'],
        custom_rom_data['rom_indices']
    )
    
    print(f"\n{Colors.OKGREEN}✓ STEP 4 완료!{Colors.ENDC}")


def _execute_custom_rom_step5(custom_rom_data: dict) -> bool:
    """STEP 5: RSA 폴더로 이동
    
    Returns:
        True if successful (and should exit), False otherwise
    """
    from steps.step2_custom_rom import input_rsa_folder_name, move_to_rsa_folder, show_rsa_flash_guide
    from core.data_manager import save_custom_rom_step_data
    import os
    
    if not custom_rom_data['rsa_available']:
        print(f"\n{Colors.FAIL}[오류] STEP 0을 먼저 실행하세요.{Colors.ENDC}")
        input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
        return False
    
    if not custom_rom_data['patch_path']:
        print(f"\n{Colors.FAIL}[오류] STEP 2-Custom을 먼저 실행하세요.{Colors.ENDC}")
        input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
        return False
    
    print(f"{Colors.BOLD}\n--- STEP 5: RSA 폴더로 이동 ---{Colors.ENDC}")
    
    rsa_folder_name = input_rsa_folder_name(
        custom_rom_data['target_model'],
        custom_rom_data['rom_type']
    )
    
    if not rsa_folder_name:
        print(f"\n{Colors.WARNING}RSA 폴더 이름 입력이 취소되었습니다.{Colors.ENDC}")
        input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
        return False
    
    if move_to_rsa_folder(
        custom_rom_data['patch_path'],
        custom_rom_data['rsa_dir'],
        rsa_folder_name
    ):
        save_custom_rom_step_data(5, {
            'rsa_folder_name': rsa_folder_name
        })
        
        rsa_folder_path = os.path.join(custom_rom_data['rsa_dir'], rsa_folder_name)
        show_rsa_flash_guide(rsa_folder_path)
        print(f"\n{Colors.OKGREEN}✓ STEP 5 완료!{Colors.ENDC}")
        return True
    else:
        print(f"\n{Colors.WARNING}RSA 폴더로 이동하지 못했습니다.{Colors.ENDC}")
        input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
        return False


# Custom ROM Manual Mode - Main Function


def execute_custom_rom_manual() -> bool:
    """사용자 지정 롬파일 단동 패치 (STEP 선택) - 리팩토링 버전"""
    # 저장된 데이터 로드
    custom_rom_data = _load_custom_rom_saved_data()
    
    while True:
        step_choice = show_custom_rom_step_menu()
        
        if step_choice == 99:
            print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다.{Colors.ENDC}")
            return True
        
        try:
            if step_choice == 0:
                _execute_custom_rom_step0(custom_rom_data)
            elif step_choice == 1:
                _execute_custom_rom_step1(custom_rom_data)
            elif step_choice == 2:
                _execute_custom_rom_step2(custom_rom_data)
            elif step_choice == 3:
                if not _execute_custom_rom_step3(custom_rom_data):
                    continue  # ARB 취소 시 다음 STEP 선택으로
            elif step_choice == 4:
                _execute_custom_rom_step4(custom_rom_data)
            elif step_choice == 5:
                if _execute_custom_rom_step5(custom_rom_data):
                    return True  # STEP 5 성공 시 종료
        
        except Exception as e:
            error_msg = str(e)
            print(f"\n{Colors.FAIL}[오류] STEP 실행 중 예외 발생: {error_msg}{Colors.ENDC}")
            
            # Traceback을 로그 파일에만 기록 (콘솔에는 표시 안 함)
            from core.logger import log_error
            log_error(error_msg, exception=e, context="사용자 지정 롬 STEP 실행")
            
            # 에러 팝업
            show_popup(
                "사용자 지정 롬 STEP 실행 실패",
                f"STEP 실행 중 오류가 발생했습니다.\n\n"
                f"오류: {error_msg}\n\n"
                f"자세한 내용은 로그 파일을 확인하세요.",
                icon=UIConstants.ICON_ERROR
            )
            
            input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
        
        # 다음 STEP 선택
        print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
        while True:
            continue_choice = input(f"\n{Colors.WARNING}다른 STEP을 실행하시겠습니까? (y/n): {Colors.ENDC}").strip().lower()
            if continue_choice == 'y':
                break
            elif continue_choice == 'n':
                print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다.{Colors.ENDC}")
                return True
            else:
                print(f"{Colors.FAIL}잘못된 입력입니다. 'y' 또는 'n'을 입력하십시오.{Colors.ENDC}")


def main_individual() -> None:
    """단독 동작 모드"""
    while True:
        step_choice = show_step_menu()
        
        if step_choice == 0:
            print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다.{Colors.ENDC}")
            return
        
        if step_choice == 1:
            execute_step_1()
        elif step_choice == 2:
            execute_step_2()
        elif step_choice == 3:
            execute_step_3()
        elif step_choice == 4:
            execute_step_4()
        
        print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
        while True:
            continue_choice = input(f"\n{Colors.WARNING}다른 STEP을 실행하시겠습니까? (y/n): {Colors.ENDC}").strip().lower()
            if continue_choice == 'y':
                break
            elif continue_choice == 'n':
                print(f"\n{Colors.OKCYAN}프로그램을 종료합니다.{Colors.ENDC}")
                return
            else:
                print(f"{Colors.FAIL}잘못된 입력입니다. 'y' 또는 'n'을 입력하십시오.{Colors.ENDC}")


def show_startup_banner() -> None:
    """프로그램 시작 배너 표시"""
    # UTF-8 출력을 위한 설정 (Windows cp949 인코딩 오류 방지)
    try:
        import sys
        import io
        if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass
    
    try:
        print(f"""
{Colors.OKCYAN}
  ██████╗  ██████╗ ███╗   ███╗    ██████╗  █████╗ ████████╗ ██████╗██╗  ██╗███████╗██████╗ 
  ██╔══██╗██╔═══██╗████╗ ████║    ██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██║  ██║██╔════╝██╔══██╗
  ██████╔╝██║   ██║██╔████╔██║    ██████╔╝███████║   ██║   ██║     ███████║█████╗  ██████╔╝
  ██╔══██╗██║   ██║██║╚██╔╝██║    ██╔═══╝ ██╔══██║   ██║   ██║     ██╔══██║██╔══╝  ██╔══██╗
  ██║  ██║╚██████╔╝██║ ╚═╝ ██║    ██║     ██║  ██║   ██║   ╚██████╗██║  ██║███████╗██║  ██║
  ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝    ╚═╝     ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
{Colors.ENDC}

{Colors.BOLD}                    {APP_NAME} v{APP_VERSION}{Colors.ENDC}
                    
                    Author: {APP_AUTHOR}
                    Last Updated: {APP_LAST_UPDATED}
    """)
    except UnicodeEncodeError:
        # 인코딩 오류 시 간단한 텍스트 배너로 대체
        print(f"\n{Colors.BOLD}{'='*80}{Colors.ENDC}")
        print(f"{Colors.OKCYAN}{Colors.BOLD}    {APP_NAME} v{APP_VERSION}{Colors.ENDC}")
        print(f"    Author: {APP_AUTHOR}")
        print(f"    Last Updated: {APP_LAST_UPDATED}")
        print(f"{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def show_user_agreement() -> bool:
    """사용자 동의서 표시 및 동의 확인"""
    from config.paths import USER_AGREEMENT_FILE
    agreement_file = USER_AGREEMENT_FILE
    
    # 동의서 파일이 없으면 프로그램 종료
    if not agreement_file.exists():
        print(f"\n{Colors.FAIL}{'='*60}{Colors.ENDC}")
        print(f"{Colors.FAIL}[오류] 동의서 파일을 찾을 수 없습니다!{Colors.ENDC}")
        print(f"{Colors.WARNING}파일 위치: {agreement_file.absolute()}{Colors.ENDC}")
        print(f"{Colors.FAIL}{'='*60}{Colors.ENDC}\n")
        
        show_popup(
            "동의서 파일 없음",
            f"프로그램_사용자_동의서.txt 파일을 찾을 수 없습니다.\n\n"
            f"파일 위치:\n{agreement_file.absolute()}\n\n"
            f"동의서 파일이 있어야 프로그램을 실행할 수 있습니다.",
            icon=UIConstants.ICON_ERROR
        )
        
        input(f"{Colors.WARNING}Enter 키를 눌러 종료...{Colors.ENDC}")
        return False
    
    try:
        # 동의서 파일을 기본 프로그램으로 열기
        print(f"\n{Colors.OKCYAN}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}프로그램 사용자 동의서{Colors.ENDC}")
        print(f"{Colors.OKCYAN}{'='*60}{Colors.ENDC}\n")
        print(f"{Colors.WARNING}동의서 파일을 엽니다. 내용을 읽어주세요...{Colors.ENDC}\n")
        
        # Windows에서 기본 프로그램으로 파일 열기
        os.startfile(str(agreement_file))
        
        # 사용자가 파일을 읽을 시간 대기
        print(f"{Colors.OKCYAN}동의서를 읽으신 후, 이 창으로 돌아와서 진행해주세요.{Colors.ENDC}\n")
        
        # 동의 확인
        print(f"{Colors.BOLD}{Colors.WARNING}위 동의서를 모두 읽고 이해하셨습니까?{Colors.ENDC}")
        print(f"{Colors.WARNING}동의하시면 \"동의\"를 정확히 입력하세요.{Colors.ENDC}")
        print(f"{Colors.WARNING}동의하지 않으시면 다른 내용을 입력하세요 (프로그램 종료).{Colors.ENDC}\n")
        
        max_attempts = 3
        for attempt in range(max_attempts):
            response = input(f"{Colors.WARNING}입력: {Colors.ENDC}").strip()
            
            if response == "동의":
                print(f"\n{Colors.OKGREEN}✓ 동의하셨습니다. 프로그램을 시작합니다.{Colors.ENDC}\n")
                return True
            else:
                remaining = max_attempts - attempt - 1
                if remaining > 0:
                    print(f"{Colors.FAIL}\"동의\"를 정확히 입력하셔야 합니다. (남은 시도: {remaining}회){Colors.ENDC}")
                else:
                    print(f"\n{Colors.FAIL}동의하지 않으셨습니다. 프로그램을 종료합니다.{Colors.ENDC}")
                    return False
        
        return False
    
    except Exception as e:
        print(f"\n{Colors.WARNING}[경고] 동의서 파일을 여는 중 오류 발생: {e}{Colors.ENDC}")
        print(f"{Colors.WARNING}계속 진행하시겠습니까? (y/n): {Colors.ENDC}")
        response = input().strip().lower()
        return response == 'y'


def main() -> None:
    """메인 진입점"""
    # 관리자 권한 체크 (가장 먼저)
    request_admin_privileges()
    
    # Windows Console QuickEdit Mode 비활성화 (마우스 클릭으로 인한 멈춤 방지)
    original_console_mode = disable_quickedit_mode()
    
    # 시작 배너 표시
    show_startup_banner()
    
    # 딜레이 제거 - 불필요한 대기 시간 최적화
    # time.sleep(1.5)
    
    # 사용자 동의서 표시 및 동의 확인
    if not show_user_agreement():
        restore_console_mode(original_console_mode)
        sys.exit(0)
    
    init_logger()
    
    if not check_all_tools():
        show_popup(TitleMessages.ERROR, ErrorMessages.FILE_NOT_FOUND, icon=UIConstants.ICON_ERROR)
        close_logger()
        restore_console_mode(original_console_mode)
        sys.exit(1)
    
    # 메뉴 매핑 (최적화: 딕셔너리 사용)
    menu_actions_normal = {
        '1': main_continuous,
        '2': execute_custom_rom_auto,
        '3': execute_country_code_auto,
        '4': execute_backup_device,
        # '5': execute_ota_update_auto,  # 임시 비활성화 (배포용)
    }
    
    menu_actions_dev = {
        '1': main_continuous,
        '2': main_individual,
        '3': execute_custom_rom_auto,
        '4': execute_custom_rom_manual,
        '5': execute_country_code_auto,
        '6': execute_country_code_manual,
        '7': execute_backup_device,
        # '8': execute_ota_update_auto,  # 임시 비활성화 (배포용)
        # '9': execute_ota_update_manual,  # 임시 비활성화 (배포용)
    }
    
    choice = None
    try:
        while True:
            choice, current_dev_mode = show_main_menu(app_config.dev_mode)
            
            # 메뉴 재표시 (개발자 모드 활성화 시)
            if choice == 'refresh':
                continue
            
            # 종료
            if choice == '0':
                print(f"\n{Colors.OKCYAN}프로그램을 종료합니다.{Colors.ENDC}")
                break
            
            # 개발자 모드 비활성화
            if choice == '8' and app_config.dev_mode:
                print(f"\n{Colors.WARNING}✓ 개발자 모드가 비활성화되었습니다.{Colors.ENDC}")
                app_config.disable_dev_mode()
                continue
            
            # 메뉴 실행
            menu_actions = menu_actions_dev if app_config.dev_mode else menu_actions_normal
            action = menu_actions.get(choice)
            
            if action:
                try:
                    action()
                except Exception as e:
                    error_msg = str(e)
                    print(f"\n{Colors.FAIL}{'='*60}{Colors.ENDC}")
                    print(f"{Colors.FAIL}{Colors.BOLD}[오류] 작업 실행 중 예외 발생:{Colors.ENDC}")
                    print(f"{Colors.FAIL}{error_msg}{Colors.ENDC}")
                    print(f"{Colors.FAIL}{'='*60}{Colors.ENDC}")
                    
                    # Traceback을 로그 파일에만 기록 (콘솔에는 표시 안 함)
                    from core.logger import log_error
                    log_error(error_msg, exception=e, context="메뉴 작업 실행")
                    
                    # 에러 팝업 표시
                    show_popup(
                        "작업 실행 오류",
                        f"작업 실행 중 오류가 발생했습니다.\n\n"
                        f"오류: {error_msg}\n\n"
                        f"자세한 내용은 로그 파일을 확인하세요.",
                        icon=UIConstants.ICON_ERROR
                    )
                    
                    input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
            else:
                print(f"{Colors.FAIL}[오류] 알 수 없는 메뉴 선택: {choice}{Colors.ENDC}")
    
    finally:
        cleanup_temp_dirs()
        close_logger()
        restore_console_mode(original_console_mode)
        if choice != '0':
            print(f"\n{Colors.OKCYAN}{'='*60}{Colors.ENDC}")
            input(f"{Colors.BOLD}Enter 키를 누르면 종료됩니다...{Colors.ENDC}")


if __name__ == "__main__":
    main()
