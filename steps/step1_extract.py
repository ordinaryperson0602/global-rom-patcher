"""STEP 1: 기기 정보 추출 - 실제 코드"""
# 표준 라이브러리
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

# 로컬 모듈
from config.colors import Colors
from config.paths import ADB_EXE, EDL_NG_EXE, AVBTOOL_PY, LOADER_FILES, ROMFILE_PATCH_BACKUP_DIR
from config.constants import get_model_config, UIConstants, TimingConstants
from config.messages import ErrorMessages, InfoMessages, TitleMessages, WARNING_BANNER
from core.exceptions import EDLConnectionError
from core.progress import init_step_progress, update_sub_task, global_print_progress, global_end_progress
from core.context import DeviceContext
from core.logger import log_error, log_step_start, log_step_end
from utils.ui import show_popup, clear_screen
from utils.command import run_command
from utils.region_check import validate_region_code
from utils.edl_workflow import is_edl_disconnection_error, is_gpt_parsing_error, handle_gpt_parsing_error
from utils.device_utils import (
    check_adb_device_state as util_check_adb_device_state,
    get_active_slot as util_get_active_slot,
    get_device_model_info as util_get_device_model_info
)

# 모듈 레벨 컨텍스트 (전역 변수 대체)
_device_context = DeviceContext()


def _cleanup_temp_files_on_error() -> None:
    """에러 발생 시 임시 파일 정리"""
    from core.logger import info
    
    print(f"\n[정보] 임시 파일을 정리합니다...")
    
    # 1. CURRENT_DIR의 .img 파일들 삭제
    from config.paths import CURRENT_DIR
    deleted_files = []
    
    for img_file in CURRENT_DIR.glob("*.img"):
        try:
            img_file.unlink()
            deleted_files.append(img_file.name)
            print(f"  ✓ 삭제됨: {img_file.name}")
        except Exception as e:
            print(f"  ✗ 삭제 실패: {img_file.name} - {e}")
    
    # 2. output_folder 삭제
    output_folder = _device_context.get_output_folder()
    if output_folder and os.path.exists(output_folder):
        try:
            shutil.rmtree(output_folder)
            print(f"  ✓ 폴더 삭제됨: {output_folder}")
        except Exception as e:
            print(f"  ✗ 폴더 삭제 실패: {output_folder} - {e}")
    
    if deleted_files:
        info(f"임시 파일 정리 완료", deleted_count=len(deleted_files), files=deleted_files)
        print(f"[정보] 총 {len(deleted_files)}개 파일 정리 완료")


def check_edl_connection() -> bool:
    """EDL 연결 상태 확인"""
    from core.logger import info, log_validation
    
    info("EDL 연결 상태 확인 시작")
    loader_file = _device_context.get_loader()
    if not loader_file:
        log_validation("EDL 로더 파일", False, "로더 파일 미설정")
        print(f"[오류] {ErrorMessages.EDL_LOADER_NOT_SET}")
        return False
    
    log_validation("EDL 로더 파일", True, f"로더: {loader_file}")
    is_success, output, _ = run_command(
        [EDL_NG_EXE, "--loader", loader_file, "printgpt"],
        "EDL 모드 연결 확인"
    )
    
    result = is_success and "GPT Header LUN" in output
    log_validation("EDL 연결 상태", result, "GPT Header 확인됨" if result else "GPT Header 없음")
    return result


def check_adb_device_state() -> str:
    """
    ADB 기기 연결 상태 확인
    
    Note:
        내부적으로 utils.device_utils를 사용합니다.
        하위 호환성을 위해 함수 시그니처는 유지됩니다.
    """
    return util_check_adb_device_state()


