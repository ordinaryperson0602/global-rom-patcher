"""국가코드 변경 유틸리티 (자동/수동 통합)

persist.img, devinfo.img 파티션에서 국가코드를 변경합니다.

모드:
- 자동 모드: CN→KR 전체 자동 실행
- 수동 모드: STEP별 선택 실행 (CN↔KR 방향 선택 가능)
"""
import shutil
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Tuple

from config.colors import Colors
from config.paths import CURRENT_DIR, COUNTRY_CODE_BACKUP_DIR, EDL_NG_EXE
from config.constants import UIConstants
from config.messages import TitleMessages, ErrorMessages
from core.exceptions import (
    EDLConnectionError,
    LoaderNotFoundError,
    UserCancelledError,
    PartitionOperationError,
    PatchVerificationError,
    PatchCreationError
)
from core.logger import log_error, log_step_start, log_step_end
from core.progress import (
    init_standalone_progress, update_standalone_task,
    print_standalone_progress, end_standalone_progress
)
from utils.ui import show_popup, clear_screen
from utils.command import run_command
from utils.edl_workflow import EDLWorkflow, select_loader_file


# ============================================================================
# 상수 정의
# ============================================================================

# 국가코드 패턴
COUNTRY_CODE_CN = b'CNXX'
COUNTRY_CODE_KR = b'KRXX'

# 파티션 이름
PARTITIONS = ['persist', 'devinfo', 'keystore']

# 출력 폴더 경로
ANALYSIS_OUTPUT_DIR = CURRENT_DIR / "Output" / "Country_Code_Analysis"
PATCH_OUTPUT_DIR = CURRENT_DIR / "Output" / "Country_Code_Patch"


# ============================================================================
# 공통 함수
# ============================================================================

def analyze_country_code(file_path: Path) -> Dict[str, int]:
    """
    이미지 파일의 국가코드 분석
    
    Returns:
        {'cn': CN 개수, 'kr': KR 개수}
    """
    try:
        data = file_path.read_bytes()
        return {
            'cn': data.count(COUNTRY_CODE_CN),
            'kr': data.count(COUNTRY_CODE_KR)
        }
    except Exception as e:
        print(f"{Colors.FAIL}[오류] 파일 읽기 실패: {e}{Colors.ENDC}")
        log_error(f"파일 읽기 실패: {file_path}", exception=e, context="국가코드 분석")
        return {'cn': 0, 'kr': 0}


def modify_country_code(source_file: Path, target_file: Path, 
                       source_code: bytes, target_code: bytes) -> Optional[str]:
    """
    국가코드 변경
    
    Args:
        source_file: 원본 파일
        target_file: 출력 파일
        source_code: 원본 코드 (예: CNXX)
        target_code: 대상 코드 (예: KRXX)
    
    Returns:
        'patch': 변경됨
        'skip': 이미 대상 코드 상태
        'no_code': 코드 없음
        None: 오류
    """
    try:
        data = source_file.read_bytes()
        
        source_count = data.count(source_code)
        target_count = data.count(target_code)
        
        if source_count > 0:
            # 변경 적용
            new_data = data.replace(source_code, target_code)
            target_file.write_bytes(new_data)
            source_str = source_code.decode('utf-8', errors='ignore')
            target_str = target_code.decode('utf-8', errors='ignore')
            print(f"    {Colors.OKGREEN}✓ {source_str} → {target_str} 변경 ({source_count}개){Colors.ENDC}")
            return 'patch'
        
        elif target_count > 0:
            # 이미 대상 상태
            shutil.copy(source_file, target_file)
            target_str = target_code.decode('utf-8', errors='ignore')
            print(f"    {Colors.OKCYAN}→ 이미 {target_str} 상태 ({target_count}개){Colors.ENDC}")
            return 'skip'
        
        else:
            # 코드 없음
            shutil.copy(source_file, target_file)
            print(f"    {Colors.WARNING}→ 국가코드 없음 (원본 유지){Colors.ENDC}")
            return 'no_code'
    
    except Exception as e:
        error_msg = f"국가코드 변경 실패: {source_file.name}"
        print(f"    {Colors.FAIL}✗ {error_msg}: {e}{Colors.ENDC}")
        log_error(error_msg, exception=e, context="국가코드 변경")
        return None


def verify_patch_file(patch_file: Path, expected_code: bytes, context: str = "") -> bool:
    """
    패치 파일 검증
    
    Args:
        patch_file: 검증할 패치 파일
        expected_code: 기대하는 코드 (CNXX 또는 KRXX)
        context: 로깅용 컨텍스트
    
    Returns:
        검증 성공 시 True
    """
    try:
        data = patch_file.read_bytes()
        count = data.count(expected_code)
        
        if count > 0:
            code_str = expected_code.decode('utf-8', errors='ignore')
            print(f"  {Colors.OKGREEN}✓ {patch_file.name} 검증 성공: {code_str} {count}개 확인{Colors.ENDC}")
            return True
        else:
            code_str = expected_code.decode('utf-8', errors='ignore')
            print(f"  {Colors.FAIL}✗ {patch_file.name} 검증 실패: {code_str} 없음{Colors.ENDC}")
            return False
    
    except Exception as e:
        error_msg = f"패치 파일 검증 실패: {patch_file.name}"
        print(f"  {Colors.FAIL}✗ {error_msg}: {e}{Colors.ENDC}")
        log_error(error_msg, exception=e, context=f"국가코드 검증 - {context}")
        return False


