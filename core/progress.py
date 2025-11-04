"""진행률 표시 시스템"""
import sys
from typing import List, Optional
from config.colors import Colors

# 전역 진행 상태
current_main_step = 0
total_main_steps = 4
current_sub_step = 0
total_sub_steps = 0
step_name = ""
sub_tasks = []

def init_step_progress(main_step_num: int, sub_step_count: int, task_names: List[str]) -> None:
    """STEP 진행률 초기화"""
    global current_main_step, current_sub_step, total_sub_steps, sub_tasks, step_name
    current_main_step = main_step_num
    current_sub_step = 0
    total_sub_steps = sub_step_count
    step_name = f"STEP {main_step_num}"
    sub_tasks = [(name, 'pending') for name in task_names]
    print_hierarchical_progress()

def update_sub_task(task_index: int, status: str) -> None:
    """서브 작업 상태 업데이트"""
    global sub_tasks
    if 0 <= task_index < len(sub_tasks):
        task_name, _ = sub_tasks[task_index]
        sub_tasks[task_index] = (task_name, status)

def print_hierarchical_progress() -> None:
    """계층적 진행률 출력"""
    bar_length = 20
    
    overall_percent = (current_main_step / total_main_steps) * 100 if total_main_steps > 0 else 0
    print(f"\n{Colors.BOLD}{'━' * 50}{Colors.ENDC}")
    print(f"{Colors.OKCYAN}전체 진행: STEP {current_main_step}/{total_main_steps} ({overall_percent:.0f}%){Colors.ENDC}")
    print(f"{Colors.BOLD}{'━' * 50}{Colors.ENDC}")
    
    if total_sub_steps > 0:
        sub_percent = (current_sub_step / total_sub_steps) * 100
        filled = int(bar_length * current_sub_step / total_sub_steps)
        bar = '█' * filled + '-' * (bar_length - filled)
        
        step_titles = {
            1: "기기 정보 추출",
            2: "롬파일 분석 및 백업",
            3: "롬파일 패치",
            4: "패치 검증"
        }
        step_title = step_titles.get(current_main_step, "진행 중")
        print(
            f"\n{Colors.OKGREEN}[{step_name}: {step_title}]{Colors.ENDC} "
            f"{bar} {Colors.OKBLUE}{sub_percent:.0f}%{Colors.ENDC}\n"
        )
        
        if sub_tasks:
            for task_name, status in sub_tasks:
                if status == 'done':
                    print(f"  {Colors.OKGREEN}✓{Colors.ENDC} {task_name}")
                elif status == 'in_progress':
                    print(f"  {Colors.OKCYAN}→{Colors.ENDC} {task_name}")
                else:
                    print(f"  {Colors.WARNING}○{Colors.ENDC} {task_name}")
    print()

def global_print_progress(current_step: int, total_steps: int, description: str) -> None:
    """전역 진행률 표시"""
    global current_sub_step, total_sub_steps
    current_sub_step = current_step
    total_sub_steps = total_steps
    print_hierarchical_progress()

def global_end_progress() -> None:
    """진행률 표시 종료"""
    sys.stdout.flush()


# ============================================================================
# 독립 작업용 프로그레스 (STEP 번호 없는 유틸리티 작업)
# 
# 설계 참고:
# - STEP 프로그레스: 메인 STEP 1-4 작업용 (전체 진행률 표시)
# - Standalone 프로그레스: 백업, 국가코드 변경 등 독립 작업용
# - 두 시스템은 사용 컨텍스트가 다르므로 분리 유지
# ============================================================================

_standalone_tasks = []
_standalone_title = ""
_standalone_overall_step = None  # (현재_STEP, 전체_STEP) 튜플

def init_standalone_progress(title: str, task_names: List[str], 
                             overall_step: Optional[tuple] = None) -> None:
    """독립 작업 진행률 초기화
    
    Args:
        title: 작업 제목 (예: "국가코드 변경 (CN→KR)")
        task_names: 작업 이름 리스트
        overall_step: (현재_STEP, 전체_STEP) 튜플. 예: (2, 4)
                     None이면 전체 진행 헤더 표시하지 않음
    """
    global _standalone_tasks, _standalone_title, _standalone_overall_step
    _standalone_title = title
    _standalone_tasks = [(name, 'pending') for name in task_names]
    _standalone_overall_step = overall_step
    print_standalone_progress()


