import type { ReactElement } from "react";
import { cn } from "../lib/utils";

type AppIconName = "calendar" | "tag" | "user";

interface Props {
  name: AppIconName;
  className?: string;
}

const paths: Record<AppIconName, ReactElement> = {
  calendar: (
    <>
      <rect
        x="3"
        y="5"
        width="18"
        height="16"
        rx="4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
      />
      <path d="M8 3.5v4M16 3.5v4M3 9.5h18" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </>
  ),
  tag: (
    <path
      d="M20 13.5 12.5 21a2 2 0 0 1-2.83 0L4 15.33V4h11.33L20 8.67a2 2 0 0 1 0 2.83Z"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.75"
    />
  ),
  user: (
    <>
      <path
        d="M12 12a4 4 0 1 0-4-4 4 4 0 0 0 4 4Z"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.75"
      />
      <path
        d="M5 20a7 7 0 0 1 14 0"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.75"
      />
    </>
  ),
};

export function AppIcon({ name, className }: Props) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={cn("shrink-0", className)}
      data-testid={`app-icon-${name}`}
    >
      {paths[name]}
    </svg>
  );
}
