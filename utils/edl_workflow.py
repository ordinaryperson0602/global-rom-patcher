"""EDL 모드 공통 워크플로우

backup_device.py와 country_code.py의 중복 코드를 통합
"""
import time
from pathlib import Path
from typing import Optional, Callable

from config.colors import Colors
from config.paths import ADB_EXE, EDL_NG_EXE, LOADER_FILES, CURRENT_DIR
from config.constants import TimingConstants
from config.messages import InfoMessages, WARNING_BANNER
from core.progress import (
    init_standalone_progress, update_standalone_task,
    print_standalone_progress, end_standalone_progress
)
from core.exceptions import EDLConnectionError
from utils.command import run_command
from utils.ui import clear_screen
from utils.device_utils import (
    check_adb_device_state as util_check_adb_device_state,
    get_active_slot as util_get_active_slot,
    get_device_model_info as util_get_device_model_info
)


# ============================================================================
# 헬퍼 함수
# ============================================================================

def select_loader_file() -> Optional[Path]:
    """
    사용 가능한 로더 파일 자동 선택
    
    Returns:
        첫 번째로 발견된 로더 파일 경로, 없으면 None
    """
    for model_loader in LOADER_FILES.values():
        loader_path = Path(model_loader)
        if loader_path.exists():
            return loader_path
    return None


def is_edl_disconnection_error(error_output: str) -> bool:
    """
    EDL 연결 끊김 여부 확인
    
    Args:
        error_output: 에러 출력 문자열
        
    Returns:
        연결 끊김이면 True
    """
    if not error_output:
        return False
    
    error_output_lower = error_output.lower()
    disconnection_keywords = [
        "no qualcomm edl devices found",
        "cannot detect mode: no device found",
        "device disconnected",
        "communication error",
        "usb error",
        "device not found",
        "connection lost",
        "failed to communicate",
        "the port is closed",
        "port is closed",
        "error while reading response"
    ]
    
    return any(keyword in error_output_lower for keyword in disconnection_keywords)


def is_gpt_parsing_error(error_output: str) -> bool:
    """
    GPT 파싱 에러 여부 확인
    
    Args:
        error_output: 에러 출력 문자열
        
    Returns:
        GPT 파싱 에러이면 True
    """
    if not error_output:
        return False
    
    error_output_lower = error_output.lower()
    gpt_error_keywords = [
        "failed to parse xml",
        "hexadecimal value 0x00",
        "is an invalid character",
        "failed to read gpt",
        "partition '.+' not found on any scanned lun",
        "could not get storage info"
    ]
    
    return any(keyword in error_output_lower for keyword in gpt_error_keywords)


def check_edl_connection(loader_path: Path) -> bool:
    """
    EDL 모드 연결 확인
    
    Args:
        loader_path: 로더 파일 경로
        
    Returns:
        연결되면 True
        
    Raises:
        EDLConnectionError: 연결 끊김 감지 시
    """
    success, output, _ = run_command(
        [str(EDL_NG_EXE), "--loader", str(loader_path), "printgpt"],
        "EDL 연결 확인"
    )
    
    if success and "GPT Header LUN" in output:
        return True
    
    if is_edl_disconnection_error(output):
        raise EDLConnectionError("EDL 연결 끊김")
    
    return False


def reboot_device() -> bool:
    """
    EDL 모드에서 기기 재부팅
    
    Returns:
        성공 시 True
    """
    success, _, _ = run_command([str(EDL_NG_EXE), "reset"], "기기 재부팅")
    
    if success:
        print(f"{Colors.OKGREEN}[성공] 재부팅 명령 전송 완료{Colors.ENDC}")
        return True
    else:
        print(f"{Colors.FAIL}[실패] 재부팅 명령 실패{Colors.ENDC}")
        return False