def update_standalone_task(task_index: int, status: str) -> None:
    """독립 작업 상태 업데이트
    
    Args:
        task_index: 작업 인덱스
        status: 'pending', 'in_progress', 'done', 'error'
    """
    global _standalone_tasks
    if 0 <= task_index < len(_standalone_tasks):
        task_name, _ = _standalone_tasks[task_index]
        _standalone_tasks[task_index] = (task_name, status)


def print_standalone_progress() -> None:
    """독립 작업 진행률 출력"""
    bar_length = 20
    
    if not _standalone_tasks:
        return
    
    # 완료된 작업 개수 계산
    done_count = sum(1 for _, status in _standalone_tasks if status == 'done')
    total_count = len(_standalone_tasks)
    percent = (done_count / total_count * 100) if total_count > 0 else 0
    
    # 프로그레스 바
    filled = int(bar_length * done_count / total_count) if total_count > 0 else 0
    bar = '█' * filled + '-' * (bar_length - filled)
    
    # 전체 진행 헤더 (설정된 경우만 표시)
    print(f"\n{'━' * 50}")
    if _standalone_overall_step:
        current_step, total_steps = _standalone_overall_step
        overall_percent = int((current_step / total_steps) * 100)
        print(f"{Colors.OKCYAN}전체 진행: STEP {current_step}/{total_steps} ({overall_percent}%){Colors.ENDC}")
        print(f"{'━' * 50}\n")
    
    print(f"{Colors.OKGREEN}[{_standalone_title}]{Colors.ENDC} {bar} {Colors.OKBLUE}{percent:.0f}%{Colors.ENDC}\n")
    
    # 작업 목록
    for task_name, status in _standalone_tasks:
        if status == 'done':
            print(f"  {Colors.OKGREEN}✓{Colors.ENDC} {task_name}")
        elif status == 'in_progress':
            print(f"  {Colors.OKCYAN}→{Colors.ENDC} {task_name}")
        elif status == 'error':
            print(f"  {Colors.FAIL}✗{Colors.ENDC} {task_name}")
        else:  # pending
            print(f"  {Colors.WARNING}○{Colors.ENDC} {task_name}")
    
    print()


def end_standalone_progress() -> None:
    """독립 작업 진행률 종료"""
    global _standalone_tasks, _standalone_title, _standalone_overall_step
    _standalone_tasks = []
    _standalone_title = ""
    _standalone_overall_step = None
    sys.stdout.flush()


class ProgressTask:
    """
    진행률 작업 Context Manager
    
    사용 예시:
        with ProgressTask(task_index=5, step_current=3, step_total=10, step_name="STEP 3"):
            # 작업 수행
            pass
        # 자동으로 완료 처리됨
    """
    def __init__(self, task_index: int, step_current: int, step_total: int, step_name: str):
        """ProgressTask 초기화"""
        self.task_index = task_index
        self.step_current = step_current
        self.step_total = step_total
        self.step_name = step_name
    
    def __enter__(self) -> 'ProgressTask':
        """Context Manager 진입"""
        update_sub_task(self.task_index, 'in_progress')
        global_print_progress(self.step_current, self.step_total, self.step_name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context Manager 종료"""
        if exc_type is None:
            # 성공적으로 완료
            update_sub_task(self.task_index, 'done')
            global_print_progress(self.step_current + 1, self.step_total, self.step_name)
        else:
            # 에러 발생
            update_sub_task(self.task_index, 'error')
            global_end_progress()
        return False  # 예외를 다시 raise


class StepProgress:
    """
    STEP 전체 진행률 관리 Context Manager
    
    사용 예시:
        with StepProgress(step_num=3, total_tasks=10, task_names=["작업1", "작업2", ...]) as progress:
            progress.task(0)  # 작업 0 시작
            # ... 작업 수행 ...
            progress.complete_task(0)  # 작업 0 완료
    """
    def __init__(self, step_num: int, total_tasks: int, task_names: List[str]):
        """StepProgress 초기화"""
        self.step_num = step_num
        self.total_tasks = total_tasks
        self.task_names = task_names
        self.current_task = 0
    
    def __enter__(self) -> 'StepProgress':
        """Context Manager 진입"""
        init_step_progress(self.step_num, self.total_tasks, self.task_names)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Context Manager 종료"""
        global_end_progress()
        return False
    
    def task(self, task_index: int) -> None:
        """작업 시작"""
        update_sub_task(task_index, 'in_progress')
        self.current_task = task_index
        global_print_progress(task_index, self.total_tasks, f"STEP {self.step_num}")
    
    def complete_task(self, task_index: int) -> None:
        """작업 완료"""
        update_sub_task(task_index, 'done')
        global_print_progress(task_index + 1, self.total_tasks, f"STEP {self.step_num}")

