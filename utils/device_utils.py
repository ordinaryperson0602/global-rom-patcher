"""기기 연결 관련 공통 유틸리티

이 모듈은 ADB 및 EDL 연결에 필요한 공통 함수를 제공합니다.
기존 코드와 100% 호환되며, 중복을 제거하기 위해 추출되었습니다.
"""
from typing import Tuple, Optional
from src.config import ADB_EXE
from src.config import ErrorMessages
from src.config import Colors
from utils.command import run_command


def check_adb_device_state() -> str:
    """
    ADB 기기 상태 확인
    
    Returns:
        "device", "unauthorized", "not_found" 중 하나
    
    Note:
        - steps/step1_extract.py의 check_adb_device_state()와 동일
        - utils/edl_workflow.py의 check_adb_device_state()와 동일
    """
    success, output, _ = run_command([str(ADB_EXE), "devices"], "ADB 장치 검색")
    
    if not success or len(output.strip().splitlines()) <= 1:
        return "not_found"
    
    device_info = output.strip().splitlines()[1]
    
    if "unauthorized" in device_info:
        return "unauthorized"
    elif "device" in device_info:
        return "device"
    else:
        return "not_found"


def get_active_slot() -> Optional[str]:
    """
    활성 슬롯 확인 (ADB 사용)
    
    Returns:
        "_a" 또는 "_b", 실패 시 None
    
    Note:
        - steps/step1_extract.py의 get_active_slot()과 동일
        - 실패 시 사용자에게 메시지 출력 및 입력 대기
    """
    is_success_slot, output_slot, _ = run_command(
        [str(ADB_EXE), "shell", "getprop", "ro.boot.slot_suffix"],
        "활성 슬롯 확인"
    )
    
    if not is_success_slot:
        print(f"\n[실패] {ErrorMessages.ADB_SLOT_CHECK_FAILED}")
        input("Enter를 눌러 종료합니다.")
        return None
    
    slot_suffix = output_slot.strip()
    
    if slot_suffix not in ["_a", "_b"]:
        print(f"\n[실패] {ErrorMessages.ADB_SLOT_INVALID.format(slot=slot_suffix)}")
        input("Enter를 눌러 종료합니다.")
        return None
    
    return slot_suffix


def get_device_model_info() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    기기 모델 확인 및 로더 파일 설정 (ADB 사용)
    
    Returns:
        (model_prop, model_name, loader_to_use) 또는 실패 시 (None, None, None)
    
    Note:
        - steps/step1_extract.py의 get_device_model_info()와 동일
        - 사용자 확인 프롬프트 포함
        - DeviceContext에 로더 설정은 호출자가 수행
    """
    from config.constants import UIConstants, get_model_config
    from config.messages import TitleMessages, InfoMessages
    from utils.ui import show_popup
    from core.context import DeviceContext
    import os
    
    # 전역 DeviceContext 인스턴스 사용
    from steps.step1_extract import _device_context
    
    is_success_model, output_model, _ = run_command(
        [str(ADB_EXE), "shell", "getprop", "ro.product.model"],
        "모델 번호 확인"
    )
    
    if not is_success_model:
        print(f"\n[실패] {ErrorMessages.ADB_MODEL_CHECK_FAILED}")
        input("Enter를 눌러 종료합니다.")
        return None, None, None
    
    model_prop = output_model.strip()
    model_config = get_model_config()
    
    if model_prop not in model_config:
        show_popup(
            TitleMessages.ERROR, 
            ErrorMessages.MODEL_UNSUPPORTED.format(model=model_prop), 
            icon=UIConstants.ICON_ERROR
        )
        input("Enter를 눌러 종료합니다.")
        return None, None, None
    
    model_name = model_config[model_prop]["name"]
    loader_to_use = model_config[model_prop]["loader"]
    
    # 사용자 확인
    while True:
        answer = input(
            f"{Colors.WARNING}\n[확인] "
            f"{InfoMessages.DEVICE_MODEL_CONFIRM.format(model_name=model_name)} (y/n): {Colors.ENDC}"
        ).strip().lower()
        if answer == 'y':
            _device_context.set_loader(loader_to_use)
            print(f"[정보] 로더 파일을 '{os.path.basename(loader_to_use)}'(으)로 설정합니다.")
            
            if not os.path.exists(loader_to_use):
                show_popup(
                    TitleMessages.ERROR,
                    ErrorMessages.MODEL_LOADER_NOT_FOUND.format(
                        model=model_prop,
                        loader_path=loader_to_use
                    ),
                    icon=UIConstants.ICON_ERROR
                )
                input("Enter를 눌러 종료합니다.")
                return None, None, None
            break
        elif answer == 'n':
            print("\n[정보] 작업이 취소되었습니다.")
            input("Enter를 눌러 종료합니다.")
            return None, None, None
        else:
            print(f"{Colors.FAIL}y 또는 n을 입력하세요.{Colors.ENDC}")
    
    return model_prop, model_name, loader_to_use

