# Feature Specification: Run Telemetry Contract

**Feature Branch**: `main`

**Created**: 2026-08-29

**Status**: Draft

**Input**: User description: "Define the first developer-independent telemetry contract for
King Charles, covering consent, Run start, upgrade choices, 60-second checkpoints, and Run end."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validate the P0 Run Flow (Priority: P1)

As the data engineer, I can validate a representative sequence from consented play through Run end
before a live game build is available, so downstream work starts against an agreed data boundary.

**Why this priority**: Every ingestion, quality, and analytics component depends on consistent event
meaning and correlation identifiers.

**Independent Test**: Validate a fixture sequence containing session start, Run start, upgrade options,
upgrade selection, checkpoint, and Run end; the entire sequence is accepted and its relationships are
preserved.

**Acceptance Scenarios**:

1. **Given** a consented player and a new session, **When** a complete P0 Run sequence is validated,
   **Then** every event is accepted and shares the correct session and Run identifiers.
2. **Given** an upgrade choice is shown, **When** its selection is validated, **Then** both records use
   the same choice identifier and the selected item matches one of the shown options.
3. **Given** a checkpoint and Run-end summary, **When** cumulative values are compared, **Then** elapsed
   time and counters never decrease within the Run.

---

### User Story 2 - Reject Unsafe or Malformed Events (Priority: P2)

As the data engineer, I can distinguish malformed or privacy-violating telemetry from trusted events,
so invalid data never silently enters gameplay metrics.

**Why this priority**: Explicit rejection rules make privacy and data quality observable at the first
system boundary.

**Independent Test**: Submit fixtures with missing identifiers, unsupported event versions, direct
identifiers, invalid timestamps, and invalid numeric ranges; each is rejected with a specific reason.

**Acceptance Scenarios**:

1. **Given** an event containing a prohibited direct identifier, **When** it is validated, **Then** it is
   rejected with a privacy-related reason.
2. **Given** an event missing a required common field, **When** it is validated, **Then** it is rejected
   with the missing field identified.
3. **Given** a valid event is retried with the same event identifier, **When** both copies are processed,
   **Then** they can be recognized as the same logical event.

---

### User Story 3 - Evolve the Contract Safely (Priority: P3)

As the game developer, I can see which fields are required, optional, or awaiting confirmation and can
produce compatible events without relying on translated display text.

**Why this priority**: The contract must remain usable while game-specific details are confirmed and
future game versions evolve.

**Independent Test**: Review the contract and fixtures without project background; a developer can
identify all required P0 fields, stable identifiers, optional fields, and pending game questions.

**Acceptance Scenarios**:

1. **Given** a display name changes or is localized, **When** an event is produced, **Then** its stable
   item identifier remains unchanged.
2. **Given** a not-yet-confirmed game field is unavailable, **When** a P0 event is validated, **Then** the
   event remains valid if that field is documented as optional.
3. **Given** an incompatible contract change, **When** it is proposed, **Then** it requires a new contract
   version and new compatibility fixtures.

### Edge Cases

- A Run ends before its first 60-second checkpoint.
- The application closes or crashes before a normal Run-end event can be sent.
- A selection event arrives before its corresponding options event because of network delay.
- Two retries contain the same event identifier but different payloads.
- A checkpoint is delayed and arrives after the Run-end event.
- A player pauses for longer than 60 seconds; paused time must not inflate active Run time.
- A player declines or revokes consent while events remain in a local queue.
- A cumulative value is unavailable in the current game build.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every event MUST include a unique event identifier, event name, UTC event time,
  anonymous installation identifier, session identifier, game version, and contract version.
- **FR-002**: Events occurring during a Run MUST include a Run identifier; session-only events MAY
  omit it.
- **FR-003**: The P0 contract MUST define `session_started`, `run_started`,
  `upgrade_options_shown`, `upgrade_selected`, `run_checkpoint`, and `run_ended`.
- **FR-004**: `upgrade_options_shown` MUST identify one choice occurrence and describe both offered
  slots using stable item identifiers and rarity values.
- **FR-005**: `upgrade_selected` MUST reuse the shown choice identifier and identify the selected slot,
  item, rarity, and its before-and-after upgrade count when available.
- **FR-006**: `run_checkpoint` MUST represent a small cumulative state summary at each 60-second
  interval of active gameplay rather than a screenshot or save file.
