"""기기 정보 백업 유틸리티

7개 파티션을 추출하여 기기 정보를 분석한 후, persist, devinfo, keystore를 백업합니다.
"""
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Tuple

from src.config import Colors
from src.config import CURRENT_DIR, DEVICE_STATE_BACKUP_DIR
from src.config import UIConstants, PartitionConstants
from src.config import TitleMessages, ErrorMessages
from src.exceptions import (
    EDLConnectionError,
    LoaderNotFoundError,
    UserCancelledError,
    SlotInfoError,
    EDLModeEntryError,
    EDLConnectionFailedError,
    PartitionOperationError,
    RegionCodeCheckError,
    ModelInfoCheckError
)
from utils.ui import show_popup
from utils.edl_workflow import EDLWorkflow

# STEP1에서 재사용할 함수들을 import
from steps.step1_extract import (
    extract_partition,
    check_vendor_boot_region,
    check_vbmeta_props,
    get_rollback_index,
    save_device_info_to_file,
    _device_context
)


# Helper Functions (리팩토링)
def _extract_all_partitions(workflow: 'EDLWorkflow', slot_suffix: str, output_dir: Path) -> Dict[str, Path]:
    """Task 3: 7개 파티션 추출"""
    from core.logger import info, log_extraction
    
    info(
        f"백업용 파티션 추출 시작",
        slot=slot_suffix,
        output_dir=str(output_dir),
        partition_count=len(PartitionConstants.ALL_PARTITIONS)
    )
    
    print(f"\n[정보] 7개 파티션을 추출합니다...\n")
    print(f"[정보] 출력 폴더: {output_dir}")
    print(f"[성공] 출력 폴더 준비 완료.\n")
    
    extracted_files = {}
    for partition in PartitionConstants.ALL_PARTITIONS:
        print(f"[정보] '{partition}{slot_suffix}' 추출 시도...")
        
        try:
            filepath = extract_partition(partition, slot_suffix, str(output_dir))
            if not filepath:
                log_extraction(partition, False, {"error": "파일 경로 없음"})
                raise PartitionOperationError(partition, "추출")
            
            extracted_files[partition] = Path(filepath)
            file_size = Path(filepath).stat().st_size
            log_extraction(partition, True, {"size_bytes": file_size, "path": filepath})
            print(f"[성공] {filepath} ({file_size:,} bytes)")
        except EDLConnectionError as edl_err:
            print(f"\n{Colors.FAIL}[!!!] EDL 연결 끊김 감지!{Colors.ENDC}")
            raise edl_err
    
    workflow.next_task('done')
    return extracted_files


def _analyze_device_info(
    workflow: 'EDLWorkflow',
    slot_suffix: str,
    output_dir: Path,
    timestamp: str
) -> Tuple[str, str, str, str, str, str]:
    """Task 4: 기기 정보 분석"""
    from core.logger import info
    
    info(f"백업용 기기 정보 분석 시작", slot=slot_suffix)
    print(f"\n[정보] 기기 정보를 분석합니다...\n")
    
    # vendor_boot에서 지역 코드 확인
    region_result = check_vendor_boot_region(slot_suffix)
    if not region_result:
        raise RegionCodeCheckError(ErrorMessages.REGION_CODE_CHECK_FAILED)
    region_code, _ = region_result
    info(f"지역 코드 확인됨", region_code=region_code)
    
    # vbmeta에서 국가 코드, 모델, 롬 버전 확인
    model, country_code, rom_version, _ = check_vbmeta_props(slot_suffix)
    if not model:
        raise ModelInfoCheckError(ErrorMessages.MODEL_INFO_CHECK_FAILED)
    info(f"모델 정보 확인됨", model=model, country_code=country_code, rom_version=rom_version)
    
    # vbmeta_system, boot 롤백 인덱스 확인
    vbmeta_system_rb = get_rollback_index("vbmeta_system", slot_suffix, str(output_dir))
    boot_rb = get_rollback_index("boot", slot_suffix, str(output_dir))
    
    # 기기 정보 txt 파일 생성
    save_device_info_to_file(
        region_code, model, country_code, rom_version,
        vbmeta_system_rb, boot_rb, slot_suffix,
        str(output_dir), timestamp
    )
    
    workflow.next_task('done')
    return region_code, model, country_code, rom_version, vbmeta_system_rb, boot_rb


def _create_backup(workflow: 'EDLWorkflow', extracted_files: Dict[str, Path], 
                   output_dir: Path, model: str, timestamp: str) -> Path:
    """Task 5: 백업 생성 (persist, devinfo, txt만)"""
    print(f"\n[정보] 백업을 생성합니다...\n")
    
    # 백업 폴더 생성
    DEVICE_STATE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_dir = DEVICE_STATE_BACKUP_DIR / f"{timestamp}_Backup"
    backup_dir.mkdir(exist_ok=True)
    
    print(f"[정보] 백업 폴더: {backup_dir}\n")
    
    # persist와 devinfo만 백업
    for partition in PartitionConstants.BACKUP_PARTITIONS:
        source_file = extracted_files[partition]
        backup_file = backup_dir / f"{partition}_backup.img"
        
        shutil.copy(source_file, backup_file)
        print(f"  - {source_file.name} → {backup_file.name} 이동 완료.")
    
    # txt 파일도 백업
    txt_file = output_dir / f"Device_Info_{model}_{timestamp}.txt"
    if txt_file.exists():
        backup_txt = backup_dir / txt_file.name
        shutil.copy(txt_file, backup_txt)
        print(f"  - {txt_file.name} → {backup_txt.name} 이동 완료.")
    
    print(f"\n[성공] 백업 완료")
    workflow.next_task('done')
    
    return backup_dir