def handle_edl_failure_with_reboot() -> None:
    """
    EDL 통신 실패 처리 - 재부팅 시도 후 사용자 안내
    
    Raises:
        SystemExit: 항상 프로그램 종료 (재부팅 성공/실패 무관)
    """
    from config.constants import UIConstants
    from config.messages import TitleMessages
    from utils.ui import show_popup
    
    print(f"\n{Colors.OKCYAN}[정보] 기기를 재부팅합니다...{Colors.ENDC}")
    
    # 재부팅 시도
    if reboot_device():
        # 재부팅 성공
        print(f"\n{Colors.OKGREEN}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.OKGREEN}✓ 재부팅 명령이 성공적으로 전송되었습니다{Colors.ENDC}")
        print(f"{Colors.OKGREEN}{'=' * 60}{Colors.ENDC}\n")
        
        print(f"{Colors.OKCYAN}기기가 재부팅되었습니다.{Colors.ENDC}")
        print(f"{Colors.OKCYAN}기기가 완전히 부팅될 때까지 기다린 후{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.OKCYAN}프로그램을 다시 실행해주세요.{Colors.ENDC}\n")
        
        show_popup(
            "재부팅 완료",
            "기기 재부팅이 완료되었습니다.\n\n"
            "기기가 완전히 부팅될 때까지 기다린 후\n"
            "프로그램을 다시 실행해주세요.",
            exit_on_close=True,
            icon=UIConstants.ICON_INFO
        )
    else:
        # 재부팅 실패 - 강제 재부팅 안내
        print(f"\n{Colors.FAIL}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.FAIL}[!!!] 재부팅 명령 실패{Colors.ENDC}")
        print(f"{Colors.WARNING}EDL 통신이 끊겨 재부팅 명령을 전송할 수 없습니다.{Colors.ENDC}")
        print(f"{Colors.FAIL}{'=' * 60}{Colors.ENDC}\n")
        
        print(f"{Colors.BOLD}[강제 재부팅 방법]{Colors.ENDC}")
        print(f"  1. PC에서 USB 케이블을 제거하세요")
        print(f"  2. {Colors.OKGREEN}볼륨 다운(-) + 전원 버튼{Colors.ENDC}을 {Colors.BOLD}15초 이상{Colors.ENDC} 누르세요")
        print(f"  3. 태블릿이 꺼질 때까지 계속 누르고 있으세요")
        print(f"  4. 태블릿이 정상 부팅될 때까지 기다리세요")
        print(f"  5. 다시 프로그램을 실행하세요\n")
        
        show_popup(
            TitleMessages.ERROR,
            "EDL 통신 오류 - 강제 재부팅 필요\n\n"
            "기기와의 통신이 끊겨 재부팅 명령을 전송할 수 없습니다.\n\n"
            "【강제 재부팅 방법】\n"
            "1. USB 케이블 제거\n"
            "2. 볼륨 다운(-) + 전원 버튼을 15초 이상 누르기\n"
            "3. 태블릿이 꺼질 때까지 계속 누르기\n"
            "4. 정상 부팅 후 프로그램 재실행",
            exit_on_close=True,
            icon=UIConstants.ICON_ERROR
        )