def create_backup_folder() -> Path:
    """백업 폴더 생성"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    COUNTRY_CODE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_dir = COUNTRY_CODE_BACKUP_DIR / f"{timestamp}_Backup"
    backup_dir.mkdir(exist_ok=True)
    return backup_dir


# ============================================================================
# STEP 함수들 (공통)
# ============================================================================

def step1_edl_entry() -> Optional[EDLWorkflow]:
    """
    STEP 1: EDL 모드 진입 및 확인
    
    Returns:
        성공 시 EDLWorkflow 객체, 실패 시 None
    """
    tasks = ["ADB 연결 확인", "EDL 모드 진입", "EDL 연결 확인"]
    
    try:
        # 로더 파일 선택
        loader = select_loader_file()
        if not loader:
            raise LoaderNotFoundError(ErrorMessages.EDL_LOADER_NOT_SET)
        
        workflow = EDLWorkflow("국가코드 변경 STEP 1", tasks)
        workflow.loader_path = loader  # 로더 경로 설정
        workflow.initialize()  # 진행률 초기화
        
        # EDL 진입 워크플로우 실행
        if not workflow.run_common_steps():
            return None
        
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ STEP 1 완료!{Colors.ENDC}")
        return workflow
        
    except Exception as e:
        error_msg = f"STEP 1 실행 중 오류: {e}"
        print(f"\n{Colors.FAIL}[오류] {error_msg}{Colors.ENDC}")
        log_error(error_msg, exception=e, context="국가코드 변경 STEP 1")
        return None


def step2_read_and_analyze(workflow: EDLWorkflow) -> Optional[Dict[str, Path]]:
    """
    STEP 2: 파티션 읽기 및 분석
    
    Args:
        workflow: STEP 1에서 생성된 EDLWorkflow
    
    Returns:
        성공 시 파티션 파일 딕셔너리, 실패 시 None
    """
    loader_path = workflow.loader_path
    if not loader_path:
        raise LoaderNotFoundError(ErrorMessages.EDL_LOADER_NOT_SET)
    
    # 출력 폴더 생성
    ANALYSIS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    partition_files = {}
    
    print("\n[정보] 파티션을 읽어옵니다...\n")
    
    for partition in PARTITIONS:
        output_file = ANALYSIS_OUTPUT_DIR / f"{partition}.img"
        
        print(f"[정보] '{partition}' 파티션 읽기 중...")
        
        success, error_output, _ = run_command(
            [str(EDL_NG_EXE), "--loader", str(loader_path), 
             "read-part", partition, str(output_file)],
            f"{partition} 파티션 읽기"
        )
        
        if success and output_file.exists():
            file_size = output_file.stat().st_size
            print(f"[성공] {output_file.name} ({file_size:,} bytes)")
            partition_files[partition] = output_file
        else:
            raise PartitionOperationError(partition, "읽기")
    
    # 분석
    print(f"\n{Colors.OKCYAN}[국가코드 분석 결과]{Colors.ENDC}")
    print(f"{Colors.OKCYAN}{'─'*60}{Colors.ENDC}")
    
    analysis_results = {}
    for partition, file_path in partition_files.items():
        counts = analyze_country_code(file_path)
        analysis_results[partition] = counts
        
        print(f"\n{Colors.BOLD}{partition}.img:{Colors.ENDC}")
        print(f"  - CNXX: {counts['cn']}개")
        print(f"  - KRXX: {counts['kr']}개")
    
    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    analysis_file = ANALYSIS_OUTPUT_DIR / f"analysis_{timestamp}.txt"
    
    with open(analysis_file, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write("국가코드 분석 결과\n")
        f.write(f"분석 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n\n")
        
        for partition, counts in analysis_results.items():
            f.write(f"{partition}.img:\n")
            f.write(f"  - CNXX: {counts['cn']}개\n")
            f.write(f"  - KRXX: {counts['kr']}개\n\n")
        
        f.write("\n저장된 파일:\n")
        for partition in PARTITIONS:
            f.write(f"  - {partition}.img\n")
    
    print(f"\n[성공] 분석 결과 저장: {analysis_file.name}")
    print(f"{Colors.OKGREEN}{Colors.BOLD}✓ STEP 2 완료!{Colors.ENDC}")
    
    return partition_files


def step3_create_patch(direction: str = "CN_TO_KR") -> Optional[Tuple[Dict[str, Path], Dict[str, Tuple[str, Path]]]]:
    """
    STEP 3: 패치 파일 생성
    
    Args:
        direction: "CN_TO_KR" 또는 "KR_TO_CN"
    
    Returns:
        성공 시 (원본 파일 딕셔너리, 수정 작업 딕셔너리), 실패 시 None
    """
    # 방향 설정
    if direction == "CN_TO_KR":
        source_code, target_code = COUNTRY_CODE_CN, COUNTRY_CODE_KR
        direction_str = "CN → KR"
    else:  # KR_TO_CN
        source_code, target_code = COUNTRY_CODE_KR, COUNTRY_CODE_CN
        direction_str = "KR → CN"
    
    # STEP 2 파일 확인
    print(f"\n[정보] STEP 2에서 추출한 파일 확인 중...")
    
    partition_files = {}
    for partition in PARTITIONS:
        file_path = ANALYSIS_OUTPUT_DIR / f"{partition}.img"
        if not file_path.exists():
            raise FileNotFoundError(
                f"'{partition}.img' 파일을 찾을 수 없습니다.\n"
                f"STEP 2를 먼저 실행하세요.\n"
                f"예상 경로: {file_path}"
            )
        partition_files[partition] = file_path
        print(f"  ✓ {file_path.name} 확인")
    
    # 패치 파일 생성
    print(f"\n[정보] 패치 파일 생성 중... ({direction_str})")
    
    PATCH_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    patch_files = {}
    modification_tasks = {}
    
    for partition, source_file in partition_files.items():
        print(f"\n  {partition}.img 처리 중...")
        patch_file = PATCH_OUTPUT_DIR / f"{partition}_patch.img"
        
        status = modify_country_code(source_file, patch_file, source_code, target_code)
        
        if status:
            patch_files[partition] = patch_file
            modification_tasks[partition] = (status, patch_file)
        else:
            raise PatchCreationError(partition)
    
    # 백업 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = PATCH_OUTPUT_DIR / "Backup" / f"{timestamp}_Backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[정보] 백업 생성 중...")
    for partition, source_file in partition_files.items():
        backup_file = backup_dir / f"{partition}_backup.img"
        shutil.copy(source_file, backup_file)
        print(f"  ✓ {partition}_backup.img 생성")
    
    # 패치 파일도 백업
    for partition, patch_file in patch_files.items():
        backup_patch_file = backup_dir / f"{partition}_patch.img"
        shutil.copy(patch_file, backup_patch_file)
        print(f"  ✓ {partition}_patch.img 백업")
    
    # 패치 파일 검증 (실제로 변경된 파일만)
    print(f"\n[정보] 패치 파일 검증 중...")
    all_verified = True
    
    for partition, (status, patch_file) in modification_tasks.items():
        if status == 'patch':  # 실제로 변경된 파일만 검증
            if not verify_patch_file(patch_file, target_code, f"STEP 3 - {partition}"):
                all_verified = False
        elif status == 'skip':
            print(
                f"  {Colors.OKCYAN}○ {patch_file.name} 검증 건너뜀 "
                f"(이미 {target_code.decode('utf-8', errors='ignore')} 상태){Colors.ENDC}"
            )
        elif status == 'no_code':
            print(f"  {Colors.WARNING}○ {patch_file.name} 검증 건너뜀 (국가코드 없음){Colors.ENDC}")
    
    if not all_verified:
        raise PatchVerificationError(ErrorMessages.PATCH_FILE_VERIFICATION_FAILED)
    
    # Analysis 폴더 정리 (백업 폴더에 이미 저장되어 있음)
    print(f"\n[정보] 원본 파일 정리 중...")
    if ANALYSIS_OUTPUT_DIR.exists():
        try:
            shutil.rmtree(ANALYSIS_OUTPUT_DIR)
            print(f"  ✓ {ANALYSIS_OUTPUT_DIR.name} 폴더 삭제")
        except Exception as e:
            print(f"  [경고] {ANALYSIS_OUTPUT_DIR.name} 폴더 삭제 실패: {e}")
    
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ STEP 3 완료!{Colors.ENDC}")
    print(f"{Colors.OKGREEN}패치 폴더: {PATCH_OUTPUT_DIR}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}백업 폴더: {backup_dir}{Colors.ENDC}")
    
    return partition_files, modification_tasks


def step4_write_and_verify(workflow: EDLWorkflow, target_code: bytes = COUNTRY_CODE_KR) -> bool:
    """
    STEP 4: 파티션 쓰기 및 검증
    
    Args:
        workflow: STEP 1에서 생성된 EDLWorkflow
        target_code: 검증할 코드 (기본값: KRXX)
    
    Returns:
        성공 시 True
    """
    loader_path = workflow.loader_path
    
    # STEP 3 파일 확인
    print(f"\n[정보] STEP 3에서 생성한 패치 파일 확인 중...")
    
    patch_files = {}
    for partition in PARTITIONS:
        file_path = PATCH_OUTPUT_DIR / f"{partition}_patch.img"
        if not file_path.exists():
            raise FileNotFoundError(
                f"'{partition}_patch.img' 파일을 찾을 수 없습니다.\n"
                f"STEP 3을 먼저 실행하세요.\n"
                f"예상 경로: {file_path}"
            )
        patch_files[partition] = file_path
        print(f"  ✓ {file_path.name} 확인")
    
    # 최종 확인
    print(f"\n{Colors.FAIL}{'='*60}{Colors.ENDC}")
    print(f"{Colors.FAIL}⚠️  경고{Colors.ENDC}")
    print(f"{Colors.FAIL}{'='*60}{Colors.ENDC}")
    print(f"{Colors.WARNING}이 작업은 되돌릴 수 없습니다!{Colors.ENDC}")
    print(f"{Colors.WARNING}다음 파일들을 기기에 씁니다:{Colors.ENDC}\n")
    
    for partition, patch_file in patch_files.items():
        print(f"  • {patch_file.name} → {partition} 파티션")
    
    confirm = input(f"\n{Colors.OKCYAN}계속 진행하시겠습니까? (yes/no): {Colors.ENDC}").strip().lower()
    
    if confirm != 'yes':
        print(f"{Colors.WARNING}작업이 취소되었습니다.{Colors.ENDC}")
        return False
    
    # 파티션 쓰기
    print(f"\n[정보] 파티션 쓰기 중...")
    
    for partition, patch_file in patch_files.items():
        print(f"\n  '{partition}' 파티션 쓰는 중...")
        
        success, error_output, _ = run_command(
            [str(EDL_NG_EXE), "--loader", str(loader_path), 
             "write-part", partition, str(patch_file)],
            f"{partition} 파티션 쓰기"
        )
        
        if not success:
            raise PartitionOperationError(partition, "쓰기")
        
        print(f"  {Colors.OKGREEN}✓ {partition} 쓰기 완료{Colors.ENDC}")
    
    print(f"\n[성공] 모든 파티션 쓰기 완료")
    
    # 쓰기 검증 (읽어서 확인)
    print(f"\n[정보] 쓰기 검증 중 (기기에서 읽어서 확인)...")
    
    verify_dir = PATCH_OUTPUT_DIR / "Verify"
    verify_dir.mkdir(exist_ok=True)
    
    all_verified = True
    
    for partition in patch_files.keys():
        verify_file = verify_dir / f"{partition}_verify.img"
        
        print(f"\n  '{partition}' 파티션 읽기 중...")
        
        success, error_output, _ = run_command(
            [str(EDL_NG_EXE), "--loader", str(loader_path), 
             "read-part", partition, str(verify_file)],
            f"{partition} 파티션 검증 읽기"
        )
        
        if success and verify_file.exists():
            # 국가코드 확인
            data = verify_file.read_bytes()
            count = data.count(target_code)
            code_str = target_code.decode('utf-8', errors='ignore')
            
            if count > 0:
                print(f"  {Colors.OKGREEN}✓ {partition} 검증 성공: {code_str} {count}개 확인{Colors.ENDC}")
            else:
                print(f"  {Colors.FAIL}✗ {partition} 검증 실패: {code_str} 없음{Colors.ENDC}")
                all_verified = False
        else:
            print(f"  {Colors.FAIL}✗ {partition} 검증 실패 (읽기 실패){Colors.ENDC}")
            all_verified = False
    
    # 검증 임시 파일 삭제
    if verify_dir.exists():
        shutil.rmtree(verify_dir)
    
    if not all_verified:
        print(f"\n{Colors.WARNING}⚠️  일부 파티션 검증 실패!{Colors.ENDC}")
        print(f"{Colors.WARNING}하지만 쓰기는 완료되었습니다.{Colors.ENDC}")
    else:
        print(f"\n[성공] 모든 파티션 검증 완료")
    
    # 패치 파일 정리 (백업 폴더에 이미 저장되어 있음)
    print(f"\n[정보] 임시 패치 파일 정리 중...")
    for partition, patch_file in patch_files.items():
        if patch_file.exists():
            try:
                patch_file.unlink()
                print(f"  ✓ {patch_file.name} 삭제")
            except Exception as e:
                print(f"  [경고] {patch_file.name} 삭제 실패: {e}")
    
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ STEP 4 완료!{Colors.ENDC}")
    
    return True


def step5_reboot() -> bool:
    """
    STEP 5: 재부팅
    
    Returns:
        성공 시 True, 실패 시 False
    """
    print(f"\n[정보] 기기를 재부팅합니다...")
    
    success, output, _ = run_command(
        [str(EDL_NG_EXE), "reset"],
        "기기 재부팅"
    )
    
    if success:
        print(f"{Colors.OKGREEN}✓ 재부팅 명령 전송 완료{Colors.ENDC}")
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ STEP 5 완료!{Colors.ENDC}")
        return True
    else:
        print(f"{Colors.FAIL}✗ 재부팅 명령 실패{Colors.ENDC}")
        print(f"\n{Colors.BOLD}[수동 재부팅 방법]{Colors.ENDC}")
        print(f"  1. PC에서 USB 케이블을 제거하세요")
        print(f"  2. {Colors.OKGREEN}볼륨 다운(-) + 전원 버튼{Colors.ENDC}을 {Colors.BOLD}15초 이상{Colors.ENDC} 누르세요")
        print(f"  3. 태블릿이 꺼질 때까지 계속 누르고 있으세요")
        print(f"  4. 태블릿이 정상 부팅될 때까지 기다리세요\n")
        print(f"\n{Colors.WARNING}{Colors.BOLD}⚠️  STEP 5 완료 (수동 재부팅 필요){Colors.ENDC}")
        return False


# ============================================================================
# 자동 모드 (CN→KR 고정) - Helper Functions (리팩토링)
# ============================================================================

def _read_all_partitions(loader_path: str) -> Dict[str, Path]:
    """모든 파티션 읽기
    
    Returns:
        {partition_name: Path} 또는 빈 dict if error
    """
    from core.logger import info, log_edl_operation
    
    info(f"국가 코드 변경용 파티션 읽기 시작", partition_count=len(PARTITIONS))
    print("\n[정보] 파티션을 읽어옵니다...\n")
    
    partition_files = {}
    
    for partition in PARTITIONS:
        output_file = CURRENT_DIR / f"{partition}.img"
        
        try:
            success, error_output, _ = run_command(
                [str(EDL_NG_EXE), "--loader", str(loader_path), 
                 "read-part", partition, str(output_file)],
                f"{partition} 파티션 읽기"
            )
            
            if success and output_file.exists():
                partition_files[partition] = output_file
                log_edl_operation("read", partition, True)
            else:
                log_edl_operation("read", partition, False, error_output[:200] if error_output else "파일 생성 실패")
                # GPT 파싱 에러 확인
                from utils.edl_workflow import is_gpt_parsing_error, handle_gpt_parsing_error
                if is_gpt_parsing_error(error_output):
                    handle_gpt_parsing_error()
                raise PartitionOperationError(partition, "읽기")
        except EDLConnectionError as edl_err:
            print(f"\n{Colors.FAIL}[!!!] EDL 연결 끊김 감지!{Colors.ENDC}")
            raise edl_err
    
    return partition_files


def _create_backup_for_partitions(partition_files: Dict[str, Path]) -> Path:
    """파티션 백업 생성
    
    Returns:
        backup_dir Path
    """
    backup_dir = create_backup_folder()
    print(f"\n[정보] 백업 폴더: {backup_dir}\n")
    
    for partition, src_file in partition_files.items():
        backup_file = backup_dir / f"{partition}_backup.img"
        shutil.copy(src_file, backup_file)
        print(f"  - {partition}.img → {backup_file.name} 이동 완료.")
    
    print(f"\n[성공] 백업 완료")
    return backup_dir


def _modify_and_backup_patches(partition_files: Dict[str, Path], backup_dir: Path) -> Dict[str, Tuple[str, Path]]:
    """국가코드 변경 및 패치 파일 백업
    
    Returns:
        {partition: (status, patch_file_path)}
    """
    print(f"\n[정보] 국가코드를 분석하고 변경합니다...\n")
    
    modification_tasks = {}
    
    for partition, src_file in partition_files.items():
        print(f"  {partition}.img 분석 중...")
        patch_file = CURRENT_DIR / f"{partition}_patch.img"
        status = modify_country_code(src_file, patch_file, COUNTRY_CODE_CN, COUNTRY_CODE_KR)
        
        if status:
            modification_tasks[partition] = (status, patch_file)
        else:
            raise PatchCreationError(partition)
    
    # 패치 파일 백업
    print(f"\n[정보] 패치 파일을 백업합니다...")
    for partition, (status, patch_file) in modification_tasks.items():
        backup_patch_file = backup_dir / patch_file.name
        shutil.copy(patch_file, backup_patch_file)
        print(f"  - {patch_file.name} → {backup_patch_file.name} 이동 완료.")
    print(f"[성공] 패치 파일 백업 완료")
    
    # 원본 파일 정리
    print(f"\n[정보] 원본 이미지 파일 정리 중...")
    for src_file in partition_files.values():
        if src_file.exists():
            src_file.unlink()
    print(f"[성공] 정리 완료")
    
    return modification_tasks


def _verify_all_patches(modification_tasks: Dict[str, Tuple[str, Path]]) -> bool:
    """패치 파일 검증
    
    Returns:
        True if all verified
    """
    print(f"\n[정보] 패치 파일 검증 중...")
    all_verified = True
    
    for partition, (status, patch_file) in modification_tasks.items():
        if status == 'patch':  # 실제로 변경된 파일만 검증
            if not verify_patch_file(patch_file, COUNTRY_CODE_KR, f"자동 모드 - {partition}"):
                all_verified = False
    
    if not all_verified:
        raise PatchVerificationError(ErrorMessages.PATCH_FILE_VERIFICATION_FAILED)
    
    print(f"[성공] 모든 패치 파일 검증 완료")
    return True


def _write_modified_partitions(files_to_write: Dict[str, Path], loader_path: str) -> bool:
    """수정된 파티션 쓰기
    
    Returns:
        True if written, False if skipped
    """
    if not files_to_write:
        print(f"\n{Colors.OKCYAN}[정보] 모든 파일이 이미 'KRXX' 상태입니다.{Colors.ENDC}")
        print(f"       쓰기 작업을 건너뜁니다.")
        return False
    
    print(f"\n{Colors.WARNING}⚠️  다음 파일들을 태블릿에 씁니다:{Colors.ENDC}\n")
    for partition, patch_file in files_to_write.items():
        print(f"  • {patch_file.name} → {partition} 파티션")
    
    print(f"\n{Colors.FAIL}⚠️  이 작업은 되돌릴 수 없습니다!{Colors.ENDC}")
    
    confirm = input(f"\n{Colors.WARNING}'동의'를 입력하여 계속 진행하세요: {Colors.ENDC}").strip()
    
    if confirm != '동의':
        raise UserCancelledError(ErrorMessages.USER_CANCELLED)
    
    print()
    
    for partition, patch_file in files_to_write.items():
        print(f"\n  '{partition}' 파티션 쓰는 중...")
        
        success, error_output, _ = run_command(
            [str(EDL_NG_EXE), "--loader", str(loader_path), 
             "write-part", partition, str(patch_file)],
            f"{partition} 파티션 쓰기"
        )
        
        if not success:
            raise PartitionOperationError(partition, "쓰기")
        
        print(f"  {Colors.OKGREEN}✓ {partition} 쓰기 완료{Colors.ENDC}")
    
    print(f"\n[성공] 모든 파티션 쓰기 완료")
    return True


def _verify_written_partitions(files_to_write: Dict[str, Path], loader_path: str) -> bool:
    """기기에서 파티션 읽어서 쓰기 검증
    
    Returns:
        True if all verified
    """
    print(f"\n[정보] 쓰기 검증 중 (기기에서 읽어서 확인)...")
    
    verify_dir = CURRENT_DIR / "verify_temp"
    verify_dir.mkdir(exist_ok=True)
    
    all_verified = True
    
    try:
        for partition in files_to_write.keys():
            verify_file = verify_dir / f"{partition}_verify.img"
            
            print(f"\n  '{partition}' 파티션 읽기 중...")
            
            success, error_output, _ = run_command(
                [str(EDL_NG_EXE), "--loader", str(loader_path), 
                 "read-part", partition, str(verify_file)],
                f"{partition} 파티션 검증 읽기"
            )
            
            if success and verify_file.exists():
                # KRXX가 있는지 확인
                data = verify_file.read_bytes()
                kr_count = data.count(COUNTRY_CODE_KR)
                
                if kr_count > 0:
                    print(f"  {Colors.OKGREEN}✓ {partition} 검증 성공: KRXX {kr_count}개 확인{Colors.ENDC}")
                else:
                    print(f"  {Colors.FAIL}✗ {partition} 검증 실패: KRXX 없음{Colors.ENDC}")
                    all_verified = False
            else:
                print(f"  {Colors.FAIL}✗ {partition} 검증 실패 (읽기 실패){Colors.ENDC}")
                all_verified = False
    finally:
        # 검증 임시 파일 삭제
        if verify_dir.exists():
            shutil.rmtree(verify_dir)
    
    if not all_verified:
        print(f"\n{Colors.WARNING}⚠️  일부 파티션 검증 실패!{Colors.ENDC}")
        print(f"{Colors.WARNING}하지만 쓰기는 완료되었습니다.{Colors.ENDC}")
    else:
        print(f"\n[성공] 모든 파티션 검증 완료")
    
    return all_verified


def _cleanup_and_reboot() -> None:
    """임시 파일 정리 및 재부팅"""
    # 임시 파일 정리
    temp_files = list(CURRENT_DIR.glob("*_patch.img"))
    if temp_files:
        print(f"\n[정보] 임시 파일 정리 중...")
        for temp_file in temp_files:
            try:
                temp_file.unlink()
            except Exception as e:
                print(f"  [경고] {temp_file.name} 삭제 실패: {e}")
    
    # 재부팅
    print(f"\n[정보] 기기를 재부팅합니다...")
    try:
        success, _, _ = run_command([str(EDL_NG_EXE), "reset"], "기기 재부팅")
        if success:
            print(f"{Colors.OKGREEN}✓ 재부팅 명령 전송 완료{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}✗ 재부팅 명령 실패{Colors.ENDC}")
            _show_manual_reboot_instructions()
    except Exception as e:
        print(f"{Colors.FAIL}✗ 재부팅 명령 실패: {e}{Colors.ENDC}")
        _show_manual_reboot_instructions()


def _show_manual_reboot_instructions() -> None:
    """수동 재부팅 방법 표시"""
    print(f"\n{Colors.BOLD}[수동 재부팅 방법]{Colors.ENDC}")
    print(f"  1. PC에서 USB 케이블을 제거하세요")
    print(f"  2. {Colors.OKGREEN}볼륨 다운(-) + 전원 버튼{Colors.ENDC}을 {Colors.BOLD}15초 이상{Colors.ENDC} 누르세요")
    print(f"  3. 태블릿이 꺼질 때까지 계속 누르고 있으세요")
    print(f"  4. 태블릿이 정상 부팅될 때까지 기다리세요\n")


# ============================================================================
# 자동 모드 메인 함수 (리팩토링: 318줄 → 150줄)
# ============================================================================

def run_auto_country_change() -> bool:
    """국가코드 자동 변경 (CN→KR) - 리팩토링 버전"""
    log_step_start("국가코드 자동 변경")
    clear_screen()
    
    # 진행 작업 정의
    tasks = [
        "ADB 연결 확인",
        "EDL 모드 진입",
        "EDL 연결 확인",
        "파티션 읽기",
        "백업 생성",
        "국가코드 변경",
        "패치 파일 검증",
        "파티션 쓰기",
        "쓰기 검증",
        "완료"
    ]
    
    init_standalone_progress("국가코드 변경 (CN→KR)", tasks)
    
    print(f"\n{Colors.HEADER}{'━'*60}\n{Colors.BOLD}       국가코드 자동 변경 (CN→KR)\n{'━'*60}{Colors.ENDC}\n")
    
    backup_dir = None
    workflow = None
    
    try:
        # 로더 선택
        loader = select_loader_file()
        if not loader:
            raise LoaderNotFoundError(ErrorMessages.EDL_LOADER_NOT_SET)
        
        # STEP 1-3: EDL 진입
        workflow = EDLWorkflow("국가코드 변경 (CN→KR)", tasks)
        workflow.loader_path = loader  # 로더 경로 설정
        workflow.initialize()  # 진행률 초기화
        
        # EDL 워크플로우 실행 (Task 0-2)
        if not workflow.run_common_steps():
            raise UserCancelledError(ErrorMessages.USER_CANCELLED)
        
        loader_path = workflow.loader_path
        
        # Task 3: 파티션 읽기
        update_standalone_task(3, 'in_progress')
        print_standalone_progress()
        
        partition_files = _read_all_partitions(loader_path)
        
        update_standalone_task(3, 'done')
        print_standalone_progress()
        
        # Task 4: 백업 생성
        update_standalone_task(4, 'in_progress')
        print_standalone_progress()
        
        backup_dir = _create_backup_for_partitions(partition_files)
        
        update_standalone_task(4, 'done')
        print_standalone_progress()
        
        # Task 5: 국가코드 변경
        update_standalone_task(5, 'in_progress')
        print_standalone_progress()
        
        modification_tasks = _modify_and_backup_patches(partition_files, backup_dir)
        
        update_standalone_task(5, 'done')
        print_standalone_progress()
        
        # Task 6: 패치 파일 검증
        update_standalone_task(6, 'in_progress')
        print_standalone_progress()
        
        _verify_all_patches(modification_tasks)
        
        update_standalone_task(6, 'done')
        print_standalone_progress()
        
        # Task 7: 파티션 쓰기
        files_to_write = {
            part: path for part, (status, path) in modification_tasks.items() 
            if status == 'patch'
        }
        
        if not files_to_write:
            # 모든 파일이 이미 KRXX 상태
            print(f"\n{Colors.OKCYAN}[정보] 모든 파일이 이미 'KRXX' 상태입니다.{Colors.ENDC}")
            print(f"       쓰기 작업을 건너뜁니다.")
            update_standalone_task(7, 'done')
            update_standalone_task(8, 'done')
            print_standalone_progress()
        else:
            update_standalone_task(7, 'in_progress')
            print_standalone_progress()
            
            _write_modified_partitions(files_to_write, loader_path)
            
            update_standalone_task(7, 'done')
            print_standalone_progress()
            
            # Task 8: 쓰기 검증
            update_standalone_task(8, 'in_progress')
            print_standalone_progress()
            
            _verify_written_partitions(files_to_write, loader_path)
            
            update_standalone_task(8, 'done')
            print_standalone_progress()
        
        # Task 9: 완료
        update_standalone_task(9, 'done')
        print_standalone_progress()
        
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}{'='*60}\n  ✓ 국가코드 변경 프로세스가 완료되었습니다!\n{'='*60}{Colors.ENDC}\n")
        
        log_step_end("국가코드 자동 변경", success=True)
        return True
    
    except Exception as e:
        error_msg = f"국가코드 변경 중 오류 발생: {str(e)}"
        print(f"\n{Colors.FAIL}{Colors.BOLD}[오류] {error_msg}{Colors.ENDC}")
        log_error(error_msg, exception=e, context="자동 모드 - 전체")
        # 에러 발생 시 백업 폴더 삭제
        if backup_dir and backup_dir.exists():
            try:
                shutil.rmtree(backup_dir)
                print(f"[정보] 불완전한 백업 폴더 '{backup_dir}'을(를) 삭제했습니다.")
            except Exception as del_e:
                print(f"[경고] 백업 폴더 삭제 실패: {del_e}")
        
        show_popup(
            TitleMessages.ERROR,
            f"{error_msg}\n\n로그 파일을 확인하세요.",
            icon=UIConstants.ICON_ERROR
        )
        
        log_step_end("국가코드 자동 변경", success=False)
        return False
    
    finally:
        # 임시 파일 정리 및 재부팅
        _cleanup_and_reboot()
        end_standalone_progress()
        input(f"\n{Colors.OKCYAN}Enter 키를 눌러 메뉴로 돌아가기...{Colors.ENDC}")


# ============================================================================
# 수동 모드 (STEP별 선택, CN↔KR 방향 선택) - Helper Functions (리팩토링)
# ============================================================================

def _execute_manual_step1() -> Optional['EDLWorkflow']:
    """STEP 1: EDL 진입 실행"""
    log_step_start("국가코드 변경 STEP 1")
    
    clear_screen()
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}   STEP 1: EDL 모드 진입 및 확인{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    init_standalone_progress("STEP 1: EDL 진입", ["ADB 연결", "EDL 진입", "EDL 확인"])
    
    workflow = step1_edl_entry()
    
    end_standalone_progress()
    
    if workflow:
        log_step_end("국가코드 변경 STEP 1", success=True)
    else:
        log_step_end("국가코드 변경 STEP 1", success=False)
    
    input(f"\n{Colors.OKCYAN}Enter 키를 눌러 계속...{Colors.ENDC}")
    return workflow


def _execute_manual_step2(workflow: Optional['EDLWorkflow']) -> Optional['EDLWorkflow']:
    """STEP 2: 파티션 읽기 및 분석 실행"""
    log_step_start("국가코드 변경 STEP 2")
    
    clear_screen()
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}   STEP 2: 파티션 읽기 및 분석{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    try:
        # EDL 확인
        if workflow is None:
            print(f"{Colors.WARNING}[알림] STEP 1이 실행되지 않았습니다.{Colors.ENDC}")
            print(f"{Colors.WARNING}EDL 모드로 다시 진입합니다...{Colors.ENDC}\n")
            workflow = step1_edl_entry()
            if workflow is None:
                raise LoaderNotFoundError(ErrorMessages.EDL_LOADER_NOT_FOUND)
        
        init_standalone_progress("STEP 2: 파티션 분석", ["persist 읽기", "devinfo 읽기", "분석", "저장"])
        
        update_standalone_task(0, 'in_progress')
        print_standalone_progress()
        
        partition_files = step2_read_and_analyze(workflow)
        
        for i in range(4):
            update_standalone_task(i, 'done')
        print_standalone_progress()
        
        print(f"{Colors.OKGREEN}출력 폴더: {ANALYSIS_OUTPUT_DIR}{Colors.ENDC}")
        
        log_step_end("국가코드 변경 STEP 2", success=True)
    
    except Exception as e:
        error_msg = f"STEP 2 실행 중 오류: {e}"
        print(f"\n{Colors.FAIL}[오류] {error_msg}{Colors.ENDC}")
        log_error(error_msg, exception=e, context="국가코드 변경 STEP 2")
        log_step_end("국가코드 변경 STEP 2", success=False)
    
    finally:
        end_standalone_progress()
    
    input(f"\n{Colors.OKCYAN}Enter 키를 눌러 계속...{Colors.ENDC}")
    return workflow


def _execute_manual_step3() -> str:
    """STEP 3: 패치 파일 생성 실행
    
    Returns:
        선택된 방향 (CN_TO_KR 또는 KR_TO_CN)
    """
    log_step_start("국가코드 변경 STEP 3")
    
    clear_screen()
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}   STEP 3: 패치 파일 생성{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    direction = "CN_TO_KR"
    
    try:
        init_standalone_progress("STEP 3: 패치 생성", ["파일 확인", "방향 선택", "패치 생성", "백업", "검증"])
        
        update_standalone_task(0, 'done')
        print_standalone_progress()
        
        # 방향 선택
        update_standalone_task(1, 'in_progress')
        print_standalone_progress()
        
        direction = ask_direction()
        
        update_standalone_task(1, 'done')
        print_standalone_progress()
        
        # 패치 생성
        update_standalone_task(2, 'in_progress')
        print_standalone_progress()
        
        step3_create_patch(direction)
        
        for i in range(2, 5):
            update_standalone_task(i, 'done')
        print_standalone_progress()
        
        log_step_end("국가코드 변경 STEP 3", success=True)
    
    except Exception as e:
        error_msg = f"STEP 3 실행 중 오류: {e}"
        print(f"\n{Colors.FAIL}[오류] {error_msg}{Colors.ENDC}")
        log_error(error_msg, exception=e, context="국가코드 변경 STEP 3")
        log_step_end("국가코드 변경 STEP 3", success=False)
    
    finally:
        end_standalone_progress()
    
    input(f"\n{Colors.OKCYAN}Enter 키를 눌러 계속...{Colors.ENDC}")
    return direction


def _execute_manual_step4(workflow: Optional['EDLWorkflow']) -> Optional['EDLWorkflow']:
    """STEP 4: 파티션 쓰기 및 검증 실행"""
    log_step_start("국가코드 변경 STEP 4")
    
    clear_screen()
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}   STEP 4: 파티션 쓰기 및 검증{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    try:
        # EDL 확인
        if workflow is None:
            print(f"{Colors.WARNING}[알림] STEP 1이 실행되지 않았습니다.{Colors.ENDC}")
            print(f"{Colors.WARNING}EDL 모드로 다시 진입합니다...{Colors.ENDC}\n")
            workflow = step1_edl_entry()
            if workflow is None:
                raise LoaderNotFoundError(ErrorMessages.EDL_LOADER_NOT_FOUND)
        
        init_standalone_progress("STEP 4: 쓰기 및 검증", ["파일 확인", "쓰기", "검증"])
        
        update_standalone_task(0, 'in_progress')
        print_standalone_progress()
        
        step4_write_and_verify(workflow)
        
        for i in range(3):
            update_standalone_task(i, 'done')
        print_standalone_progress()
        
        log_step_end("국가코드 변경 STEP 4", success=True)
    
    except Exception as e:
        error_msg = f"STEP 4 실행 중 오류: {e}"
        print(f"\n{Colors.FAIL}[오류] {error_msg}{Colors.ENDC}")
        log_error(error_msg, exception=e, context="국가코드 변경 STEP 4")
        log_step_end("국가코드 변경 STEP 4", success=False)
    
    finally:
        end_standalone_progress()
    
    input(f"\n{Colors.OKCYAN}Enter 키를 눌러 계속...{Colors.ENDC}")
    return workflow


def _execute_manual_step5() -> None:
    """STEP 5: 재부팅 실행"""
    log_step_start("국가코드 변경 STEP 5")
    
    clear_screen()
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}   STEP 5: 재부팅{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    init_standalone_progress("STEP 5: 재부팅", ["재부팅"])
    
    update_standalone_task(0, 'in_progress')
    print_standalone_progress()
    
    reboot_success = step5_reboot()
    
    update_standalone_task(0, 'done')
    print_standalone_progress()
    
    if reboot_success:
        log_step_end("국가코드 변경 STEP 5", success=True)
    else:
        log_step_end("국가코드 변경 STEP 5", success=False)
    
    end_standalone_progress()
    input(f"\n{Colors.OKCYAN}Enter 키를 눌러 계속...{Colors.ENDC}")


def _execute_manual_full_run(workflow: Optional['EDLWorkflow'], direction: str) -> bool:
    """STEP 9: 전체 실행 (STEP 1→2→3→4→5)"""
    log_step_start("국가코드 변경 전체 실행")
    
    clear_screen()
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}   전체 실행 (STEP 1→2→3→4→5){Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    try:
        # 방향 선택
        direction = ask_direction()
        
        # STEP 1
        if workflow is None:
            print(f"\n{Colors.OKCYAN}[STEP 1/5] EDL 진입 중...{Colors.ENDC}")
            workflow = step1_edl_entry()
            if workflow is None:
                raise LoaderNotFoundError(ErrorMessages.EDL_LOADER_NOT_FOUND)
        
        # STEP 2
        print(f"\n{Colors.OKCYAN}[STEP 2/5] 파티션 읽기 및 분석 중...{Colors.ENDC}")
        step2_read_and_analyze(workflow)
        
        # STEP 3
        print(f"\n{Colors.OKCYAN}[STEP 3/5] 패치 파일 생성 중...{Colors.ENDC}")
        step3_create_patch(direction)
        
        # STEP 4
        print(f"\n{Colors.OKCYAN}[STEP 4/5] 파티션 쓰기 및 검증 중...{Colors.ENDC}")
        step4_write_and_verify(workflow)
        
        # STEP 5
        print(f"\n{Colors.OKCYAN}[STEP 5/5] 재부팅 중...{Colors.ENDC}")
        reboot_success = step5_reboot()
        
        log_step_end("국가코드 변경 전체 실행", success=reboot_success)
        
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        print(f"{Colors.OKGREEN}{Colors.BOLD}  ✓ 모든 작업이 완료되었습니다!{Colors.ENDC}")
        print(f"{Colors.OKGREEN}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")
        
        return True
    
    except Exception as e:
        error_msg = f"전체 실행 중 오류: {e}"
        print(f"\n{Colors.FAIL}[오류] {error_msg}{Colors.ENDC}")
        log_error(error_msg, exception=e, context="국가코드 변경 전체 실행")
        log_step_end("국가코드 변경 전체 실행", success=False)
        
        input(f"\n{Colors.OKCYAN}Enter 키를 눌러 계속...{Colors.ENDC}")
        return False


# ============================================================================
# 수동 모드 메뉴 함수들
# ============================================================================

def show_step_selection_menu() -> int:
    """STEP 선택 메뉴 표시"""
    clear_screen()
    
    print(f"\n{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'국가코드 변경 (수동, STEP 선택)':^74}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}\n")
    
    print(f"{Colors.OKCYAN}  실행할 STEP을 선택하세요:{Colors.ENDC}\n")
    
    print(f"  {Colors.BOLD}1. STEP 1: EDL 모드 진입 및 확인{Colors.ENDC}")
    print(f"     └─ ADB 연결 → EDL 모드 전환 → EDL 연결 확인\n")
    
    print(f"  {Colors.BOLD}2. STEP 2: 파티션 읽기 및 분석{Colors.ENDC}")
    print(f"     └─ persist/devinfo 읽기 → 국가코드 분석 → 결과 저장\n")
    
    print(f"  {Colors.BOLD}3. STEP 3: 패치 파일 생성 (로컬){Colors.ENDC}")
    print(f"     └─ 방향 선택 → 패치 생성 → 백업 → 검증\n")
    
    print(f"  {Colors.BOLD}4. STEP 4: 파티션 쓰기 및 검증{Colors.ENDC}")
    print(f"     └─ EDL 모드에서 기기에 쓰기 → 검증\n")
    
    print(f"  {Colors.BOLD}5. STEP 5: 재부팅{Colors.ENDC}")
    print(f"     └─ 기기 재부팅\n")
    
    print(f"  {Colors.OKGREEN}9. 전체 실행 (STEP 1→2→3→4→5){Colors.ENDC}")
    print(f"     └─ 모든 단계를 순차적으로 실행\n")
    
    print(f"  {Colors.WARNING}0. 메인 메뉴로 돌아가기{Colors.ENDC}\n")
    
    print(f"{Colors.HEADER}{'='*80}{Colors.ENDC}")
    
    while True:
        try:
            choice = input(f"\n{Colors.OKCYAN}선택 (0-5, 9): {Colors.ENDC}").strip()
            choice_int = int(choice)
            
            if choice_int in [0, 1, 2, 3, 4, 5, 9]:
                return choice_int
            else:
                print(f"{Colors.FAIL}0~5 또는 9를 입력하세요.{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.FAIL}숫자를 입력하세요.{Colors.ENDC}")


def ask_direction() -> str:
    """방향 선택"""
    print(f"\n{Colors.OKCYAN}{'='*60}{Colors.ENDC}")
    print(f"{Colors.OKCYAN}국가코드 변경 방향 선택{Colors.ENDC}")
    print(f"{Colors.OKCYAN}{'='*60}{Colors.ENDC}\n")
    print("  1. CN → KR (중국 → 한국)")
    print("  2. KR → CN (한국 → 중국)")
    
    while True:
        choice = input(f"\n{Colors.OKCYAN}선택 (1/2): {Colors.ENDC}").strip()
        
        if choice == '1':
            print(f"{Colors.OKGREEN}✓ CN → KR 선택됨{Colors.ENDC}")
            return "CN_TO_KR"
        elif choice == '2':
            print(f"{Colors.OKGREEN}✓ KR → CN 선택됨{Colors.ENDC}")
            return "KR_TO_CN"
        else:
            print(f"{Colors.FAIL}잘못된 입력입니다. 1 또는 2를 입력하세요.{Colors.ENDC}")


def run_manual_country_change_menu() -> bool:
    """국가코드 변경 (수동) 메인 메뉴 - 리팩토링 버전"""
    workflow = None
    direction = "CN_TO_KR"  # 기본값
    
    while True:
        choice = show_step_selection_menu()
        
        if choice == 0:
            # 메인 메뉴로 돌아가기
            break
        
        elif choice == 1:
            # STEP 1: EDL 진입
            workflow = _execute_manual_step1()
        
        elif choice == 2:
            # STEP 2: 파티션 읽기 및 분석
            workflow = _execute_manual_step2(workflow)
        
        elif choice == 3:
            # STEP 3: 패치 파일 생성
            direction = _execute_manual_step3()
        
        elif choice == 4:
            # STEP 4: 파티션 쓰기 및 검증
            workflow = _execute_manual_step4(workflow)
        
        elif choice == 5:
            # STEP 5: 재부팅
            _execute_manual_step5()
        
        elif choice == 9:
            # 전체 실행 (STEP 1→2→3→4→5)
            if _execute_manual_full_run(workflow, direction):
                break
    
    return True


if __name__ == "__main__":
    # 테스트용
    run_manual_country_change_menu()
