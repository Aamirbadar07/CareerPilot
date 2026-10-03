"use client";

import { Moon, Sun } from "lucide-react";
import { ThemeProvider as NextThemes, useTheme } from "next-themes";
import { MotionConfig } from "framer-motion";
import { Toaster } from "sonner";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <NextThemes attribute="class" defaultTheme="dark" enableSystem={false} disableTransitionOnChange>
      {/* reducedMotion="user": framer-motion drops transform and layout animation for people
          who ask for reduced motion, leaving instant state changes. */}
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
      <ThemedToaster />
    </NextThemes>
  );
}

function ThemedToaster() {
  const { resolvedTheme } = useTheme();
  return <Toaster theme={resolvedTheme === "light" ? "light" : "dark"} position="bottom-right" richColors closeButton />;
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const dark = !mounted || resolvedTheme !== "light";
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
    </Button>
  );
}
