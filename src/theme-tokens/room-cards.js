/**
 * ============================================================
 * THEME TOKENS: ROOM CARDS
 * ============================================================
 *
 * PURPOSE
 * -------
 * Defines room-card specific surface, profile-chip, and grid
 * tokens used by the primary room control surface.
 *
 * ARCHITECTURAL ROLE
 * ------------------
 * Room cards are a distinct editor group because their tokens
 * control both the visual room surface and room-specific chips
 * without changing the flat backend token contract.
 *
 * ============================================================
 */

import { roomToken } from "./helpers.js";

export const ROOM_CARD_TOKENS = [
  roomToken.color("--evcc-profile-chip-bg", "Profile Chip BG"),
  roomToken.color("--evcc-profile-chip-border", "Profile Chip Border"),
  roomToken.color("--evcc-profile-chip-custom-bg", "Profile Chip Custom BG"),
  roomToken.color("--evcc-profile-chip-custom-border", "Profile Chip Custom Border"),
  roomToken.color("--evcc-profile-chip-custom-text", "Profile Chip Custom Text"),
  roomToken.color("--evcc-profile-chip-text", "Profile Chip Text"),
  roomToken.color("--evcc-room-chip-bg", "Room Chip BG"),
  roomToken.color("--evcc-room-chip-border", "Room Chip Border"),
  roomToken.color("--evcc-room-chip-text", "Room Chip Text"),
  roomToken.number("--evcc-room-fill-opacity", "Room Fill Opacity"),
  roomToken.size("--evcc-room-grid-columns", "Room Grid Columns"),
  roomToken.size("--evcc-room-grid-gap", "Room Grid Gap"),
  roomToken.size("--evcc-room-grid-min", "Room Grid Min"),
];
