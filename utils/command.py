"""명령어 실행 유틸리티"""
import subprocess
import os
import sys
from typing import List, Tuple
from pathlib import Path
from core.logger import log_command_output
from core.progress import global_end_progress
from config.colors import Colors
from config.paths import TOOL_DIR, ROOTING_TOOL_DIR

def run_command(command: List[str], step_name: str = "", check: bool = True) -> Tuple[bool, str, str]:
    """
    명령어 실행 (통합 버전)
    
    Args:
        command: 실행할 명령어 리스트
        step_name: 작업 이름 (로깅용, 선택사항)
        check: True이면 실패 시 예외 발생, False이면 실패해도 계속 진행
        
    Returns:
        (성공 여부, stdout, stderr) 튜플
    """
    try:
        process = subprocess.run(
            command, check=check, text=True, 
            encoding='utf-8', errors='ignore', 
            capture_output=True
        )
        log_command_output(command, process.stdout, process.stderr, True)
        return True, process.stdout, process.stderr
    except subprocess.CalledProcessError as e:
        stdout_output = e.stdout if hasattr(e, 'stdout') and e.stdout else ""
        stderr_output = e.stderr if e.stderr else ""
        
        if stderr_output:
            print(f"오류 로그:\n{stderr_output.strip()}")
        log_command_output(command, stdout_output, stderr_output, False)
        return False, stdout_output, stderr_output
    except FileNotFoundError:
        print(f"[실패] 명령어를 찾을 수 없습니다: {command[0]}")
        if command[0] == "python":
            print("[진단] Python이 설치되어 있고 PATH에 등록되어 있는지 확인하십시오.")
        log_command_output(command, "", f"FileNotFoundError: {command[0]}", False)
        return False, "", f"FileNotFoundError: {command[0]}"

def run_adb_command(command: List[str], step_name: str = "") -> Tuple[bool, str, str]:
    """
    ADB 명령 실행 (별칭)
    
    Args:
        command: ADB 명령어 리스트
        step_name: 작업 이름 (로깅용)
        
    Returns:
        (성공 여부, stdout, stderr) 튜플
    """
    return run_command(command, step_name)

def run_external_command(cmd_params: List[str], suppress_output: bool = False) -> bool:
    """
    외부 명령 실행 (STEP 3/4용)
    
    Args:
        cmd_params: 실행할 명령어 및 인자 리스트
        suppress_output: True이면 출력 억제
        
    Returns:
        성공 시 True, 실패 시 False
    """
    env = os.environ.copy()
    env['PATH'] = str(TOOL_DIR) + os.pathsep + str(ROOTING_TOOL_DIR) + os.pathsep + env['PATH']
    
    if not suppress_output:
        print(f"  [실행] > {' '.join([Path(p).name for p in cmd_params[:3]])}...")
    
    try:
        process = subprocess.run(
            cmd_params, check=True, capture_output=True, text=True,
            encoding='utf-8', errors='ignore', env=env
        )
        log_command_output(cmd_params, process.stdout, process.stderr, True)
        if process.stderr:
            global_end_progress()
            sys.stderr.write(f"{Colors.WARNING}")
            for line in process.stderr.strip().split('\n'):
                sys.stderr.write(f"  [STDERR] {line}\n")
            sys.stderr.write(f"{Colors.ENDC}")
            sys.stderr.flush()
        return True
    except subprocess.CalledProcessError as e:
        global_end_progress()
        log_command_output(cmd_params, e.stdout if hasattr(e, 'stdout') else "", e.stderr, False)
        print(f"\n  {Colors.FAIL}[오류] 명령 실행에 실패했습니다 (코드: {e.returncode}){Colors.ENDC}", file=sys.stderr)
        print(f"  {Colors.FAIL}[STDOUT]:\n{e.stdout.strip()}{Colors.ENDC}", file=sys.stderr)
        print(f"  {Colors.FAIL}[STDERR]:\n{e.stderr.strip()}{Colors.ENDC}", file=sys.stderr)
        return False
    except FileNotFoundError:
        global_end_progress()
        log_command_output(cmd_params, "", f"FileNotFoundError: {cmd_params[0]}", False)
        print(f"\n  {Colors.FAIL}[오류] 명령을 찾을 수 없습니다: {cmd_params[0]}{Colors.ENDC}", file=sys.stderr)
        return False

