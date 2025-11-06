"""커스텀 예외 클래스

프로젝트 전반에서 사용되는 커스텀 예외들을 정의합니다.
표준 Exception 대신 이 예외들을 사용하면 더 정밀한 에러 처리가 가능합니다.
"""


# EDL 관련 예외


class EDLConnectionError(Exception):
    """EDL 모드 중 연결이 끊겼을 때 발생하는 예외"""
    pass


class LoaderNotFoundError(Exception):
    """로더 파일을 찾을 수 없을 때 발생하는 예외"""
    pass


class EDLModeEntryError(Exception):
    """EDL 모드 진입에 실패했을 때 발생하는 예외"""
    pass


class EDLConnectionFailedError(Exception):
    """EDL 연결 확인에 실패했을 때 발생하는 예외"""
    pass


# 파티션 관련 예외


class PartitionOperationError(Exception):
    """파티션 작업(읽기/쓰기) 실패 시 발생하는 예외
    
    Attributes:
        partition (str): 파티션 이름
        operation (str): 작업 유형 ('읽기', '쓰기', '추출' 등)
        message (str): 상세 에러 메시지
    """
    def __init__(self, partition: str, operation: str, message: str = ""):
        """PartitionOperationError 초기화"""
        self.partition = partition
        self.operation = operation
        self.message = message
        super().__init__(f"'{partition}' 파티션 {operation} 실패" + (f": {message}" if message else ""))


# 사용자 작업 관련 예외


class UserCancelledError(Exception):
    """사용자가 작업을 취소했을 때 발생하는 예외"""
    pass


# ADB/슬롯 관련 예외


class SlotInfoError(Exception):
    """슬롯 정보를 확인할 수 없을 때 발생하는 예외"""
    pass


# 분석 관련 예외


class RegionCodeCheckError(Exception):
    """지역 코드 확인에 실패했을 때 발생하는 예외"""
    pass


class ModelInfoCheckError(Exception):
    """모델 정보 확인에 실패했을 때 발생하는 예외"""
    pass


# 패치 관련 예외


class PatchVerificationError(Exception):
    """패치 파일 검증에 실패했을 때 발생하는 예외"""
    pass


class PatchCreationError(Exception):
    """패치 생성에 실패했을 때 발생하는 예외
    
    Attributes:
        partition (str): 패치 대상 파티션
        message (str): 상세 에러 메시지
    """
    def __init__(self, partition: str, message: str = ""):
        """PatchCreationError 초기화"""
        self.partition = partition
        self.message = message
        super().__init__(f"'{partition}' 패치 생성 실패" + (f": {message}" if message else ""))

