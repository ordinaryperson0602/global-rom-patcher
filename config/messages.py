"""에러 및 정보 메시지 중앙 관리"""


class ErrorMessages:
    """에러 메시지"""
    
    # EDL 관련
    EDL_DISCONNECT = "EDL 모드 중 PC와 태블릿의 통신에 문제가 생겼습니다."
    EDL_DISCONNECT_DETAIL = (
        "EDL 모드 중 PC와 태블릿의 통신에 문제가 생겼습니다.\n\n"
        "PC와 태블릿의 연결을 해제하고,\n"
        "볼륨 다운 + 전원 버튼을 15초가량 눌러\n"
        "강제 재부팅한 후 프로그램을 다시 실행하십시오."
    )
    EDL_LOADER_NOT_SET = "로더 파일이 설정되지 않았습니다."
    EDL_LOADER_NOT_FOUND = "로더 파일을 찾을 수 없습니다."
    EDL_MODE_ENTRY_FAILED = "EDL 모드 진입 실패"
    EDL_CONNECTION_FAILED = "EDL 연결 확인 실패"
    
    # 모델 관련
    MODEL_UNSUPPORTED = "지원되지 않는 모델입니다.\n확인된 모델: {model}"
    MODEL_MISMATCH = "ADB로 확인된 모델({adb_model})과\nvbmeta의 Prop 모델({vbmeta_model})이 일치하지 않습니다."
    MODEL_LOADER_NOT_FOUND = "모델({model})은(는) 확인되었으나, 필요한 로더 파일이 없습니다:\n{loader_path}"
    
    # 지역 코드 관련
    REGION_MIXED_PRC_ROW = "vendor_boot 이미지에서 ROW/IROW와(과) PRC/IPRC이(가) 모두 발견되었습니다"
    REGION_MIXED_PRC_IPRC = "vendor_boot 이미지에서 지역코드가 PRC와 IPRC로 혼합되어 발견되었습니다."
    REGION_ROW_NOT_SUPPORTED = (
        "이 제품은 정발제품(ROW/IROW Hex)으로 확인됩니다.\n"
        "정발제품은 자동업데이트(OTA)를 이용해주세요."
    )
    REGION_NOT_FOUND = "vendor_boot 이미지에서 지역코드(ROW/IROW 또는 PRC/IPRC)를 찾을 수 없습니다."
    REGION_PATTERN_NOT_FOUND = (
        "vendor_boot에서 ROW/IROW 패턴을 찾을 수 없습니다.\n\n"
        "STEP 2 검증을 통과했는데 패턴이 없다면\n"
        "파일이 손상되었거나 지원하지 않는 형식입니다."
    )
    
    # 파티션/파일 관련
    PARTITION_EXTRACTION_FAILED = "'{partition}' 파티션 추출 실패"
    PARTITION_READ_FAILED = "'{partition}' 파티션 읽기 실패"
    PARTITION_WRITE_FAILED = "'{partition}' 파티션 쓰기 실패"
    PARTITION_OPERATION_FAILED = "'{partition}' 처리 중 오류"
    FILE_ANALYSIS_FAILED = "{file} 파일 분석 중 오류: {error}"
    FILE_NOT_FOUND = "필수 파일이 없습니다.\n'Tools' 폴더를 확인하세요."
    PATCH_FILE_VERIFICATION_FAILED = "패치 파일 검증 실패"
    PATCH_CREATION_FAILED = "'{partition}' 패치 생성 실패"
    
    # vbmeta 관련
    VBMETA_FINGERPRINT_NOT_FOUND = "vbmeta Prop에서 'fingerprint' 속성을 찾을 수 없습니다."
    VBMETA_FORMAT_INVALID = "vbmeta 'fingerprint' Prop 형식이 예상과 다릅니다.\n(모델/롬버전 추출 실패)"
    VBMETA_COUNTRY_CODE_MIXED = "국가코드가 PRC / ROW 모두 발견되었습니다.\n패드 모델 또는 상태를 확인하십시오."
    VBMETA_COUNTRY_CODE_NOT_FOUND = "국가코드가 발견되지 않았습니다.\n패드 모델 또는 상태를 확인하십시오."
    
    # 롤백 인덱스 관련
    ROLLBACK_INDEX_INVALID = "롤백 인덱스 값이 유효하지 않습니다:\n{indices}"
    
    # ADB 관련
    ADB_MODEL_CHECK_FAILED = "ADB를 통해 모델 번호를 확인할 수 없습니다."
    ADB_SLOT_CHECK_FAILED = "ADB를 통해 활성 슬롯을 확인할 수 없습니다."
    ADB_SLOT_INVALID = "예상치 못한 슬롯 값입니다: '{slot}'"
    SLOT_INFO_UNAVAILABLE = "슬롯 정보를 확인할 수 없습니다."
    
    # 사용자 작업 관련
    USER_CANCELLED = "사용자가 작업을 취소했습니다."
    
    # 분석 관련
    REGION_CODE_CHECK_FAILED = "지역 코드 확인 실패"
    MODEL_INFO_CHECK_FAILED = "모델 정보 확인 실패"
    
    # 관리자 권한
    ADMIN_REQUIRED = "프로그램 실행을 위해 관리자 권한이 필요합니다."
    ADMIN_ELEVATION_FAILED = "관리자 권한 상승에 실패했습니다."


class InfoMessages:
    """정보 메시지"""
    
    # 작업 확인
    DEVICE_MODEL_CONFIRM = "연결된 기기가 {model_name} 모델이 맞습니까?"
    DEVICE_MODEL_CHECK_AGAIN = "기기와 모델 번호를 다시 한번 확인하십시오."
    
    # 경고 메시지
    WARNING_DO_NOT_DISCONNECT = "⚠️  통신 중 - USB 케이블과 태블릿을 절대 건드리지 마십시오! ⚠️"
    WARNING_EDL_COMMUNICATION = "⚠️  EDL 통신 중 - USB 연결을 유지하십시오! ⚠️"
    
    # 작업 안내
    EDL_WAIT_MESSAGE = "기기가 EDL 모드로 전환될 때까지 {seconds}초간 대기합니다..."
    
    # 성공 메시지
    SUCCESS_ALL_COMPLETE = "모든 작업이 성공적으로 완료되었습니다!"


class TitleMessages:
    """팝업 타이틀"""
    ERROR = "오류 - NG"
    WARNING = "경고"
    INFO = "정보"
    CANCEL = "작업 중단 (NG)"
    CONFIRM = "확인"


# 경고 배너
WARNING_BANNER = f"""{'=' * 80}
                  ⚠️  경   고  ⚠️                  
{'=' * 80}

  지금부터 태블릿과 PC가 통신을 시작합니다!
  작업이 완료될 때까지 다음 사항을 절대 하지 마십시오:

  ❌ USB 케이블을 뽑지 마십시오
  ❌ 태블릿 전원 버튼을 누르지 마십시오
  ❌ PC를 종료하거나 재시작하지 마십시오
  ❌ 프로그램을 강제 종료하지 마십시오
{'=' * 80}
"""

