"""로깅 시스템 - structlog 기반 구조화 로깅"""
import os
import sys
import re
import logging
import platform
import structlog
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict

from config.paths import LOGS_DIR


# ============================================================================
# structlog 프로세서 (ANSI 색상 제거)
# ============================================================================

def strip_ansi_processor(logger: Any, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """로그 파일에서 ANSI 색상 코드 제거"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    
    # event (메시지) 처리
    if 'event' in event_dict and isinstance(event_dict['event'], str):
        event_dict['event'] = ansi_escape.sub('', event_dict['event'])
    
    # 다른 필드도 처리
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = ansi_escape.sub('', value)
    
    return event_dict


# ============================================================================
# Print 캡처 클래스
# ============================================================================

class PrintCapture:
    """print()를 structlog으로 자동 라우팅"""
    
    def __init__(self, logger_instance: logging.Logger, original_stdout: Any, file_handler: logging.FileHandler) -> None:
        """
        Print 캡처 초기화
        
        Args:
            logger_instance: 로거 인스턴스
            original_stdout: 원본 stdout
            file_handler: 파일 핸들러
        """
        self.logger = logger_instance
        self.terminal = original_stdout
        self.file_handler = file_handler
    
    def write(self, message: str) -> None:
        """print() 호출 시 자동 호출됨"""
        # 터미널에도 출력 (기존 동작 유지)
        self.terminal.write(message)
        self.terminal.flush()
        
        # 로그 파일에도 기록
        if self.file_handler and message:
            # ANSI 코드 제거
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_message = ansi_escape.sub('', message)
            
            # 파일에 직접 기록
            self.file_handler.stream.write(clean_message)
            self.file_handler.stream.flush()
    
    def flush(self) -> None:
        """버퍼 플러시"""
        self.terminal.flush()


# ============================================================================
# 전역 변수
# ============================================================================

app_logger = None
log_file_path = None
start_time = None
step_timings = {}
original_stdout = None
file_handler = None


# ============================================================================
# 로거 초기화
# ============================================================================

def init_logger(level: int = logging.INFO) -> None:
    """
    structlog 로거 초기화 + print() 자동 캡처
    
    Args:
        level: 로깅 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    global app_logger, log_file_path, start_time, original_stdout, file_handler
    
    if app_logger is not None:
        return  # 이미 초기화됨
    
    # 로그 디렉토리 생성
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 로그 파일명 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"process_log_{timestamp}.txt"
    log_file_path = LOGS_DIR / log_filename
    
    # 시작 시간 기록
    start_time = datetime.now()
    
    # 원본 stdout 백업
    original_stdout = sys.stdout
    
    # ========================================================================
    # 표준 logging 설정 (structlog가 이를 사용)
    # ========================================================================
    
    # 파일 핸들러 생성
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8', mode='w')
    file_handler.setLevel(logging.DEBUG)
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    
    # ========================================================================
    # structlog 설정
    # ========================================================================
    
    structlog.configure(
        processors=[
            # Context 추가
            structlog.contextvars.merge_contextvars,
            # 타임스탬프 추가
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            # 로그 레벨 추가
            structlog.processors.add_log_level,
            # 스택 정보 추가 (에러 시)
            structlog.processors.StackInfoRenderer(),
            # Exception 포매팅
            structlog.processors.format_exc_info,
            # ANSI 색상 제거 (파일용)
            strip_ansi_processor,
            # 최종 렌더링 (파일은 KeyValue 형식)
            structlog.processors.KeyValueRenderer(
                key_order=['timestamp', 'level', 'event'],
                drop_missing=True
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # structlog 로거 생성
    app_logger = structlog.get_logger('rom_tool')
    
    # 로그 헤더 작성
    _write_log_header()
    
    # ========================================================================
    # print()를 logging으로 자동 라우팅
    # ========================================================================
    sys.stdout = PrintCapture(app_logger, original_stdout, file_handler)
    sys.stderr = PrintCapture(app_logger, sys.__stderr__, file_handler)
    
    print(f"[정보] 로그 파일: {log_file_path}\n")


def _write_log_header() -> None:
    """로그 파일 헤더 작성 (시스템 정보)"""
    if not file_handler:
        return
    
    # 직접 파일에 헤더 작성
    file_handler.stream.write(f"{'='*80}\n")
    file_handler.stream.write(f"{'통합 롬파일 패치 도구 - 실행 로그 (structlog)':^80}\n")
    file_handler.stream.write(f"{'='*80}\n\n")
    
    file_handler.stream.write(f"[시스템 정보]\n")
    file_handler.stream.write(f"  시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    file_handler.stream.write(f"  Python 버전: {sys.version.split()[0]}\n")
    file_handler.stream.write(f"  운영체제: {platform.system()} {platform.release()}\n")
    file_handler.stream.write(f"  플랫폼: {platform.platform()}\n")
    file_handler.stream.write(f"  아키텍처: {platform.machine()}\n")
    file_handler.stream.write(f"  프로세서: {platform.processor()}\n")
    file_handler.stream.write(f"  작업 디렉토리: {os.getcwd()}\n")
    file_handler.stream.write(f"  Python 실행 파일: {sys.executable}\n")
    file_handler.stream.write(f"\n{'='*80}\n\n")
    file_handler.stream.flush()


def close_logger() -> None:
    """로거 종료 (요약 정보 작성 + stdout 복구)"""
    global app_logger, start_time, step_timings, original_stdout, file_handler
    
    if not file_handler:
        return
    
    # 종료 요약 작성
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    
    file_handler.stream.write(f"\n\n{'='*80}\n")
    file_handler.stream.write(f"{'실행 완료':^80}\n")
    file_handler.stream.write(f"{'='*80}\n")
    file_handler.stream.write(f"  종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    file_handler.stream.write(f"  총 소요 시간: {elapsed:.2f}초 ({elapsed/60:.2f}분)\n")
    
    if step_timings:
        file_handler.stream.write(f"\n[STEP별 소요 시간]\n")
        for step_name, duration in step_timings.items():
            file_handler.stream.write(f"  {step_name}: {duration:.2f}초 ({duration/60:.2f}분)\n")
    
    file_handler.stream.write(f"{'='*80}\n")
    file_handler.stream.flush()
    
    # stdout, stderr 복구
    if original_stdout:
        sys.stdout = original_stdout
        sys.stderr = sys.__stderr__
    
    # 핸들러 정리
    if file_handler:
        file_handler.close()
    
    app_logger = None


# ============================================================================
# structlog 편의 함수
# ============================================================================

def get_logger() -> Optional[logging.Logger]:
    """현재 로거 반환"""
    return app_logger


def debug(msg: str, **context) -> None:
    """DEBUG 레벨 로그 (구조화 데이터 추가 가능)"""
    if app_logger:
        app_logger.debug(msg, **context)


def info(msg: str, **context) -> None:
    """INFO 레벨 로그 (구조화 데이터 추가 가능)"""
    if app_logger:
        app_logger.info(msg, **context)


def warning(msg: str, **context) -> None:
    """WARNING 레벨 로그 (구조화 데이터 추가 가능)"""
    if app_logger:
        app_logger.warning(msg, **context)


def error(msg: str, **context) -> None:
    """ERROR 레벨 로그 (구조화 데이터 추가 가능)"""
    if app_logger:
        app_logger.error(msg, **context)


def critical(msg: str, **context) -> None:
    """CRITICAL 레벨 로그 (구조화 데이터 추가 가능)"""
    if app_logger:
        app_logger.critical(msg, **context)


# ============================================================================
# Context 관리 (structlog의 강력한 기능)
# ============================================================================

def bind_context(**context) -> None:
    """
    영구 Context 추가 (해당 로거의 모든 로그에 자동 포함)
    
    예시:
        bind_context(step="STEP1", device_model="TB520FU")
        # 이후 모든 로그에 step, device_model이 자동 포함됨
    """
    if app_logger:
        structlog.contextvars.bind_contextvars(**context)


def unbind_context(*keys) -> None:
    """Context 제거"""
    if app_logger:
        structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """모든 Context 제거"""
    if app_logger:
        structlog.contextvars.clear_contextvars()


# ============================================================================
# 기존 함수 호환성 유지
# ============================================================================

def log_command_output(command, stdout, stderr, success) -> None:
    """
    명령어 실행 결과 로깅 (구조화)
    
    Args:
        command: 실행한 명령어
        stdout: 표준 출력
        stderr: 표준 에러 출력
        success: 성공 여부
    """
    if not app_logger:
        return
    
    # structlog로 구조화 로깅
    level = "info" if success else "error"
    
    getattr(app_logger, level)(
        "명령어 실행",
        command=' '.join(command) if isinstance(command, list) else command,
        success=success,
        stdout=stdout[:500] if stdout else "",  # 길이 제한
        stderr=stderr[:500] if stderr else "",
    )


def log_error(error_msg: str, exception: Optional[Exception] = None, context: str = "") -> None:
    """
    에러 상세 로깅 (traceback 포함)
    
    Args:
        error_msg: 에러 메시지
        exception: Exception 객체 (traceback 자동 포함)
        context: 에러 발생 컨텍스트
    """
    if not app_logger:
        return
    
    error_data = {
        "error_msg": error_msg,
        "context": context,
    }
    
    if exception:
        app_logger.error("⚠️  에러 발생", exc_info=exception, **error_data)
    else:
        app_logger.error("⚠️  에러 발생", **error_data)


def log_step_start(step_name: str) -> None:
    """
    STEP 시작 로깅 + Context 바인딩
    
    Args:
        step_name: STEP 이름 (예: "STEP 1")
    """
    global step_timings
    
    if not app_logger:
        return
    
    # Context에 step_name 추가 (이후 모든 로그에 자동 포함)
    bind_context(step=step_name)
    
    # 파일에 구분선 작성
    if file_handler:
        file_handler.stream.write(f"\n{'█'*80}\n")
        file_handler.stream.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {step_name} 시작\n")
        file_handler.stream.write(f"{'█'*80}\n\n")
        file_handler.stream.flush()
    
    # 타이밍 시작
    if not hasattr(app_logger, '_step_start_times'):
        app_logger._step_start_times = {}
    app_logger._step_start_times[step_name] = datetime.now()
    
    # structlog 로그
    app_logger.info(f"{step_name} 시작", step_name=step_name)


def log_step_end(step_name: str, success: bool = True) -> None:
    """
    STEP 종료 로깅 (소요 시간 포함)
    
    Args:
        step_name: STEP 이름
        success: 성공 여부
    """
    global step_timings
    
    if not app_logger:
        return
    
    # 소요 시간 계산
    duration = 0
    if hasattr(app_logger, '_step_start_times') and step_name in app_logger._step_start_times:
        start = app_logger._step_start_times[step_name]
        duration = (datetime.now() - start).total_seconds()
        step_timings[step_name] = duration
    
    status = "✓ 성공" if success else "✗ 실패"
    
    # 파일에 구분선 작성
    if file_handler:
        file_handler.stream.write(f"\n{'─'*80}\n")
        file_handler.stream.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {step_name} 완료: {status}\n")
        file_handler.stream.write(f"소요 시간: {duration:.2f}초 ({duration/60:.2f}분)\n")
        file_handler.stream.write(f"{'─'*80}\n\n")
        file_handler.stream.flush()
    
    # structlog 로그
    app_logger.info(
        f"{step_name} 완료",
        step_name=step_name,
        success=success,
        duration_sec=duration,
        status=status
    )
    
    # Context 제거
    unbind_context("step")


# ============================================================================
# 추가: 상세 로깅 헬퍼 함수
# ============================================================================

def log_validation(item: str, result: bool, details: str = "") -> None:
    """
    검증 결과 로깅
    
    Args:
        item: 검증 항목 (예: "모델 번호")
        result: 검증 결과 (True/False)
        details: 상세 정보
    """
    if not app_logger:
        return
    
    status = "✓ OK" if result else "✗ NG"
    level = "info" if result else "warning"
    
    getattr(app_logger, level)(
        f"검증: {item}",
        item=item,
        result=status,
        details=details
    )


def log_extraction(partition: str, success: bool, details: Dict[str, Any] = None) -> None:
    """
    파티션 추출 로깅
    
    Args:
        partition: 파티션 이름
        success: 성공 여부
        details: 상세 정보 (dict)
    """
    if not app_logger:
        return
    
    level = "info" if success else "error"
    
    log_data = {
        "partition": partition,
        "success": success,
    }
    
    if details:
        log_data.update(details)
    
    getattr(app_logger, level)(
        f"파티션 추출: {partition}",
        **log_data
    )


def log_patch(operation: str, target: str, success: bool, details: str = "") -> None:
    """
    패치 작업 로깅
    
    Args:
        operation: 작업 이름 (예: "vbmeta 서명 제거")
        target: 대상 파일/파티션
        success: 성공 여부
        details: 상세 정보
    """
    if not app_logger:
        return
    
    level = "info" if success else "error"
    
    getattr(app_logger, level)(
        f"패치: {operation}",
        operation=operation,
        target=target,
        success=success,
        details=details
    )


def log_edl_operation(operation: str, partition: str, success: bool, error_msg: str = "") -> None:
    """
    EDL 작업 로깅
    
    Args:
        operation: 작업 유형 (read/write/erase)
        partition: 파티션 이름
        success: 성공 여부
        error_msg: 에러 메시지
    """
    if not app_logger:
        return
    
    level = "info" if success else "error"
    
    getattr(app_logger, level)(
        f"EDL {operation.upper()}",
        operation=operation,
        partition=partition,
        success=success,
        error=error_msg
    )


# ============================================================================
# print() 대체는 필요 없음 (자동 캡처됨)
# ============================================================================
