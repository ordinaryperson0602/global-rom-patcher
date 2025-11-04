"""STEP 2-Custom: 사용자 지정 롬파일 분석 및 검증

이 패키지는 사용자가 지정한 롬파일(RSA 다운로드 폴더 외부)을 분석하고
패치할 수 있도록 준비하는 기능을 제공합니다.

모듈 구성:
- rsa_folder: RSA 폴더 준비 및 이동
- rom_selection: 롬파일 선택 및 폴더 구조 분석
- rom_detection: 롬 타입 자동 감지 (글로벌/내수)
- rom_validation: 롬파일 구조 및 모델 호환성 검증
- patch_folder: 패치용 폴더 생성
- rollback_index: 롤백 인덱스 추출 및 정보 저장
"""
import traceback
from typing import Tuple, Optional, Dict

from config.colors import Colors
from config.constants import UIConstants
from config.messages import TitleMessages
from core.logger import log_error
from core.progress import (
    init_standalone_progress, update_standalone_task,
    print_standalone_progress, end_standalone_progress
)
from utils.ui import show_popup

# 하위 모듈에서 필요한 함수들 import
from .rsa_folder import (
    check_and_prepare_rsa_folder,
    input_rsa_folder_name,
    move_to_rsa_folder,
    show_rsa_flash_guide
)
from .rom_selection import (
    select_rom_folder,
    find_actual_rom_path
)
from .rom_detection import detect_rom_type
from .rom_validation import (
    validate_rom_structure,
    verify_model_compatibility
)
from .patch_folder import create_patch_folder
from .rollback_index import (
    extract_rollback_indices,
    save_custom_rom_info_to_file
)


# 공개 API
__all__ = [
    'run_step_2_custom',
    'check_and_prepare_rsa_folder',
    'input_rsa_folder_name',
    'move_to_rsa_folder',
    'show_rsa_flash_guide',
]


# ============================================================================
# Helper Functions (리팩토링)
# ============================================================================

def _select_rom_with_retry() -> Optional[str]:
    """롬파일 선택 (재시도 가능)"""
    selected_path = None
    while not selected_path:
        selected_path = select_rom_folder()
        if not selected_path:
            print(f"\n{Colors.WARNING}{'='*60}{Colors.ENDC}")
            retry = input(f"{Colors.WARNING}다시 선택하시겠습니까? (y: 다시 선택 / n: 메인 메뉴로): {Colors.ENDC}").strip().lower()
            if retry != 'y':
                print(f"\n{Colors.OKCYAN}메인 메뉴로 돌아갑니다.{Colors.ENDC}")
                return None
    return selected_path


def _find_and_verify_rom_structure(selected_path: str) -> Tuple[Optional[str], Optional[bool]]:
    """롬파일 구조 확인"""
    rom_path, is_nested = find_actual_rom_path(selected_path)
    if not rom_path:
        print(f"\n{Colors.FAIL}[오류] 올바른 롬파일 구조를 찾을 수 없습니다.{Colors.ENDC}")
        print(f"{Colors.WARNING}image 폴더가 있는 롬파일을 선택하세요.{Colors.ENDC}")
        input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
        return None, None
    return rom_path, is_nested


def _detect_rom_type_with_error_handling(rom_path: str, target_model: str) -> Tuple[Optional[str], Optional[Dict]]:
    """롬 타입 감지 (에러 처리 포함)"""
    try:
        rom_type, rom_info = detect_rom_type(rom_path, target_model)
        return rom_type, rom_info
    except Exception as e:
        error_message = str(e)
        print(f"\n{Colors.FAIL}[NG] {error_message}{Colors.ENDC}")
        
        show_popup(
            TitleMessages.ERROR,
            f"롬파일 분석 실패 (NG)\n\n"
            f"{error_message}\n\n"
            f"올바른 롬파일을 선택하세요.",
            exit_on_close=False,
            icon=UIConstants.ICON_ERROR
        )
        
        log_error(f"롬 타입 감지 실패: {error_message}", exception=e, context="STEP 2-Custom - 롬 타입 감지")
        input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
        return None, None


def _validate_rom_structure_with_error(rom_path: str, rom_type: str) -> bool:
    """롬 구조 검증"""
    is_valid, error_msg = validate_rom_structure(rom_path, rom_type)
    if not is_valid:
        print(f"\n{Colors.FAIL}[오류] {error_msg}{Colors.ENDC}")
        input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
    return is_valid


# ============================================================================
# Main Function
# ============================================================================

