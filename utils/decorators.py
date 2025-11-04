"""유용한 데코레이터 - 프로덕션 수준"""
import functools
import traceback
from typing import Callable, Any

from config.constants import UIConstants
from config.colors import Colors
from utils.ui import show_popup
from core.progress import global_end_progress
from core.logger import log_error


def handle_step_error(step_name: str, exit_on_error: bool = True) -> Callable:
    """
    STEP 실행 중 에러를 깔끔하게 처리하는 데코레이터 (traceback 포함)
    
    Args:
        step_name: STEP 이름 (예: "STEP 1")
        exit_on_error: 에러 발생 시 프로그램 종료 여부
    """
    def decorator(func: Callable) -> Callable:
        """데코레이터 wrapper"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            """함수 실행 wrapper"""
            try:
                return func(*args, **kwargs)
            except KeyboardInterrupt:
                global_end_progress()
                error_msg = f"사용자가 {step_name} 실행을 중단했습니다."
                print(f"\n\n{Colors.WARNING}[중단] {error_msg}{Colors.ENDC}")
                log_error(error_msg, context=f"{step_name} - 사용자 중단")
                if exit_on_error:
                    show_popup(f"{step_name} 중단", "사용자가 작업을 취소했습니다.", icon=UIConstants.ICON_WARNING)
                return None
            except Exception as e:
                global_end_progress()
                error_msg = f"{step_name} 실행 중 예상치 못한 오류 발생"
                print(f"\n\n{Colors.FAIL}{'='*60}{Colors.ENDC}")
                print(f"{Colors.FAIL}[오류] {error_msg}{Colors.ENDC}")
                print(f"{Colors.FAIL}예외 타입: {type(e).__name__}{Colors.ENDC}")
                print(f"{Colors.FAIL}예외 내용: {e}{Colors.ENDC}")
                print(f"{Colors.FAIL}{'='*60}{Colors.ENDC}")
                print(f"\n{Colors.WARNING}[Traceback]{Colors.ENDC}")
                # 로그 파일에 상세 기록
                log_error(error_msg, exception=e, context=f"{step_name}")
                
                if exit_on_error:
                    show_popup(
                        f"{step_name} 실패",
                        f"오류가 발생했습니다:\n\n{type(e).__name__}: {e}\n\n로그 파일을 확인하세요.",
                        icon=UIConstants.ICON_ERROR,
                        exit_on_close=True
                    )
                return None
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay_seconds: float = 1.0) -> Callable:
    """
    실패 시 재시도하는 데코레이터 (에러 로깅 포함)
    
    Args:
        max_retries: 최대 재시도 횟수
        delay_seconds: 재시도 간 대기 시간 (초)
    """
    def decorator(func: Callable) -> Callable:
        """데코레이터 wrapper"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            """함수 실행 wrapper"""
            import time
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"{Colors.WARNING}[재시도 {attempt + 1}/{max_retries}] {func.__name__} 실패: {e}{Colors.ENDC}")
                        time.sleep(delay_seconds)
                    else:
                        error_msg = f"{func.__name__}이(가) {max_retries}번 시도 후 실패"
                        print(f"{Colors.FAIL}[실패] {error_msg}{Colors.ENDC}")
                        log_error(error_msg, exception=e, context=f"재시도 데코레이터 - {func.__name__}")
                        raise
            return None
        return wrapper
    return decorator


def log_execution_time(func: Callable) -> Callable:
    """함수 실행 시간을 측정하고 출력하는 데코레이터 (에러 로깅 포함)"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        """함수 실행 wrapper"""
        import time
        
        start_time = time.time()
        print(f"{Colors.OKCYAN}[시작] {func.__name__} 실행 중...{Colors.ENDC}")
        
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            print(f"{Colors.OKGREEN}[완료] {func.__name__} 실행 완료 (소요 시간: {elapsed:.2f}초){Colors.ENDC}")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = f"{func.__name__} 실행 실패 (소요 시간: {elapsed:.2f}초)"
            print(f"{Colors.FAIL}[실패] {error_msg}{Colors.ENDC}")
            log_error(error_msg, exception=e, context=f"실행 시간 측정 - {func.__name__}")
            raise
    
    return wrapper