def get_device_model_info() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    기기 모델 확인 및 로더 파일 설정
    
    Note:
        내부적으로 utils.device_utils를 사용합니다.
        하위 호환성을 위해 함수 시그니처는 유지됩니다.
    """
    return util_get_device_model_info()


def get_active_slot() -> Optional[str]:
    """
    활성 슬롯 확인
    
    Note:
        내부적으로 utils.device_utils를 사용합니다.
        하위 호환성을 위해 함수 시그니처는 유지됩니다.
    """
    slot_suffix = util_get_active_slot()
    if slot_suffix:
        print(f"\n[성공] 확인된 활성 슬롯: {slot_suffix}")
    return slot_suffix


def wait_for_adb_connection(current_step: int, total_steps: int) -> Tuple[Optional[str], Optional[str]]:
    """ADB 연결 대기 및 모델/슬롯 확인"""
    while True:
        update_sub_task(0, 'in_progress')
        global_print_progress(current_step, total_steps, "STEP 1")
        
        print("\n" + "="*50)
        print("[ 1단계 - 1 ] ADB 연결 상태를 확인합니다.")
        print(" * USB 디버깅이 활성화된 상태로 태블릿을 PC에 연결하십시오.")
        print("="*50 + "\n")
        
        device_state = check_adb_device_state()
        
        if device_state == "device":
            print("\n[성공] 태블릿이 'device' 상태로 정상 연결되었습니다.")
            current_step += 1
            update_sub_task(0, 'done')
            global_print_progress(current_step, total_steps, "STEP 1")
            
            # 모델 확인
            update_sub_task(1, 'in_progress')
            print("\n[정보] 연결된 장치의 모델 번호를 확인합니다...")
            model_result = get_device_model_info()
            if model_result[0] is None:
                return None, None
            
            target_model_number, model_name, loader_to_use = model_result
            current_step += 1
            update_sub_task(1, 'done')
            global_print_progress(current_step, total_steps, "STEP 1")
            
            # 슬롯 확인
            update_sub_task(2, 'in_progress')
            print("\n[정보] 연결된 장치의 활성 슬롯을 확인합니다...")
            slot_suffix = get_active_slot()
            if slot_suffix is None:
                return None, None
            
            current_step += 1
            update_sub_task(2, 'done')
            global_print_progress(current_step, total_steps, "STEP 1")
            return slot_suffix, target_model_number
        
        elif device_state == "unauthorized":
            print("\n[진단] 태블릿이 'unauthorized' (미승인) 상태입니다.")
            print("  [해결] 태블릿 화면의 'USB 디버깅 허용' 팝업에서 '허용'을 누르십시오.")
        else:
            print("\n[진단] 연결된 ADB 장치가 없습니다.")
            print("\n  [해결]")
            print("  1. 태블릿과 PC의 연결상태를 확인해주십시오.")
            print("  2. 개발자 옵션에서 'USB 디버깅'이 켜져 있는지 확인해주십시오.")
            print("  3. 설정에서 'USB 환경설정' 검색 후 'USB 사용 용도'가 '데이터 전송 안함'으로 되어 있는지 확인해주십시오.")
            print("  4. 위의 방법으로도 해결되지 않는다면, 케이블을 교체하거나 PC의 다른 USB 포트에 연결해 보십시오.")
        
        response = input("\n문제를 해결한 후, 연결을 다시 확인하려면 Enter 키를 누르십시오 (종료: 'q'): ").strip().lower()
        if response == 'q':
            print("\n[정보] 작업을 취소합니다.")
            return None, None


def enter_edl_mode(current_step: int, total_steps: int) -> bool:
    """EDL 모드 진입"""
    update_sub_task(3, 'in_progress')
    global_print_progress(current_step, total_steps, "STEP 1")
    print("\n[정보] ADB 연결, 모델 및 슬롯 확인 완료. EDL 모드로 전환합니다...")
    
    # 경고 배너 출력
    print(f"\n{Colors.FAIL}{WARNING_BANNER}{Colors.ENDC}")
    
    run_command([ADB_EXE, "reboot", "edl"], "EDL 모드 진입 명령 전송")
    wait_seconds = TimingConstants.EDL_BOOT_WAIT
    print(f"\n{Colors.WARNING}[정보] {InfoMessages.EDL_WAIT_MESSAGE.format(seconds=wait_seconds)}{Colors.ENDC}")
    time.sleep(wait_seconds)
    
    return True


def wait_for_edl_connection(current_step: int, total_steps: int) -> bool:
    """EDL 모드 연결 대기"""
    while True:
        clear_screen()
        
        update_sub_task(4, 'in_progress')
        global_print_progress(current_step, total_steps, "STEP 1")
        
        print("\n" + "="*50)
        print("[ 1단계 - 2 ] EDL 모드 연결 상태를 확인합니다.")
        print(" * 태블릿 화면이 꺼지고 PC가 장치를 인식할 때까지 기다리십시오.")
        print("="*50)
        print(f"{Colors.WARNING}{Colors.BOLD}{InfoMessages.WARNING_DO_NOT_DISCONNECT}{Colors.ENDC}")
        print("="*50 + "\n")
        
        is_success, output, _ = run_command(
            [EDL_NG_EXE, "--loader", _device_context.get_loader(), "printgpt"],
            "EDL 모드 연결 확인"
        )
        
        if is_success and "GPT Header LUN" in output:
            print("\n[성공] 태블릿이 EDL 모드로 정상 연결되었습니다.")
            return True
        else:
            print("\n[진단] EDL 모드 장치를 찾지 못했거나 통신에 실패했습니다.")
            print("  [해결] PC '장치 관리자'에서 'Qualcomm 9008' 드라이버를 확인하거나, 강제 재부팅 후 다시 시도하십시오.")
        
        if input("\n연결을 다시 확인하려면 Enter, 종료하려면 'q'를 입력하십시오: ").lower() == 'q':
            return False


def reboot_to_edl(current_step: int, total_steps: int) -> Tuple[bool, Optional[str], Optional[str]]:
    """ADB 연결, 모델 확인, EDL 모드 진입 (메인 로직)"""
    clear_screen()
    
    # 1. ADB 연결 및 모델/슬롯 확인
    slot_suffix, target_model_number = wait_for_adb_connection(current_step, total_steps)
    if slot_suffix is None:
        return False, None, None
    
    current_step = 3
    
    # 2. EDL 모드 진입
    if not enter_edl_mode(current_step, total_steps):
        return False, None, None
    
    current_step += 1
    update_sub_task(3, 'done')
    global_print_progress(current_step, total_steps, "STEP 1")
    
    # 3. EDL 연결 대기
    if not wait_for_edl_connection(current_step, total_steps):
        return False, None, None
    
    current_step += 1
    update_sub_task(4, 'done')
    global_print_progress(current_step, total_steps, "STEP 1")
    
    return True, slot_suffix, target_model_number


def extract_partition(partition_name: str, slot_suffix: str, output_dir: Optional[str] = None) -> Optional[str]:
    """파티션 추출"""
    from core.logger import info, log_extraction
    
    if partition_name in ["persist", "devinfo", "keystore"]:
        partition_to_read = partition_name
        base_output_filename = f"{partition_name}.img"
    else:
        partition_to_read = f"{partition_name}{slot_suffix}"
        base_output_filename = f"{partition_to_read}.img"
    
    if output_dir:
        output_filepath = os.path.join(output_dir, base_output_filename)
    else:
        output_filepath = base_output_filename
    
    info(f"파티션 추출 시작", partition=partition_name, slot=slot_suffix, target=partition_to_read, output=output_filepath)
    
    command = [EDL_NG_EXE, "--loader", _device_context.get_loader(), "read-part", partition_to_read, output_filepath]
    step_description = f"'{partition_to_read}' 파티션 추출"
    
    if os.path.exists(output_filepath):
        print(f"[경고] '{output_filepath}' 파일이 이미 존재합니다. 덮어씁니다.")
    
    # EDL 기기가 이전 작업을 완료하고 다음 명령을 받을 준비를 하도록 1초 대기
    time.sleep(0.5)
    
    success, error_output, _ = run_command(command, step_description)
    
    # 추출 결과 로깅
    if success and os.path.exists(output_filepath):
        file_size = os.path.getsize(output_filepath)
        log_extraction(partition_to_read, True, {"size_bytes": file_size, "output": output_filepath})
    else:
        log_extraction(partition_to_read, False, {"error": error_output[:200] if error_output else "파일 생성 실패"})
    
    if not success or not os.path.exists(output_filepath):
        # GPT 파싱 에러 확인 (최우선)
        if is_gpt_parsing_error(error_output):
            if os.path.exists(output_filepath):
                try:
                    os.remove(output_filepath)
                    print(f"[정보] 불완전한 파일 '{output_filepath}'을(를) 삭제했습니다.")
                except Exception as e:
                    print(f"[경고] 파일 삭제 실패: {e}")
                    log_error(f"파일 삭제 실패: {output_filepath}", exception=e, context="STEP 1 - 파티션 추출")
            
            output_folder = _device_context.get_output_folder()
            if output_folder and os.path.exists(output_folder):
                try:
                    shutil.rmtree(output_folder)
                    print(f"[정보] 불완전한 폴더 '{output_folder}'을(를) 삭제했습니다.")
                except Exception as e:
                    print(f"[경고] 폴더 삭제 실패: {e}")
                    log_error(f"폴더 삭제 실패: {output_folder}", exception=e, context="STEP 1 - 파티션 추출")
            
            # GPT 파싱 에러 처리 (자동 재부팅 시도)
            handle_gpt_parsing_error()
        
        # EDL 연결 끊김 확인
        if is_edl_disconnection_error(error_output):
            if os.path.exists(output_filepath):
                try:
                    os.remove(output_filepath)
                    print(f"[정보] 불완전한 파일 '{output_filepath}'을(를) 삭제했습니다.")
                except Exception as e:
                    print(f"[경고] 파일 삭제 실패: {e}")
                    log_error(f"파일 삭제 실패: {output_filepath}", exception=e, context="STEP 1 - 파티션 추출")
            
            output_folder = _device_context.get_output_folder()
            if output_folder and os.path.exists(output_folder):
                try:
                    shutil.rmtree(output_folder)
                    print(f"[정보] 불완전한 폴더 '{output_folder}'을(를) 삭제했습니다.")
                except Exception as e:
                    print(f"[경고] 폴더 삭제 실패: {e}")
                    log_error(f"폴더 삭제 실패: {output_folder}", exception=e, context="STEP 1 - 파티션 추출")
            
            print(f"\n{Colors.FAIL}{'=' * 60}{Colors.ENDC}")
            print(f"{Colors.FAIL}[오류] {ErrorMessages.EDL_DISCONNECT}{Colors.ENDC}")
            print(f"{Colors.WARNING}PC와 태블릿의 연결을 해제하고,{Colors.ENDC}")
            print(f"{Colors.WARNING}볼륨 다운 + 전원 버튼을 15초가량 눌러 강제 재부팅한 후{Colors.ENDC}")
            print(f"{Colors.WARNING}프로그램을 다시 실행하십시오.{Colors.ENDC}")
            print(f"{Colors.FAIL}{'=' * 60}{Colors.ENDC}")
            
            show_popup(
                TitleMessages.ERROR,
                ErrorMessages.EDL_DISCONNECT_DETAIL,
                icon=UIConstants.ICON_ERROR
            )
            
            raise EDLConnectionError("EDL 모드 중 PC와 태블릿의 연결이 끊겼습니다.")
        else:
            print(f"[실패] '{output_filepath}' 파일을 생성하지 못했습니다.")
            return None
    
    return output_filepath


def check_vendor_boot_region(slot_suffix: str) -> Optional[Tuple[str, str]]:
    """vendor_boot 지역 코드 확인"""
    print("\n" + "="*50)
    print(f"[ 2단계 ] vendor_boot{slot_suffix} 지역 코드(Region Code) 확인 (Hex)")
    print("="*50)
    print(f"{Colors.WARNING}{Colors.BOLD}{InfoMessages.WARNING_EDL_COMMUNICATION}{Colors.ENDC}")
    print("="*50 + "\n")
    
    filepath = extract_partition("vendor_boot", slot_suffix)
    if not filepath:
        return None
    
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        
        region_code = validate_region_code(data)
        
        # 지역 코드에 따라 메시지 출력
        if region_code in ['IPRC', 'PRC']:
            print(f"[성공] 지역 코드가 '{region_code}' (Hex)로 확인되었습니다. (내수 기기)")
        elif region_code in ['IROW', 'ROW']:
            print(f"[성공] 지역 코드가 '{region_code}' (Hex)로 확인되었습니다. (글로벌 변경된 기기)")
        else:
            print(f"[성공] 지역 코드가 '{region_code}' (Hex)로 확인되었습니다. (PASS)")
        
        return f"{region_code} (Hex)", filepath
    
    except ValueError as e:
        error_msg = str(e)
        if "혼합" in error_msg or "모두 발견" in error_msg:
            show_popup(TitleMessages.ERROR, error_msg, icon=UIConstants.ICON_ERROR)
        else:
            show_popup(TitleMessages.ERROR, ErrorMessages.REGION_NOT_FOUND, icon=UIConstants.ICON_ERROR)
        return None
    except Exception as e:
        error_msg = ErrorMessages.FILE_ANALYSIS_FAILED.format(file=filepath, error=e)
        print(f"[실패] {error_msg}")
        log_error(error_msg, exception=e, context="STEP 1 - vendor_boot 지역 코드 확인")
        return None


def check_vbmeta_props(slot_suffix: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """vbmeta 국가 코드, 모델, 롬 버전 확인"""
    print("\n" + "="*50)
    print(f"[ 3단계 ] vbmeta{slot_suffix} 국가 코드, 모델, 롬 버전 확인")
    print("="*50)
    print(f"{Colors.WARNING}{Colors.BOLD}{InfoMessages.WARNING_EDL_COMMUNICATION}{Colors.ENDC}")
    print("="*50 + "\n")
    
    filepath = extract_partition("vbmeta", slot_suffix)
    if not filepath:
        return None, None, None, None
    
    command = ["python", AVBTOOL_PY, "info_image", "--image", filepath]
    success, output, _ = run_command(command, f"avbtool.py로 '{filepath}' 분석")
    
    if not success:
        return None, None, None, None
    
    fingerprint_regex = re.compile(
        r"'[^/]+/([^/]+)/[^:]+:[^/]+/(([^:]+_(PRC|ROW))):user/release-keys'"
    )
    
    found_models = set()
    found_rom_versions = set()
    found_country_codes = set()
    fingerprint_lines_count = 0
    matched_lines_count = 0
    
    for line in output.splitlines():
        if line.strip().startswith("Prop:") and "fingerprint" in line.strip():
            fingerprint_lines_count += 1
            match = fingerprint_regex.search(line)
            
            if match:
                matched_lines_count += 1
                found_models.add(match.group(1))
                found_rom_versions.add(match.group(2))
                found_country_codes.add(match.group(4))
    
    if fingerprint_lines_count == 0:
        show_popup(
            TitleMessages.ERROR,
            ErrorMessages.VBMETA_FINGERPRINT_NOT_FOUND,
            icon=UIConstants.ICON_ERROR
        )
        return None, None, None, None
    
    if matched_lines_count == 0:
        show_popup(
            TitleMessages.ERROR,
            ErrorMessages.VBMETA_FORMAT_INVALID,
            icon=UIConstants.ICON_ERROR
        )
        return None, None, None, None
    
    prc_found = "PRC" in found_country_codes
    row_found = "ROW" in found_country_codes
    country_code = None
    
    if prc_found and not row_found:
        country_code = "PRC"
    elif row_found and not prc_found:
        country_code = "ROW"
    elif prc_found and row_found:
        show_popup(
            TitleMessages.ERROR,
            ErrorMessages.VBMETA_COUNTRY_CODE_MIXED,
            icon=UIConstants.ICON_ERROR
        )
        return None, None, None, None
    else:
        show_popup(
            TitleMessages.ERROR,
            ErrorMessages.VBMETA_COUNTRY_CODE_NOT_FOUND,
            icon=UIConstants.ICON_ERROR
        )
        return None, None, None, None
    
    model = list(found_models)[0]
    rom_version = list(found_rom_versions)[0]
    
    print(f"[성공] 모델: {model}, 국가 코드: {country_code}")
    print(f"[성공] 롬 버전: {rom_version}")
    return model, country_code, rom_version, filepath


def get_rollback_index(partition_name: str, slot_suffix: str, output_dir: str) -> str:
    """롤백 인덱스 확인"""
    from core.logger import info, log_validation
    
    partition_name_with_slot = f"{partition_name}{slot_suffix}"
    
    info(f"롤백 인덱스 확인 시작", partition=partition_name, slot=slot_suffix, target=partition_name_with_slot)
    
    print("\n" + "="*50)
    print(f"[ 4단계 ] {partition_name_with_slot} 롤백 인덱스 확인")
    print("="*50)
    print(f"{Colors.WARNING}{Colors.BOLD}{InfoMessages.WARNING_EDL_COMMUNICATION}{Colors.ENDC}")
    print("="*50 + "\n")
    
    # 파일이 이미 존재하는지 확인 (중복 추출 방지)
    expected_filename = f"{partition_name_with_slot}.img"
    expected_filepath = os.path.join(output_dir, expected_filename)
    
    if os.path.exists(expected_filepath):
        print(f"[정보] '{expected_filename}' 파일이 이미 존재합니다. 재사용합니다.")
        filepath = expected_filepath
    else:
        filepath = extract_partition(partition_name, slot_suffix, output_dir)
        if not filepath:
            return "EXTRACTION_FAILURE"
    
    command = ["python", AVBTOOL_PY, "info_image", "--image", filepath]
    success, output, _ = run_command(command, f"avbtool.py로 '{filepath}' 분석")
    
    if not success:
        return "AVBTOOL_FAILURE"
    
    rollback_regex = re.compile(r"Rollback Index:\s*(\d+)")
    match = rollback_regex.search(output)
    
    if match:
        index = match.group(1)
        log_validation(f"롤백 인덱스 ({partition_name_with_slot})", True, f"Rollback Index: {index}")
        info(f"롤백 인덱스 추출 성공", partition=partition_name_with_slot, rollback_index=index)
        print(f"[성공] {partition_name_with_slot} 롤백 인덱스: {index}")
        return index
    else:
        log_validation(f"롤백 인덱스 ({partition_name_with_slot})", False, "Rollback Index 없음")
        print(f"[실패] {partition_name_with_slot}에서 롤백 인덱스를 찾을 수 없습니다.")
        return "NOT_FOUND"


def save_device_info_to_file(region_code: str, model: str, country_code: str, rom_version: str,
                             vbmeta_system_rb: str, boot_rb: str, current_slot: str,
                             output_dir: str, timestamp: str) -> bool:
    """기기 정보를 txt 파일로 저장"""
    print("\n" + "="*50)
    print("[ 5단계 ] 정보 파일로 저장")
    print("="*50)
    
    output_filename = f"Device_Info_{model or 'UNKNOWN'}_{timestamp}.txt"
    output_filepath = os.path.join(output_dir, output_filename)
    
    slot_display = current_slot.replace('_', '')
    
    content = (
        f"=== 장치 분석 정보 ===\n"
        f"분석 시간: {timestamp}\n"
        f"{'='*20}\n"
        f"1. 모델 번호 (vbmeta Prop): {model}\n"
        f"2. 롬 버전 (vbmeta Prop): {rom_version}\n"
        f"3. 지역 코드 (vendor_boot Hex): {region_code}\n"
        f"4. 국가 코드 (vbmeta Prop): {country_code}\n"
        f"5. vbmeta_system 롤백 인덱스: {vbmeta_system_rb}\n"
        f"6. boot 롤백 인덱스: {boot_rb}\n"
        f"7. current-slot: {slot_display}\n"
    )
    
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[성공] 장치 정보를 '{output_filepath}' 파일에 저장했습니다.")
        return True
    except Exception as e:
        print(f"[실패] 정보 파일 저장 중 오류: {e}")
        return False


def reboot_device_from_edl() -> bool:
    """EDL 모드에서 장치 재부팅"""
    print("\n" + "="*50)
    print("[ 7단계 ] 장치 재부팅")
    print("="*50)
    loader_file = _device_context.get_loader()
    if loader_file:
        run_command([EDL_NG_EXE, "--loader", loader_file, "reset"], "장치 재부팅")
        return True
    else:
        print("\n[정보] 모델이 확인되지 않아 EDL 재부팅을 건너뜁니다.")
        return False


# Helper Functions (리팩토링)
def _check_vendor_boot_and_vbmeta(slot_suffix: str, target_model_number: str, 
                                   step1_current_step: int, step1_total_steps: int) -> Tuple[Dict[str, str], Dict[str, str], int]:
    """Task 5-6: vendor_boot과 vbmeta 확인"""
    device_info = {
        "region_code": "N/A", "model": "N/A", "country_code": "N/A",
        "rom_version": "N/A", "vbmeta_system_rb": "N/A", "boot_rb": "N/A",
        "current_slot": slot_suffix
    }
    temp_files_to_move = {}
    
    # Task 5: vendor_boot 확인
    update_sub_task(5, 'in_progress')
    global_print_progress(step1_current_step, step1_total_steps, "STEP 1")
    result = check_vendor_boot_region(slot_suffix)
    if result is None:
        raise Exception("vendor_boot 지역 코드 확인 실패 또는 NG")
    region_code, vendor_boot_temp_path = result
    device_info["region_code"] = region_code
    temp_files_to_move[os.path.basename(vendor_boot_temp_path)] = vendor_boot_temp_path
    step1_current_step += 1
    update_sub_task(5, 'done')
    global_print_progress(step1_current_step, step1_total_steps, "STEP 1")
    
    # Task 6: vbmeta 확인
    update_sub_task(6, 'in_progress')
    global_print_progress(step1_current_step, step1_total_steps, "STEP 1")
    result = check_vbmeta_props(slot_suffix)
    model, country_code, rom_version, vbmeta_temp_path = result
    if model is None:
        raise Exception("vbmeta 확인 실패")
    device_info["model"] = model
    device_info["country_code"] = country_code
    device_info["rom_version"] = rom_version
    temp_files_to_move[os.path.basename(vbmeta_temp_path)] = vbmeta_temp_path
    step1_current_step += 1
    update_sub_task(6, 'done')
    global_print_progress(step1_current_step, step1_total_steps, "STEP 1")
    
    # 모델 번호 검증
    if model != target_model_number:
        show_popup(
            TitleMessages.ERROR,
            ErrorMessages.MODEL_MISMATCH.format(
                adb_model=target_model_number,
                vbmeta_model=model
            ),
            icon=UIConstants.ICON_ERROR
        )
        raise Exception("모델 불일치")
    
    return device_info, temp_files_to_move, step1_current_step


def _extract_rollback_and_additional_partitions(slot_suffix: str, output_dir_path: str, 
                                                 temp_files_to_move: Dict[str, str],
                                                 device_info: Dict[str, str],
                                                 step1_current_step: int, step1_total_steps: int) -> int:
    """Task 7: 롤백 인덱스 확인 및 추가 파티션 추출"""
    update_sub_task(7, 'in_progress')
    global_print_progress(step1_current_step, step1_total_steps, "STEP 1")
    
    # 임시 파일 이동
    print("\n[정보] 임시 추출 파일 이동 중...")
    for dest_filename, src_path in temp_files_to_move.items():
        if src_path and os.path.exists(src_path):
            dest_path = os.path.join(output_dir_path, dest_filename)
            try:
                shutil.move(src_path, dest_path)
                print(f"  - {src_path} -> {dest_path} 이동 완료.")
            except Exception as e:
                error_msg = f"{src_path} 이동 실패: {e}"
                print(f"  - [오류] {error_msg}")
                log_error(error_msg, exception=e, context="STEP 1 - 파일 이동")
        else:
            print(f"  - [경고] {dest_filename}의 원본({src_path})을 찾을 수 없어 이동 생략.")
    
    # 롤백 인덱스 추출
    device_info["vbmeta_system_rb"] = get_rollback_index("vbmeta_system", slot_suffix, output_dir_path)
    device_info["boot_rb"] = get_rollback_index("boot", slot_suffix, output_dir_path)
    
    # 추가 파티션 추출
    print("\n[정보] 추가 파티션 추출 중...")
    extract_partition("persist", slot_suffix, output_dir_path)
    extract_partition("devinfo", slot_suffix, output_dir_path)
    extract_partition("keystore", slot_suffix, output_dir_path)
    
    step1_current_step += 1
    update_sub_task(7, 'done')
    global_print_progress(step1_current_step, step1_total_steps, "STEP 1")
    
    return step1_current_step


def _save_device_info_and_validate(device_info: Dict[str, str], output_dir_path: str, 
                                    timestamp: str, step1_current_step: int, 
                                    step1_total_steps: int) -> Tuple[str, Dict[str, str], str, int]:
    """Task 8: 기기 정보 저장 및 검증"""
    update_sub_task(8, 'in_progress')
    global_print_progress(step1_current_step, step1_total_steps, "STEP 1")
    
    save_device_info_to_file(
        device_info["region_code"], device_info["model"],
        device_info["country_code"], device_info["rom_version"],
        device_info["vbmeta_system_rb"], device_info["boot_rb"],
        device_info["current_slot"],
        output_dir_path, timestamp
    )
    
    print("\n[성공] 모든 정보 추출 및 저장을 완료했습니다.")
    step1_current_step += 1
    update_sub_task(8, 'done')
    global_print_progress(step1_current_step, step1_total_steps, "STEP 1")
    
    device_rollback_indices = {
        'boot': device_info["boot_rb"],
        'vbmeta_system': device_info["vbmeta_system_rb"]
    }
    
    # 롤백 인덱스 검증
    try:
        int(device_rollback_indices['boot'])
        int(device_rollback_indices['vbmeta_system'])
    except ValueError:
        error_msg = ErrorMessages.ROLLBACK_INDEX_INVALID.format(indices=device_rollback_indices)
        print(f"[오류] {error_msg}")
        show_popup(
            TitleMessages.ERROR,
            error_msg,
            icon=UIConstants.ICON_ERROR
        )
        raise Exception("롤백 인덱스 파싱 실패")
    
    return device_info["model"], device_rollback_indices, output_dir_path, step1_current_step



def run_step_1() -> Tuple[Optional[str], Optional[Dict[str, str]], Optional[str]]:
    """STEP 1 메인 로직 - 리팩토링 버전"""
    
    step1_total_steps = 10
    step1_current_step = 0
    
    task_names = [
        "ADB 연결 확인",
        "모델 번호 확인",
        "활성 슬롯 확인",
        "EDL 모드 진입",
        "EDL 모드 연결",
        "vendor_boot 확인",
        "vbmeta 확인",
        "롤백 인덱스 확인",
        "정보 파일 저장",
        "기기 재부팅"
    ]
    init_step_progress(1, step1_total_steps, task_names)
    
    # Task 0-4: EDL 모드 진입
    edl_success, slot_suffix, target_model_number = reboot_to_edl(step1_current_step, step1_total_steps)
    if not edl_success:
        return None, None, None
    
    step1_current_step = 5
    output_dir_path = None
    
    try:
        # Task 5-6: vendor_boot과 vbmeta 확인
        device_info, temp_files_to_move, step1_current_step = _check_vendor_boot_and_vbmeta(
            slot_suffix, target_model_number, step1_current_step, step1_total_steps
        )
        
        # 출력 폴더 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_folder_name = f"{timestamp}_Backup"
        ROMFILE_PATCH_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        output_dir_path = str(ROMFILE_PATCH_BACKUP_DIR / output_folder_name)
        _device_context.set_output_folder(Path(output_dir_path))
        
        print(f"\n[정보] 출력 폴더 생성 시도: {output_dir_path}")
        os.makedirs(output_dir_path, exist_ok=True)
        print(f"[성공] 출력 폴더 준비 완료.")
        
        # Task 7: 롤백 인덱스 확인 및 추가 파티션 추출
        step1_current_step = _extract_rollback_and_additional_partitions(
            slot_suffix, output_dir_path, temp_files_to_move, device_info, 
            step1_current_step, step1_total_steps
        )
        
        # Task 8: 기기 정보 저장 및 검증
        model, device_rollback_indices, output_dir_path, step1_current_step = _save_device_info_and_validate(
            device_info, output_dir_path, timestamp, step1_current_step, step1_total_steps
        )
        
        return model, device_rollback_indices, output_dir_path
    
    except EDLConnectionError as e:
        print(f"\n[정보] EDL 연결 끊김으로 인해 메뉴로 돌아갑니다.")
        _cleanup_temp_files_on_error()
        return None, None, None
    except Exception as e:
        error_msg = f"프로그램 실행 중 중단되었습니다: {e}"
        print(f"\n[오류] {error_msg}")
        log_error(error_msg, exception=e, context="STEP 1 - 전체 실행")
        _cleanup_temp_files_on_error()
        show_popup(
            "STEP 1 오류 - NG",
            f"{error_msg}\n\n로그 파일을 확인하세요.",
            icon=UIConstants.ICON_ERROR
        )
        return None, None, None
    finally:
        # Task 9: 기기 재부팅
        update_sub_task(9, 'in_progress')
        global_print_progress(step1_current_step, step1_total_steps, "STEP 1")
        try:
            reboot_device_from_edl()
        except EDLConnectionError:
            print("[정보] EDL 연결이 끊겨 재부팅 명령을 건너뜁니다.")
        except Exception as e:
            error_msg = f"재부팅 명령 실패: {e}"
            print(f"[경고] {error_msg}")
            log_error(error_msg, exception=e, context="STEP 1 - 재부팅")
        step1_current_step += 1
        update_sub_task(9, 'done')
        global_print_progress(step1_current_step, step1_total_steps, "STEP 1")
        global_end_progress()