def run_step_2_custom(target_model: str, step1_output_dir: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[Dict], Optional[Dict[str, str]]]:
    """
    STEP 2-Custom 메인 실행 함수
    
    Args:
        target_model: 기기 모델 번호
        step1_output_dir: STEP 1 백업 폴더 경로 (정보 파일 저장용)
    
    Returns:
        (patch_path, rom_type, rom_info, rom_indices) 또는 실패 시 (None, None, None, None)
        - patch_path: 패치용 폴더 경로 (_PATCH), 원본은 그대로 유지됨
        - rom_type: 'global' 또는 'china'
        - rom_info: 롬파일 정보 딕셔너리
        - rom_indices: 롤백 인덱스 정보
    """
    from core.logger import info
    
    info(f"STEP 2-Custom 시작", target_model=target_model)
    
    # 진행률 초기화
    task_names = [
        "롬파일 선택",
        "폴더 구조 분석",
        "롬파일 이름 확인",
        "vbmeta Prop 확인",
        "vendor_boot Hex 확인",
        "vbmeta_system 롤백 확인",
        "boot 롤백 확인",
        "검증 정보 저장",
        "패치용 폴더 생성"
    ]
    
    init_standalone_progress("STEP 2-Custom", task_names, overall_step=(2, 4))
    
    try:
        # 1. 롬파일 선택 (취소 시 재선택 가능)
        update_standalone_task(0, 'in_progress')
        print_standalone_progress()
        
        selected_path = _select_rom_with_retry()
        if not selected_path:
            end_standalone_progress()
            return None, None, None, None
        
        update_standalone_task(0, 'done')
        print_standalone_progress()
        
        # 2. 실제 image 폴더가 있는 경로 찾기 (중첩 구조 처리)
        update_standalone_task(1, 'in_progress')
        print_standalone_progress()
        
        rom_path, is_nested = _find_and_verify_rom_structure(selected_path)
        if not rom_path:
            update_standalone_task(1, 'error')
            print_standalone_progress()
            end_standalone_progress()
            return None, None, None, None
        
        update_standalone_task(1, 'done')
        print_standalone_progress()
        
        # 3. 롬파일 이름 확인 (1차 검증: 폴더명으로 모델 확인)
        update_standalone_task(2, 'in_progress')
        print_standalone_progress()
        
        if not verify_model_compatibility(target_model, rom_path):
            update_standalone_task(2, 'error')  # 롬파일 이름 확인 실패
            # 나머지는 실행 안 됨 (pending 유지)
            print_standalone_progress()
            end_standalone_progress()
            return None, None, None, None
        
        update_standalone_task(2, 'done')
        print_standalone_progress()
        
        # 4-5. vbmeta Prop 확인 + vendor_boot Hex 확인 (롬 타입 감지 + 2차 검증)
        update_standalone_task(3, 'in_progress')
        print_standalone_progress()
        
        rom_type, rom_info = _detect_rom_type_with_error_handling(rom_path, target_model)
        if not rom_type:
            update_standalone_task(3, 'error')
            print_standalone_progress()
            end_standalone_progress()
            return None, None, None, None
        
        update_standalone_task(3, 'done')
        update_standalone_task(4, 'done')
        print_standalone_progress()
        
        # 구조 검증 (UI 표시 없이 백그라운드 실행)
        if not _validate_rom_structure_with_error(rom_path, rom_type):
            update_standalone_task(5, 'error')
            update_standalone_task(6, 'error')
            update_standalone_task(7, 'error')
            update_standalone_task(8, 'error')
            print_standalone_progress()
            end_standalone_progress()
            return None, None, None, None
        
        # 5-6. vbmeta_system 롤백 확인 + boot 롤백 확인 (롤백 인덱스 추출)
        update_standalone_task(5, 'in_progress')
        print_standalone_progress()
        
        rom_indices = extract_rollback_indices(rom_path)
        
        update_standalone_task(5, 'done')  # vbmeta_system 롤백 확인
        update_standalone_task(6, 'done')  # boot 롤백 확인
        print_standalone_progress()
        
        # 7. 검증 정보 저장
        update_standalone_task(7, 'in_progress')
        print_standalone_progress()
        
        save_custom_rom_info_to_file(rom_path, rom_type, target_model, rom_indices, step1_output_dir)
        
        update_standalone_task(7, 'done')
        print_standalone_progress()
        
        # 8. 패치용 폴더 생성 (원본은 유지, 중첩 구조는 정상화)
        update_standalone_task(8, 'in_progress')
        print_standalone_progress()
        
        patch_path = create_patch_folder(rom_path, selected_path, is_nested)
        if not patch_path:
            update_standalone_task(8, 'error')
            print_standalone_progress()
            print(f"\n{Colors.FAIL}[오류] 패치용 폴더 생성 실패. 작업을 중단합니다.{Colors.ENDC}")
            input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
            end_standalone_progress()
            return None, None, None, None
        
        update_standalone_task(8, 'done')
        print_standalone_progress()
        
        # 완료
        end_standalone_progress()
        print(f"\n{Colors.OKGREEN}{'='*50}{Colors.ENDC}")
        print(f"{Colors.OKGREEN}✓ STEP 2-Custom 완료!{Colors.ENDC}")
        print(f"{Colors.OKGREEN}{'='*50}{Colors.ENDC}")
        
        # patch_path를 반환 (STEP 3에서 패치할 경로)
        return patch_path, rom_type, rom_info, rom_indices
    
    except Exception as e:
        end_standalone_progress()
        print(f"\n{Colors.FAIL}[오류] STEP 2-Custom 실행 중 예외 발생: {e}{Colors.ENDC}")
        log_error(f"STEP 2-Custom 실패: {e}", exception=e, context="STEP 2-Custom")
        input(f"\n{Colors.WARNING}Enter 키를 눌러 계속...{Colors.ENDC}")
        return None, None, None, None

