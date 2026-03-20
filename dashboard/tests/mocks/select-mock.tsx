/**
 * Shared mock for @/components/ui/select (ShadCN Select).
 *
 * Radix UI Select uses pointer-capture APIs unavailable in jsdom.
 * This mock replaces it with a simple inline listbox that exercises
 * the same external contract (value, onValueChange, disabled, etc.).
 *
 * Usage in test files:
 *   vi.mock("@/components/ui/select", () => require("../tests/mocks/select-mock"));
 *   // or with import:
 *   import * as selectMock from "../tests/mocks/select-mock";
 *   vi.mock("@/components/ui/select", () => selectMock);
 */
import React from "react";

export function Select({
  value,
  onValueChange,
  children,
}: {
  value?: string;
  onValueChange?: (v: string) => void;
  children?: React.ReactNode;
}) {
  return (
    <div data-testid="select-root" data-value={value}>
      {typeof children === "object" && children !== null
        ? React.Children.map(children as React.ReactElement[], (child) =>
            React.isValidElement(child)
              ? React.cloneElement(child as React.ReactElement<Record<string, unknown>>, {
                  __value: value,
                  __onValueChange: onValueChange,
                })
              : child,
          )
        : children}
    </div>
  );
}

export function SelectTrigger({
  children,
  "aria-label": ariaLabel,
  __value: _value,
  __onValueChange: _onChange,
  ...rest
}: React.PropsWithChildren<{
  "aria-label"?: string;
  __value?: string;
  __onValueChange?: (v: string) => void;
  [key: string]: unknown;
}>) {
  return (
    <button role="combobox" aria-label={ariaLabel} aria-controls="select-listbox" aria-expanded={false} data-selected-value={_value} {...rest}>
      {children}
    </button>
  );
}

export function SelectValue({ placeholder }: { placeholder?: string }) {
  return <span>{placeholder}</span>;
}

export function SelectContent({
  children,
  __value,
  __onValueChange,
}: React.PropsWithChildren<{
  __value?: string;
  __onValueChange?: (v: string) => void;
}>) {
  return (
    <div role="listbox">
      {typeof children === "object" && children !== null
        ? React.Children.map(children as React.ReactElement[], (child) =>
            React.isValidElement(child)
              ? React.cloneElement(child as React.ReactElement<Record<string, unknown>>, {
                  __value,
                  __onValueChange,
                })
              : child,
          )
        : children}
    </div>
  );
}

export function SelectItem({
  value,
  disabled,
  className,
  children,
  __value: currentValue,
  __onValueChange: onValueChange,
}: React.PropsWithChildren<{
  value: string;
  disabled?: boolean;
  className?: string;
  __value?: string;
  __onValueChange?: (v: string) => void;
}>) {
  return (
    <div
      role="option"
      aria-disabled={disabled ? "true" : undefined}
      aria-selected={currentValue === value}
      data-state={currentValue === value ? "checked" : "unchecked"}
      className={className}
      onClick={() => !disabled && onValueChange?.(value)}
    >
      {children}
    </div>
  );
}