- **FR-007**: A checkpoint MUST include active Run time, player level, health percentage, total kills,
  total collected XP, earned gold, cleared miniboss-wave count, and active upgrade counts when those
  values are available from the game.
- **FR-008**: `run_ended` MUST include an end reason, active Run duration, final level, cumulative
  gameplay totals, miniboss progress, and final upgrade counts when those values are available.
- **FR-009**: The contract MUST permit a Run to end before any checkpoint and MUST NOT assume that
  every session has a normal session-end record.
- **FR-010**: Validation MUST reject direct identifiers including Steam ID, Steam nickname, email,
  device identifier, authentication token, chat content, precise location, or username.
- **FR-011**: Validation MUST reject missing required fields, malformed UTC timestamps, unsupported
  event names, unsupported contract versions, negative counters, and health percentages outside
  zero through one hundred.
- **FR-012**: Repeated delivery MUST preserve the original event identifier so duplicates can be
  recognized without treating a retry as a new event.
- **FR-013**: Stable internal identifiers MUST be used for items and other game entities; localized
  display names MUST NOT serve as identifiers.
- **FR-014**: High-frequency actions such as frames, attacks, hits, individual kills, damage ticks,
  XP increments, and individual blue-orb pickups MUST NOT be represented as P0 network events.
- **FR-015**: The feature MUST provide accepted and rejected representative examples for every P0
  event category and validation rule.
- **FR-016**: Required, optional, and developer-pending fields MUST be distinguishable in the contract
  documentation.
- **FR-017**: A player who has not consented or has revoked consent MUST produce no new telemetry, and
  revocation MUST discard unsent queued telemetry.

### Key Entities *(include if feature involves data)*

- **Telemetry Event**: One immutable gameplay fact with a stable identity, occurrence time, event
  category, contract version, and correlation identifiers.
- **Session**: One game application session associated with an anonymous installation.
- **Run**: One gameplay attempt beginning when active play starts and normally ending on death or
  another developer-confirmed end condition.
- **Upgrade Choice**: One display of two upgrade options and the player's related selection, joined by
  a stable choice identifier.
- **Run Checkpoint**: A periodic cumulative summary of a Run's active time, player state, progress,
  resources, and upgrades.
- **Upgrade State**: A stable item identifier and its current selection or upgrade count within a Run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: One complete representative P0 Run sequence passes all contract checks with zero manual
  corrections.
- **SC-002**: Every required field and every prohibited direct identifier has at least one failing
  example that is rejected with a specific reason.
- **SC-003**: One hundred percent of duplicate examples retain a matching event identifier and are
  distinguishable from distinct logical events.
- **SC-004**: A developer unfamiliar with the data platform can identify the six P0 event categories,
  required common fields, optional fields, and pending questions in under 15 minutes.
- **SC-005**: All dashboard-bound fields in this feature can be traced to a named event and field
  definition without consulting game source code.

## Confirmed Scope

- The analysis unit is a Run rather than a stage.
- The initial flow covers consent, session start, Run start, two-option upgrade choices, 60-second
  checkpoints, and Run end.
- Hearts restore current health; magnet and miniboss events are post-P0 additions.
- Individual blue-orb pickups and other high-frequency combat actions are aggregated, not sent one by
  one.
- `event_id` is preserved across retries and used for deduplication.
- Direct player and device identifiers are excluded.

## Developer-Pending Decisions

- The exact code points that define active Run start and every distinguishable Run-end reason.
- The existing stable item identifiers and complete rarity enumeration.
- Availability and precise meaning of level, health, kills, XP, gold, active upgrades, and upgrade
  counts in game code.
- Whether miniboss timing is exactly every three minutes and whether stable miniboss identifiers exist.
- The game engine and language, configuration mechanism for test and production telemetry endpoints,
  and timing of the first integration build.

These decisions MAY refine optional fields and later features. They MUST NOT block the P0 contract
fixtures or cause unconfirmed values to be fabricated.

## Assumptions

- The first implementation slice uses synthetic representative events and does not require a live
  game build.
- Run elapsed time excludes paused time.
- A normal death is represented as `player_death`; additional end reasons remain extensible until the
  developer confirms them.
- Unavailable cumulative gameplay fields are optional during initial integration but their absence
  must be observable.
- Heart, magnet, and miniboss lifecycle events are outside this P0 feature and will be specified after
  the base flow is stable.
