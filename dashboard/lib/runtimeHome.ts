import { homedir } from "os";
import { join } from "path";

export function getRuntimeHome(): string {
  return process.env.OPEN_CONTROL_HOME || process.env.NANOBOT_HOME || join(homedir(), ".nanobot");
}

export function getRuntimePath(...parts: string[]): string {
  return join(getRuntimeHome(), ...parts);
}
