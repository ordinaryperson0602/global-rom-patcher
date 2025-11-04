"""지역 코드 검사 유틸리티"""
# 표준 라이브러리
from typing import Optional, Tuple

# 로컬 모듈
from config.constants import HEX_PRC, HEX_IPRC, HEX_ROW, HEX_IROW


def check_region_patterns(data: bytes) -> Tuple[bool, bool, bool, bool]:
    """
    Hex 패턴 확인
    
    Args:
        data: 검사할 바이너리 데이터
    
    Returns:
        (prc_found, iprc_found, row_found, irow_found)
    """
    return (
        data.count(HEX_PRC) > 0,
        data.count(HEX_IPRC) > 0,
        data.count(HEX_ROW) > 0,
        data.count(HEX_IROW) > 0
    )


def validate_region_code(data: bytes) -> Optional[str]:
    """
    지역 코드 검증 및 반환
    
    Args:
        data: 검사할 바이너리 데이터
    
    Returns:
        "PRC", "IPRC", "ROW", "IROW" 중 하나, 또는 None (오류 시)
        
    Raises:
        ValueError: 지역 코드가 혼합되어 있거나 유효하지 않을 때
    """
    prc, iprc, row, irow = check_region_patterns(data)
    
    is_prc_type = prc or iprc
    is_row_type = row or irow
    
    # 검증: PRC와 ROW가 동시에 존재
    if is_prc_type and is_row_type:
        raise ValueError("지역 코드가 ROW/IROW와(과) PRC/IPRC 모두 발견되었습니다.")
    
    # 검증: PRC와 IPRC가 동시에 존재
    if prc and iprc:
        raise ValueError("지역 코드가 PRC와 IPRC로 혼합되어 발견되었습니다.")
    
    # 검증: ROW와 IROW가 동시에 존재
    if row and irow:
        raise ValueError("지역 코드가 ROW와 IROW로 혼합되어 발견되었습니다.")
    
    # 아무 패턴도 없음
    if not is_prc_type and not is_row_type:
        raise ValueError("지역 코드(ROW/IROW 또는 PRC/IPRC)를 찾을 수 없습니다.")
    
    # 정상: PRC, IPRC, ROW, IROW 모두 허용
    if iprc:
        return "IPRC"
    if prc:
        return "PRC"
    if irow:
        return "IROW"
    if row:
        return "ROW"
    
    return None


def check_region_in_image(data: bytes) -> Tuple[bool, bool]:
    """
    이미지에서 PRC와 ROW 존재 여부 확인 (간단 버전)
    
    Args:
        data: 검사할 바이너리 데이터
    
    Returns:
        (prc_found, row_found) - PRC/IPRC 중 하나라도 있으면 True, ROW/IROW 중 하나라도 있으면 True
    """
    prc, iprc, row, irow = check_region_patterns(data)
    return (prc or iprc, row or irow)