def _cleanup_temp_files(output_dir: Path, slot_suffix: str) -> None:
    """임시 파일 정리"""
    # Device_Info 임시 폴더 정리
    if output_dir and output_dir.exists():
        try:
            shutil.rmtree(output_dir)
            print(f"[정보] 임시 폴더 '{output_dir.name}'을(를) 삭제했습니다.")
        except Exception as e:
            print(f"[경고] 임시 폴더 삭제 실패: {e}")
    
    # 스크립트 경로에 남아있는 임시 .img 파일 정리
    if slot_suffix:
        temp_files_to_clean = [
            f"vendor_boot{slot_suffix}.img",
            f"vbmeta{slot_suffix}.img",
            f"vbmeta_system{slot_suffix}.img",
            f"boot{slot_suffix}.img"
        ]
        
        cleaned = False
        for temp_file in temp_files_to_clean:
            temp_path = CURRENT_DIR / temp_file
            if temp_path.exists():
                if not cleaned:
                    print(f"\n[정보] 임시 파일 정리 중...")
                    cleaned = True
                try:
                    temp_path.unlink()
                    print(f"  → {temp_file} 삭제")
                except Exception as e:
                    print(f"  → [경고] {temp_file} 삭제 실패: {e}")


def run_backup() -> bool:
    """기기 고유 정보 백업 프로세스 - 리팩토링 버전"""
    
    # 진행 작업 정의
    tasks = [
        "ADB 연결 확인",
        "EDL 모드 진입",
        "EDL 연결 확인",
        "7개 파티션 추출",
        "기기 정보 분석",
        "백업 생성",
        "완료"
    ]
    
    workflow = EDLWorkflow("기기 정보 백업", tasks)
    workflow.initialize()
    
    print(f"\n{Colors.HEADER}{'━'*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}       기기 고유 정보 백업{Colors.ENDC}")
    print(f"{Colors.HEADER}{'━'*60}{Colors.ENDC}\n")
    
    slot_suffix = None
    output_dir = None
    backup_dir = None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        # 로더 파일 설정
        if not workflow.setup_loader():
            raise LoaderNotFoundError(ErrorMessages.EDL_LOADER_NOT_FOUND)
        
        # DeviceContext에 로더 설정
        _device_context.set_loader(str(workflow.loader_path))
        
        # Task 0: ADB 연결 확인
        if not workflow.connect_adb():
            raise UserCancelledError(ErrorMessages.USER_CANCELLED)
        workflow.next_task('done')
        
        # ⭐ 슬롯 정보 가져오기 (EDL 진입 전에 확인!)
        from utils.device_utils import get_active_slot
        print(f"\n[정보] 활성 슬롯을 확인합니다...")
        slot_suffix = get_active_slot()
        if slot_suffix:
            print(f"[성공] 확인된 활성 슬롯: {slot_suffix}")
        if slot_suffix is None:
            raise SlotInfoError(ErrorMessages.SLOT_INFO_UNAVAILABLE)
        
        # Task 1: EDL 모드 진입
        if not workflow.enter_edl_mode():
            raise EDLModeEntryError(ErrorMessages.EDL_MODE_ENTRY_FAILED)
        workflow.next_task('done')
        
        # Task 2: EDL 연결 확인
        if not workflow.confirm_edl_connection():
            raise EDLConnectionFailedError(ErrorMessages.EDL_CONNECTION_FAILED)
        workflow.next_task('done')
        
        # Device_Info 폴더 생성
        output_dir = CURRENT_DIR / f"Device_Info_{timestamp}"
        output_dir.mkdir(exist_ok=True)
        _device_context.set_output_folder(output_dir)
        
        # Task 3: 7개 파티션 추출
        extracted_files = _extract_all_partitions(workflow, slot_suffix, output_dir)
        
        # Task 4: 기기 정보 분석
        region_code, model, country_code, rom_version, vbmeta_system_rb, boot_rb = _analyze_device_info(
            workflow, slot_suffix, output_dir, timestamp
        )
        
        # Task 5: 백업 생성
        backup_dir = _create_backup(workflow, extracted_files, output_dir, model, timestamp)
        
        # Task 6: 완료
        workflow.next_task('done')
        
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        print(f"{Colors.OKGREEN}{Colors.BOLD}  ✓ 백업 프로세스가 완료되었습니다!{Colors.ENDC}")
        print(f"{Colors.OKGREEN}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        print(f"\n📁 백업 위치: {backup_dir}\n")
        
        workflow.finalize()
        return True
    
    except Exception as e:
        error_msg = f"백업 프로세스 중 오류 발생: {str(e)}"
        print(f"\n{Colors.FAIL}{Colors.BOLD}[오류] {error_msg}{Colors.ENDC}")
        
        # 에러 발생 시 백업 폴더 삭제
        if backup_dir and backup_dir.exists():
            try:
                shutil.rmtree(backup_dir)
                print(f"[정보] 불완전한 백업 폴더 '{backup_dir}'을(를) 삭제했습니다.")
            except Exception as del_e:
                print(f"[경고] 백업 폴더 삭제 실패: {del_e}")
        
        show_popup(
            TitleMessages.ERROR,
            error_msg,
            icon=UIConstants.ICON_ERROR
        )
        
        workflow.finalize()
        return False
    
    finally:
        _cleanup_temp_files(output_dir, slot_suffix)
        workflow.cleanup_and_reboot()