def handle_gpt_parsing_error() -> None:
    """
    GPT 파싱 에러 처리 - 자동 재부팅 시도 후 실패 시 사용자 안내
    
    Raises:
        SystemExit: 재부팅 실패 시 프로그램 종료
    """
    from config.constants import UIConstants
    from config.messages import TitleMessages
    from utils.ui import show_popup
    
    print(f"\n{Colors.FAIL}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.FAIL}[오류] GPT 파싱 오류 감지{Colors.ENDC}")
    print(f"{Colors.WARNING}EDL 모드에서 파티션 테이블을 읽을 수 없습니다.{Colors.ENDC}")
    print(f"{Colors.OKCYAN}자동으로 기기 재부팅을 시도합니다...{Colors.ENDC}")
    print(f"{Colors.FAIL}{'=' * 60}{Colors.ENDC}\n")
    
    # 재부팅 시도
    if reboot_device():
        print(f"\n{Colors.OKGREEN}재부팅 명령이 성공적으로 전송되었습니다.{Colors.ENDC}")
        print(f"{Colors.OKCYAN}기기가 재부팅될 때까지 잠시 기다린 후{Colors.ENDC}")
        print(f"{Colors.OKCYAN}프로그램을 다시 실행해주세요.{Colors.ENDC}\n")
        input(f"{Colors.WARNING}Enter 키를 눌러 종료...{Colors.ENDC}")
        raise SystemExit(0)
    else:
        # 재부팅 실패 - 강제 재부팅 안내
        print(f"\n{Colors.FAIL}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.FAIL}[!!!] 재부팅 명령 실패{Colors.ENDC}")
        print(f"{Colors.WARNING}기기가 응답하지 않습니다.{Colors.ENDC}")
        print(f"{Colors.FAIL}{'=' * 60}{Colors.ENDC}\n")
        
        print(f"{Colors.BOLD}[강제 재부팅 방법]{Colors.ENDC}")
        print(f"  1. PC에서 USB 케이블을 제거하세요")
        print(f"  2. {Colors.OKGREEN}볼륨 다운(-) + 전원 버튼{Colors.ENDC}을 {Colors.BOLD}15초 이상{Colors.ENDC} 누르세요")
        print(f"  3. 태블릿이 꺼질 때까지 계속 누르고 있으세요")
        print(f"  4. 태블릿이 정상 부팅될 때까지 기다리세요")
        print(f"  5. 다시 프로그램을 실행하세요\n")
        
        show_popup(
            TitleMessages.ERROR,
            "GPT 파싱 오류 - 강제 재부팅 필요\n\n"
            "기기가 응답하지 않습니다.\n\n"
            "【강제 재부팅 방법】\n"
            "1. USB 케이블 제거\n"
            "2. 볼륨 다운(-) + 전원 버튼을 15초 이상 누르기\n"
            "3. 태블릿이 꺼질 때까지 계속 누르기\n"
            "4. 정상 부팅 후 프로그램 재실행",
            exit_on_close=False,
            icon=UIConstants.ICON_ERROR
        )
        
        input(f"\n{Colors.WARNING}Enter 키를 눌러 메뉴로 돌아가기...{Colors.ENDC}")
        
        # EDL 연결 끊김 예외 발생 (메뉴로 돌아감)
        from core.exceptions import EDLConnectionError
        raise EDLConnectionError("GPT 파싱 오류 - 강제 재부팅 필요")


# ============================================================================
# EDLWorkflow 클래스
# ============================================================================

