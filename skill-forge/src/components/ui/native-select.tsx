import * as React from "react"

import { cn } from "@/lib/utils"

const ARROW_BG = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(24,24,27,0.55)' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`

function NativeSelect({ className, style, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      data-slot="native-select"
      className={cn(
        "w-full cursor-pointer appearance-none rounded-md border border-black/10 bg-surface p-2.5 px-3.5 pr-9 text-sm text-foreground transition-[color,border-color,box-shadow,background-color] duration-200 outline-none",
        "hover:border-black/20",
        "focus-visible:border-accent/60 focus-visible:bg-surface-up focus-visible:ring-[3px] focus-visible:ring-accent/15",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      style={{
        backgroundImage: ARROW_BG,
        backgroundRepeat: "no-repeat",
        backgroundPosition: "right 12px center",
        ...style,
      }}
      {...props}
    />
  )
}

export { NativeSelect }
