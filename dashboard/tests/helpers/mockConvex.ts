import { vi } from "vitest";
import type { Mock } from "vitest";
import type { FunctionReference } from "convex/server";
import type { ReactMutation } from "convex/react";
import type { Id, TableNames } from "@/convex/_generated/dataModel";

/** Cast a string to a branded Convex Id for test mocks */
export function testId<T extends TableNames>(value: string): Id<T> {
  return value as unknown as Id<T>;
}

/**
 * Create a mock that satisfies ReactMutation (callable + withOptimisticUpdate).
 * The return type is a Mock so you can access `.mock.calls` etc., and it is
 * also assignable to ReactMutation via the cast.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ReactMutationMock = Mock & ReactMutation<FunctionReference<"mutation">>;

export function mockReactMutation(impl: (...args: unknown[]) => unknown): ReactMutationMock {
  const fn = vi.fn(impl);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (fn as any).withOptimisticUpdate = vi.fn().mockReturnValue(fn);
  return fn as unknown as ReactMutationMock;
}