class EDLWorkflow:
    """
    EDL 모드 작업 공통 워크플로우
    
    backup_device.py와 country_code.py의 공통 로직을 통합한 클래스
    """
    
    def __init__(self, title: str, tasks: list):
        """
        Args:
            title: 작업 제목 (예: "기기 정보 백업")
            tasks: 작업 목록 (예: ["ADB 연결", "EDL 진입", ...])
        """
        self.title = title
        self.tasks = tasks
        self.loader_path: Optional[Path] = None
        self.current_task = 0
    
    def initialize(self) -> None:
        """진행률 초기화"""
        init_standalone_progress(self.title, self.tasks)
    
    def finalize(self) -> None:
        """진행률 종료"""
        end_standalone_progress()
    
    def next_task(self, status: str = 'done') -> None:
        """
        다음 작업으로 이동
        
        Args:
            status: 현재 작업 상태 ('done', 'in_progress', 'error')
        """
        if status == 'done':
            update_standalone_task(self.current_task, 'done')
            self.current_task += 1
        
        if self.current_task < len(self.tasks):
            update_standalone_task(self.current_task, 'in_progress')
        
        print_standalone_progress()
    
    def check_adb_device_state(self) -> str:
        """
        ADB 기기 상태 확인
        
        Returns:
            "device", "unauthorized", "not_found" 중 하나
        
        Note:
            내부적으로 utils.device_utils를 사용하지만,
            기존 동작과 100% 동일하게 유지됩니다.
        """
        return util_check_adb_device_state()
    
    def connect_adb(self) -> bool:
        """
        ADB 연결 확인 (재시도 루프 포함)
        
        Returns:
            성공 시 True, 실패 시 False
        """
        print("\n" + "="*50)
        print("[ 1단계 - 1 ] ADB 연결 상태를 확인합니다.")
        print(" * USB 디버깅이 활성화된 상태로 태블릿을 PC에 연결하십시오.")
        print("="*50 + "\n")
        
        while True:
            device_state = self.check_adb_device_state()
            
            if device_state == "device":
                print("\n[성공] 태블릿이 'device' 상태로 정상 연결되었습니다.")
                return True
            
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
                return False
    
    def enter_edl_mode(self) -> bool:
        """
        EDL 모드 진입
        
        Returns:
            성공 시 True
        """
        print("\n[정보] ADB 연결 확인 완료. EDL 모드로 전환합니다...")
        
        # 경고 배너 출력
        print(f"\n{Colors.FAIL}{WARNING_BANNER}{Colors.ENDC}")
        
        run_command([str(ADB_EXE), "reboot", "edl"], "EDL 모드 진입 명령 전송")
        
        wait_seconds = TimingConstants.EDL_BOOT_WAIT
        print(f"\n{Colors.WARNING}[정보] {InfoMessages.EDL_WAIT_MESSAGE.format(seconds=wait_seconds)}{Colors.ENDC}")
        time.sleep(wait_seconds)
        
        return True
    
    def confirm_edl_connection(self) -> bool:
        """
        EDL 연결 확인 (재시도 루프 포함)
        
        Returns:
            성공 시 True, 실패 시 False
        """
        while True:
            clear_screen()
            print_standalone_progress()
            
            print("\n" + "="*50)
            print("[ 1단계 - 2 ] EDL 모드 연결 상태를 확인합니다.")
            print(" * 태블릿 화면이 꺼지고 PC가 장치를 인식할 때까지 기다리십시오.")
            print("="*50)
            print(f"{Colors.WARNING}{Colors.BOLD}{InfoMessages.WARNING_DO_NOT_DISCONNECT}{Colors.ENDC}")
            print("="*50 + "\n")
            
            try:
                if check_edl_connection(self.loader_path):
                    print("\n[성공] 태블릿이 EDL 모드로 정상 연결되었습니다.")
                    return True
            except EDLConnectionError:
                print("\n[진단] EDL 모드 장치를 찾지 못했거나 통신에 실패했습니다.")
                print("  [해결] PC '장치 관리자'에서 'Qualcomm 9008' 드라이버를 확인하거나, 강제 재부팅 후 다시 시도하십시오.")
            
            response = input("\n연결을 다시 확인하려면 Enter, 종료하려면 'q'를 입력하십시오: ").lower()
            if response == 'q':
                return False
    
    def setup_loader(self) -> bool:
        """
        로더 파일 설정
        
        Returns:
            성공 시 True, 실패 시 False
        """
        self.loader_path = select_loader_file()
        if not self.loader_path:
            print(f"{Colors.FAIL}[오류] 로더 파일을 찾을 수 없습니다.{Colors.ENDC}")
            return False
        
        print(f"[정보] 로더 파일: {self.loader_path.name}\n")
        return True
    
    def run_common_steps(self) -> bool:
        """
        공통 단계 실행 (ADB → EDL 진입 → EDL 확인)
        
        Returns:
            성공 시 True, 실패 시 False
        """
        # 로더 파일 설정
        if not self.setup_loader():
            return False
        
        # Task 0: ADB 연결 확인
        if not self.connect_adb():
            return False
        self.next_task('done')
        
        # Task 1: EDL 모드 진입
        if not self.enter_edl_mode():
            return False
        self.next_task('done')
        
        # Task 2: EDL 연결 확인
        if not self.confirm_edl_connection():
            return False
        self.next_task('done')
        
        return True
    
    def cleanup_and_reboot(self, message: str = "Enter 키를 눌러 메뉴로 돌아가기...") -> None:
        """
        정리 및 재부팅
        
        Args:
            message: 사용자에게 표시할 메시지
        """
        print(f"\n[정보] 기기를 재부팅합니다...")
        reboot_device()
        input(f"\n{Colors.WARNING}{message}{Colors.ENDC}")
    
    # ========================================================================
    # 확장 메서드 (Phase 2 - 리팩토링)
    # ========================================================================
    
    def get_slot_info(self) -> Optional[str]:
        """
        활성 슬롯 정보 가져오기 (ADB 사용)
        
        Returns:
            "_a" 또는 "_b", 실패 시 None
        
        Note:
            - ADB 연결이 필요합니다 (connect_adb() 호출 후 사용)
            - 내부적으로 utils.device_utils.get_active_slot() 사용
            - 기존 동작과 100% 동일 (에러 메시지, 입력 대기 포함)
        """
        print(f"\n[정보] 활성 슬롯을 확인합니다...")
        return util_get_active_slot()
    
    def get_model_info(self) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        기기 모델 정보 가져오기 (ADB 사용)
        
        Returns:
            (model_prop, model_name, loader_path) 또는 실패 시 (None, None, None)
        
        Note:
            - ADB 연결이 필요합니다 (connect_adb() 호출 후 사용)
            - 사용자 확인 프롬프트 포함
            - DeviceContext에 로더 자동 설정
            - 내부적으로 utils.device_utils.get_device_model_info() 사용
            - 기존 동작과 100% 동일
        """
        print(f"\n[정보] 연결된 장치의 모델 번호를 확인합니다...")
        return util_get_device_model_info()
    
    def setup_device_context(self) -> tuple[Optional[str], Optional[str]]:
        """
        기기 컨텍스트 설정 (모델 + 슬롯)
        
        Returns:
            (slot_suffix, model_prop) 또는 실패 시 (None, None)
        
        Note:
            - ADB 연결이 필요합니다 (connect_adb() 호출 후 사용)
            - 모델 확인 → 로더 설정 → 슬롯 확인 순서로 진행
            - 기존 step1_extract.py의 동작과 동일한 순서 유지
        
        Example:
            workflow = EDLWorkflow("작업", ["ADB 연결", ...])
            workflow.initialize()
            
            if workflow.connect_adb():
                slot, model = workflow.setup_device_context()
                if slot and model:
                    # EDL 진입...
        """
        # 1. 모델 정보 확인
        model_prop, model_name, loader_path = self.get_model_info()
        if model_prop is None:
            return None, None
        
        # 2. 슬롯 정보 확인
        slot_suffix = self.get_slot_info()
        if slot_suffix is None:
            return None, None
        
        return slot_suffix, model_prop


# ============================================================================
# 파티션 읽기/쓰기 함수
# ============================================================================

def read_partition(loader_path: Path, partition_name: str, output_file: Path, retry: bool = False) -> bool:
    """
    파티션 읽기 (재시도 포함)
    
    Args:
        loader_path: 로더 파일 경로
        partition_name: 파티션 이름
        output_file: 출력 파일 경로
        retry: 재시도 여부 (내부 사용)
        
    Returns:
        성공 시 True
        
    Raises:
        EDLConnectionError: 연결 끊김 시 (재시도 후에도 실패)
    """
    from core.logger import info, log_edl_operation
    
    if retry:
        info(f"파티션 읽기 재시도", partition=partition_name, retry=True)
        print(f"{Colors.WARNING}[재시도] '{partition_name}' 다시 추출 시도...{Colors.ENDC}")
    else:
        info(f"파티션 읽기 시작", partition=partition_name, output=str(output_file))
        print(f"[정보] '{partition_name}' 추출 시도...")
    
    success, error_output, _ = run_command(
        [str(EDL_NG_EXE), "--loader", str(loader_path), "read-part", partition_name, str(output_file)],
        f"{partition_name} 파티션 읽기"
    )
    
    if success and output_file.exists():
        file_size = output_file.stat().st_size
        log_edl_operation("read", partition_name, True)
        info(f"파티션 읽기 성공", partition=partition_name, size_bytes=file_size, retry=retry)
        if retry:
            print(f"{Colors.OKGREEN}[재시도 성공] {output_file.name} ({file_size:,} bytes){Colors.ENDC}")
        else:
            print(f"[성공] {output_file.name} ({file_size:,} bytes)")
        return True
    else:
        log_edl_operation("read", partition_name, False, error_output)
        print(f"{Colors.FAIL}[실패] {partition_name} 파티션 읽기 실패{Colors.ENDC}")
        
        # EDL 연결 끊김 확인
        if is_edl_disconnection_error(error_output):
            # 불완전한 파일 삭제
            if output_file.exists():
                try:
                    output_file.unlink()
                    print(f"[정보] 불완전한 파일 '{output_file.name}'을(를) 삭제했습니다.")
                except Exception as e:
                    print(f"[경고] 파일 삭제 실패: {e}")
            
            # 재시도 로직
            if not retry:
                # 첫 번째 실패 → 1회 재시도
                print(f"\n{Colors.WARNING}{'='*60}{Colors.ENDC}")
                print(f"{Colors.WARNING}[경고] EDL 통신 오류 발생 - 재시도 합니다{Colors.ENDC}")
                print(f"{Colors.WARNING}{'='*60}{Colors.ENDC}\n")
                time.sleep(2)  # 2초 대기
                
                # 재시도
                return read_partition(loader_path, partition_name, output_file, retry=True)
            else:
                # 재시도도 실패 → 재부팅 시도 후 종료
                print(f"\n{Colors.FAIL}{'='*60}{Colors.ENDC}")
                print(f"{Colors.FAIL}[오류] 재시도도 실패했습니다. 기기를 재부팅합니다.{Colors.ENDC}")
                print(f"{Colors.FAIL}{'='*60}{Colors.ENDC}\n")
                
                # 재부팅 시도
                handle_edl_failure_with_reboot()
                
                # 여기까지 오면 재부팅 실패 → 강제 종료
                raise EDLConnectionError("EDL 연결 끊김 (재시도 및 재부팅 실패)")
        
        return False


def write_partition(loader_path: Path, partition_name: str, input_file: Path, retry: bool = False) -> bool:
    """
    파티션 쓰기 (재시도 포함)
    
    Args:
        loader_path: 로더 파일 경로
        partition_name: 파티션 이름
        input_file: 입력 파일 경로
        retry: 재시도 여부 (내부 사용)
        
    Returns:
        성공 시 True
        
    Raises:
        EDLConnectionError: 연결 끊김 시 (재시도 후에도 실패)
    """
    from core.logger import info, log_edl_operation
    
    if retry:
        info(f"파티션 쓰기 재시도", partition=partition_name, retry=True)
        print(f"{Colors.WARNING}[재시도] '{partition_name}' 파티션에 다시 쓰는 중...{Colors.ENDC}")
    else:
        info(f"파티션 쓰기 시작", partition=partition_name, input=str(input_file))
        print(f"[정보] '{partition_name}' 파티션에 쓰는 중...")
    
    success, error_output, _ = run_command(
        [str(EDL_NG_EXE), "--loader", str(loader_path), "write-part", partition_name, str(input_file)],
        f"{partition_name} 파티션 쓰기"
    )
    
    if success:
        log_edl_operation("write", partition_name, True)
        info(f"파티션 쓰기 성공", partition=partition_name, retry=retry)
        if retry:
            print(f"{Colors.OKGREEN}[재시도 성공] {partition_name} 파티션 쓰기 완료{Colors.ENDC}")
        else:
            print(f"[성공] {partition_name} 파티션 쓰기 완료")
        return True
    else:
        log_edl_operation("write", partition_name, False, error_output)
        print(f"{Colors.FAIL}[실패] {partition_name} 파티션 쓰기 실패{Colors.ENDC}")
        
        # EDL 연결 끊김 확인
        if is_edl_disconnection_error(error_output):
            # 재시도 로직
            if not retry:
                # 첫 번째 실패 → 1회 재시도
                print(f"\n{Colors.WARNING}{'='*60}{Colors.ENDC}")
                print(f"{Colors.WARNING}[경고] EDL 통신 오류 발생 - 재시도 합니다{Colors.ENDC}")
                print(f"{Colors.WARNING}{'='*60}{Colors.ENDC}\n")
                time.sleep(2)  # 2초 대기
                
                # 재시도
                return write_partition(loader_path, partition_name, input_file, retry=True)
            else:
                # 재시도도 실패 → 재부팅 시도 후 종료
                print(f"\n{Colors.FAIL}{'='*60}{Colors.ENDC}")
                print(f"{Colors.FAIL}[오류] 재시도도 실패했습니다. 기기를 재부팅합니다.{Colors.ENDC}")
                print(f"{Colors.FAIL}{'='*60}{Colors.ENDC}\n")
                
                # 재부팅 시도
                handle_edl_failure_with_reboot()
                
                # 여기까지 오면 재부팅 실패 → 강제 종료
                raise EDLConnectionError("EDL 연결 끊김 (재시도 및 재부팅 실패)")
        
        return False

