-- 개발자가 정의한 아이템 의도와 실제 telemetry item_id를 연결하는 기준 테이블이다.
-- 설정값만으로 결과를 단정하지 않고, 아이템 목적에 맞는 Gold 지표를 선택하기 위해 필요하다.

USE ROLE PANDOK_ENGINEER;
USE WAREHOUSE PANDOK_WH;
USE DATABASE PANDOK;
USE SCHEMA GOLD;

-- game_version을 키에 포함해 향후 밸런스 변경이 과거 설정을 덮어쓰지 않게 한다.
-- 현재 이벤트로 선택을 확인할 수 없는 필드 픽업은 안정적인 ID가 확정될 때까지 제외한다.
CREATE OR REPLACE TABLE ITEM_CATALOG AS
SELECT
  column1::STRING AS game_version,
  column2::STRING AS choice_source,
  column3::STRING AS item_id,
  column4::STRING AS display_name,
  column5::STRING AS item_category,
  column6::STRING AS intended_effect,
  column7::STRING AS primary_metric,
  column8::BOOLEAN AS rarity_scaled,
  column9::STRING AS metric_readiness
FROM VALUES
  ('0.1.0', 'level_up_weapon', 'bone', 'Bone', 'weapon',
   'Fast homing projectiles', 'kills_per_minute_after_selection', FALSE, 'DERIVABLE'),
  ('0.1.0', 'level_up_weapon', 'tennis_ball', 'Tennis Ball', 'weapon',
   'Fast ricocheting projectiles', 'kills_per_minute_after_selection', FALSE, 'DERIVABLE'),
  ('0.1.0', 'level_up_weapon', 'steak', 'Steak', 'weapon',
   'Tracking automatic projectiles', 'kills_per_minute_after_selection', FALSE, 'DERIVABLE'),
  ('0.1.0', 'level_up_weapon', 'fireball', 'Fireball', 'weapon',
   'Slow long-lived homing projectiles', 'kills_per_minute_after_selection', FALSE, 'DERIVABLE'),

  ('0.1.0', 'level_up_upgrade', 'bone_extra_projectiles', 'Bone Extra Projectiles',
   'offense_projectile_count', 'Increase projectiles per attack',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),
  ('0.1.0', 'level_up_upgrade', 'bone_attack_speed_multiplier', 'Bone Attack Speed',
   'offense_attack_speed', 'Increase automatic attack frequency',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),
  ('0.1.0', 'level_up_upgrade', 'bone_damage_bonus', 'Bone Damage',
   'offense_damage', 'Increase projectile damage',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),
  ('0.1.0', 'level_up_upgrade', 'tennis_ball_extra_projectiles', 'Tennis Ball Extra Projectiles',
   'offense_projectile_count', 'Increase projectiles per attack',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),
  ('0.1.0', 'level_up_upgrade', 'tennis_ball_attack_speed_multiplier', 'Tennis Ball Attack Speed',
   'offense_attack_speed', 'Increase automatic attack frequency',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),
  ('0.1.0', 'level_up_upgrade', 'tennis_ball_damage_bonus', 'Tennis Ball Damage',
   'offense_damage', 'Increase projectile damage',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),
  ('0.1.0', 'level_up_upgrade', 'steak_extra_projectiles', 'Steak Extra Projectiles',
   'offense_projectile_count', 'Increase projectiles per attack',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),
  ('0.1.0', 'level_up_upgrade', 'steak_attack_speed_multiplier', 'Steak Attack Speed',
   'offense_attack_speed', 'Increase automatic attack frequency',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),
  ('0.1.0', 'level_up_upgrade', 'steak_damage_bonus', 'Steak Damage',
   'offense_damage', 'Increase projectile damage',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),
  ('0.1.0', 'level_up_upgrade', 'fireball_extra_projectiles', 'Fireball Extra Projectiles',
   'offense_projectile_count', 'Increase projectiles per attack',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),
  ('0.1.0', 'level_up_upgrade', 'fireball_attack_speed_multiplier', 'Fireball Attack Speed',
   'offense_attack_speed', 'Increase automatic attack frequency',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),
  ('0.1.0', 'level_up_upgrade', 'fireball_damage_bonus', 'Fireball Damage',
   'offense_damage', 'Increase projectile damage',
   'kills_per_minute_after_selection', TRUE, 'DERIVABLE'),

  ('0.1.0', 'statue', 'horseshoe', 'Horseshoe', 'rarity_luck',
   'Increase the chance of higher-rarity options', 'subsequent_high_rarity_option_rate',
   TRUE, 'DERIVABLE'),
  ('0.1.0', 'statue', 'gold_ingot', 'Gold Ingot', 'economy',
   'Increase gold gained from coins', 'gold_gain_after_selection',
   TRUE, 'LIMITED_BY_CHECKPOINT_CADENCE'),
  ('0.1.0', 'statue', 'hourglass', 'Hourglass', 'progression',
   'Increase experience gained from XP orbs', 'xp_gain_after_selection',
   TRUE, 'LIMITED_BY_CHECKPOINT_CADENCE'),
  ('0.1.0', 'statue', 'sword', 'Sword', 'offense_damage',
   'Increase final damage for all weapons', 'kills_per_minute_after_selection',
   TRUE, 'DERIVABLE'),
  ('0.1.0', 'statue', 'bull_skull', 'Bull Skull', 'risk_reward',
   'Advance difficulty time', 'progression_and_death_rate_after_selection',
   TRUE, 'DERIVABLE'),
  ('0.1.0', 'statue', 'sticky_bone', 'Sticky Bone', 'offense_chain',
   'Chain a projectile to additional enemies after the first hit',
   'kills_per_minute_after_selection', FALSE, 'DERIVABLE'),
  ('0.1.0', 'statue', 'greyhound_tooth', 'Greyhound Tooth', 'offense_execute',
   'Chance to execute a non-boss enemy', 'kills_per_minute_after_selection',
   FALSE, 'DERIVABLE'),
  ('0.1.0', 'statue', 'blood_scent', 'Blood Scent', 'offense_execute',
   'Execute enemies below the configured health threshold',
   'kills_per_minute_after_selection', FALSE, 'DERIVABLE');

