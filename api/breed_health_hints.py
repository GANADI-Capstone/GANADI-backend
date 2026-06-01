"""
품종·연령별 안구 질환 참고 문구 (PDF·리포트용, 일반 교육 정보).
수의사 진단을 대체하지 않으며, 보호자·수의사 상담 참고용이다.
"""

from __future__ import annotations

from typing import List, Optional

# 품종(부분 일치) → 흔한 안구 관련 질환
_DOG_BREED_EYE: dict[str, list[str]] = {
    "말티즈": ["백내장", "유루증", "결막염", "안검내반증"],
    "푸들": ["백내장", "유루증", "안검염"],
    "포메라니안": ["유루증", "안검내반증", "결막염"],
    "시츄": ["안검내반증", "유루증", "각막 질환"],
    "치와와": ["유루증", "결막염", "백내장"],
    "비글": ["핵경화", "결막염"],
    "골든": ["핵경화", "유루증", "백내장"],
    "래브라도": ["유루증", "핵경화", "결막염"],
    "코카": ["유루증", "백내장", "안검염"],
    "프렌치": ["유루증", "각막 궤양", "결막염"],
    "불독": ["각막 질환", "안검염", "유루증"],
    "닥스": ["유루증", "백내장"],
    "시바": ["핵경화", "결막염"],
    "허스키": ["유루증", "핵경화"],
}

_CAT_BREED_EYE: dict[str, list[str]] = {
    "페르시안": ["각막 궤양", "결막염", "유루증(눈물자국)"],
    "브리티시": ["결막염", "각막 궤양"],
    "먼치킨": ["각막 궤양", "결막염"],
    "스코티시": ["결막염", "각막 질환"],
    "러시안": ["결막염", "각막 궤양"],
    "메인쿤": ["결막염", "유루증"],
    "코리안": ["결막염", "각막 궤양"],
    "코숏": ["결막염", "각막 궤양"],
    "봄베이": ["결막염"],
    "랙돌": ["결막염", "유루증"],
}


def _match_breed(breed: Optional[str], table: dict[str, list[str]]) -> list[str]:
    if not breed or not str(breed).strip():
        return []
    b = str(breed).strip().lower()
    for key, diseases in table.items():
        if key.lower() in b or b in key.lower():
            return diseases
    return []


def _age_notes(age: Optional[int]) -> List[str]:
    if age is None:
        return ["연령 정보가 없어 연령대별 참고만 일반적으로 안내합니다."]
    notes: List[str] = []
    if age < 1:
        notes.append("1세 미만은 선천성·감염성 결막염, 눈물 배출 이상을 주의 깊게 관찰하는 것이 좋습니다.")
    elif age < 7:
        notes.append("성견·성묘기에는 알레르기성 결막염, 외상성 각막 질환이 상대적으로 흔합니다.")
    else:
        notes.append(
            "7세 이상(노령)은 백내장, 핵경화, 만성 유루증, 안검 종양 등 "
            "노령성 안질환 발생 빈도가 높아지므로 정기 안과 스크리닝이 권장됩니다."
        )
    if age >= 10:
        notes.append("10세 이상은 백내장·안압 이상 등 진행성 질환을 조기에 발견하기 위해 검진 간격을 짧게 잡는 것이 좋습니다.")
    return notes


def build_breed_age_health_notes(
    animal_type: str,
    breed: Optional[str] = None,
    age: Optional[int] = None,
) -> str:
    """PDF·리포트에 넣을 품종·연령 참고 문단 (plain text)."""
    animal = (animal_type or "").lower()
    species_label = "강아지" if animal == "dog" else "고양이" if animal == "cat" else "반려동물"
    lines: List[str] = []

    breed_diseases = _match_breed(breed, _DOG_BREED_EYE if animal == "dog" else _CAT_BREED_EYE)
    if breed and breed_diseases:
        lines.append(
            f"· {species_label} 품종 「{breed.strip()}」에서는 "
            f"{', '.join(breed_diseases)} 등 안구 질환이 상대적으로 자주 보고됩니다."
        )
    elif breed:
        lines.append(
            f"· {species_label} 품종 「{breed.strip()}」에 대한 등록된 참고 데이터는 제한적입니다. "
            "정기적인 눈 상태 관찰과 수의사 검진을 권장합니다."
        )

    for note in _age_notes(age):
        lines.append(f"· {note}")

    if age is not None:
        lines.append(f"· 현재 등록 연령: {age}세 (참고용, 실제 검진 시점과 다를 수 있음).")

    if not lines:
        return (
            "품종·연령 정보가 충분하지 않아 일반적인 안구 건강 관리만 안내합니다. "
            "눈곱 증가, 충혈, 눈물, 눈을 감는 행동 등이 보이면 수의사 상담을 받으세요."
        )

    return "\n".join(lines)
