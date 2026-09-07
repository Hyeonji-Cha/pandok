# Athena와 Gold의 영문 스키마를 바꾸지 않고 대시보드 표시만 한국어로 변환한다.
# 알 수 없는 새 값은 숨기거나 오역하지 않고 원문 그대로 표시한다.

from __future__ import annotations

from collections.abc import Mapping, Sequence


COLUMN_LABELS = {
    "game_version": "게임 버전",
    "checkpoint_number": "체크포인트 번호",
    "elapsed_minutes": "경과 시간(분)",
    "started_run_count": "시작 Run 수",
    "reached_run_count": "도달 Run 수",
    "reach_percentage": "도달률(%)",
    "step_dropoff_percentage": "구간 이탈률(%)",
    "end_reason": "종료 사유",
    "death_cause": "사망 원인",
    "run_count": "Run 수",
    "average_run_seconds": "평균 생존시간(초)",
    "choice_source": "선택 경로",
    "item_id": "아이템 ID",
    "weapon_id": "무기 ID",
    "display_name": "표시 이름",
    "item_category": "아이템 분류",
    "intended_effect": "설계 효과",
    "primary_metric": "주요 분석 지표",
    "selection_count": "선택 횟수",
    "selected_run_count": "선택 Run 수",
    "outcome_observed_run_count": "결과 관측 Run 수",
    "average_seconds_after_selection": "선택 후 평균 관측시간(초)",
    "death_within_60_seconds_percentage": "선택 후 60초 내 사망률(%)",
    "average_final_level": "평균 최종 레벨",
    "average_total_kills": "평균 총 킬 수",
    "analysis_status": "분석 상태",
    "starting_run_count": "시작 무기 Run 수",
    "exposure_count": "노출 횟수",
    "exposed_run_count": "노출 Run 수",
    "first_selected_run_count": "최초 선택 Run 수",
    "selection_percentage": "노출 대비 선택률(%)",
    "kills_per_minute": "분당 킬 수",
    "average_total_xp": "평균 총 경험치",
    "average_total_gold": "평균 총 골드",
    "death_percentage": "사망률(%)",
    "offered_run_count": "제시 Run 수",
    "not_selected_run_count": "비선택 Run 수",
    "selected_outcome_run_count": "선택 결과 관측 Run 수",
    "not_selected_outcome_run_count": "비선택 결과 관측 Run 수",
    "selected_average_kills": "선택 시 평균 킬 수",
    "not_selected_average_kills": "비선택 시 평균 킬 수",
    "average_kill_difference": "평균 킬 차이",
    "selected_average_run_seconds": "선택 시 평균 생존시간(초)",
    "not_selected_average_run_seconds": "비선택 시 평균 생존시간(초)",
    "average_run_seconds_difference": "평균 생존시간 차이(초)",
    "run_status": "Run 상태",
    "input_event_count": "입력 이벤트 수",
    "unique_event_count": "고유 이벤트 수",
    "exact_retry_count": "동일 재전송 수",
    "conflicting_duplicate_count": "충돌 중복 수",
}


VALUE_LABELS = {
    "player_death": "플레이어 사망",
    "player_quit": "게임 종료",
    "player_restart": "Run 재시작",
    "incomplete": "미완료",
    "enemy_damage": "적 공격",
    "fall": "추락",
    "environmental_hazard": "환경 피해",
    "unknown": "분류 불가",
    "not_collected_legacy": "미수집(이전 계약)",
    "not_applicable": "해당 없음",
    "valid": "정상",
    "INSUFFICIENT_SAMPLE": "표본 부족",
    "DESCRIPTIVE_ONLY": "참고용 관찰 결과",
    "DERIVABLE": "분석 가능",
    "LIMITED_BY_CHECKPOINT_CADENCE": "체크포인트 주기 제약",
    "level_up_weapon": "레벨업 무기 선택",
    "level_up_upgrade": "레벨업 무기 강화",
    "statue": "석상 보상",
    "weapon": "무기",
    "offense_projectile_count": "공격·발사체 수",
    "offense_attack_speed": "공격·공격 속도",
    "offense_damage": "공격·피해량",
    "offense_chain": "공격·연쇄",
    "offense_execute": "공격·처형",
    "rarity_luck": "희귀도·행운",
    "economy": "경제",
    "progression": "성장",
    "risk_reward": "위험·보상",
    "Bone": "뼈다귀 (Bone)",
    "Tennis Ball": "테니스공 (Tennis Ball)",
    "Steak": "스테이크 (Steak)",
    "Fireball": "파이어볼 (Fireball)",
    "Horseshoe": "말발굽 (Horseshoe)",
    "Gold Ingot": "금괴 (Gold Ingot)",
    "Hourglass": "모래시계 (Hourglass)",
    "Sword": "검 (Sword)",
    "Bull Skull": "황소 해골 (Bull Skull)",
    "Sticky Bone": "끈적이는 뼈 (Sticky Bone)",
    "Greyhound Tooth": "그레이하운드 이빨 (Greyhound Tooth)",
    "Blood Scent": "피 냄새 (Blood Scent)",
    "Increase projectiles per attack": "공격당 발사체 수 증가",
    "Increase automatic attack frequency": "자동 공격 빈도 증가",
    "Increase projectile damage": "발사체 피해량 증가",
    "Increase the chance of higher-rarity options": "높은 희귀도 옵션 등장 확률 증가",
    "Increase gold gained from coins": "코인 획득 골드 증가",
    "Increase experience gained from XP orbs": "경험치 오브 획득 경험치 증가",
    "Increase final damage for all weapons": "모든 무기의 최종 피해량 증가",
    "Advance difficulty time": "난이도 진행 시간 앞당김",
    "Chain a projectile to additional enemies after the first hit": "첫 적중 후 추가 적에게 발사체 연쇄",
    "Chance to execute a non-boss enemy": "보스가 아닌 적을 즉시 처치할 확률",
    "Execute enemies below the configured health threshold": "설정 체력 이하의 적 처형",
}


def localize_rows(
    rows: Sequence[Mapping[str, str | None]],
) -> list[dict[str, str | None]]:
    """원본 행을 변경하지 않고 표시명과 제한된 상태값만 한국어로 바꾼다."""

    return [
        {
            COLUMN_LABELS.get(column, column): VALUE_LABELS.get(value, value)
            for column, value in row.items()
        }
        for row in rows
    ]
