import { homedir } from "os";
import { join } from "path";

let _resolved: string | undefined;
let _resolvedFromEnv: string | undefined;
let _resolvedLive: string | undefined;
let _resolvedLiveFromEnv: string | undefined;

export function getRuntimeHome(): string {
  const currentEnv = process.env.OPEN_CONTROL_HOME || process.env.NANOBOT_HOME;
  if (_resolved !== undefined && _resolvedFromEnv === currentEnv) {
    return _resolved;
  }

  if (process.env.OPEN_CONTROL_HOME) {
    _resolved = process.env.OPEN_CONTROL_HOME;
    _resolvedFromEnv = process.env.OPEN_CONTROL_HOME;
    console.info(`[runtime-home] Resolved to: ${_resolved} (source: OPEN_CONTROL_HOME)`);
    return _resolved;
  }

  if (process.env.NANOBOT_HOME) {
    _resolved = process.env.NANOBOT_HOME;
    _resolvedFromEnv = process.env.NANOBOT_HOME;
    console.info(`[runtime-home] Resolved to: ${_resolved} (source: NANOBOT_HOME)`);
    return _resolved;
  }

  _resolved = join(homedir(), ".nanobot");
  _resolvedFromEnv = undefined;
  console.info(`[runtime-home] Resolved to: ${_resolved} (source: default)`);
  return _resolved;
}

export function getRuntimePath(...parts: string[]): string {
  return join(getRuntimeHome(), ...parts);
}

export function getLiveHome(): string {
  const currentEnv = process.env.OPEN_CONTROL_LIVE_HOME;
  if (_resolvedLive !== undefined && _resolvedLiveFromEnv === currentEnv) {
    return _resolvedLive;
  }

  if (process.env.OPEN_CONTROL_LIVE_HOME) {
    _resolvedLive = process.env.OPEN_CONTROL_LIVE_HOME;
    _resolvedLiveFromEnv = process.env.OPEN_CONTROL_LIVE_HOME;
    console.info(
      `[runtime-home] Live resolved to: ${_resolvedLive} (source: OPEN_CONTROL_LIVE_HOME)`,
    );
    return _resolvedLive;
  }

  _resolvedLive = join(getRuntimeHome(), "live-sessions");
  _resolvedLiveFromEnv = undefined;
  console.info(`[runtime-home] Live resolved to: ${_resolvedLive} (source: default)`);
  return _resolvedLive;
}

export function getLivePath(...parts: string[]): string {
  return join(getLiveHome(), ...parts);
}
