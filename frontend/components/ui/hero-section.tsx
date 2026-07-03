"use client";

import { ArrowRightIcon } from "lucide-react";
import Image from "next/image";
import { useTheme } from "@/components/ThemeProvider";
import { cn } from "@/lib/utils";

interface HeroAction {
  text: string;
  href: string;
  icon?: React.ReactNode;
  variant?: "primary" | "ghost";
}

interface HeroProps {
  badge?: {
    text: string;
    action: {
      text: string;
      href: string;
    };
  };
  title: string;
  description: string;
  actions: HeroAction[];
  image?: {
    light: string;
    dark: string;
    alt: string;
  };
}

export function HeroSection({
  badge,
  title,
  description,
  actions,
  image,
}: HeroProps) {
  const { theme } = useTheme();
  const imageSrc = image ? (theme === "light" ? image.light : image.dark) : null;

  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden bg-[#0a0a0a] text-white px-4">

      {/* ── Warm amber/orange radial glow at the bottom, matching reference ── */}
      <div
        aria-hidden
        className="pointer-events-none absolute bottom-0 left-1/2 -translate-x-1/2 w-[1100px] h-[250px]"
        style={{
          background:
            "radial-gradient(ellipse 70% 60% at 50% 100%, hsla(var(--brand-foreground)/0.45) 0%, hsla(var(--brand)/0.18) 55%, transparent 100%)",
          filter: "blur(28px)",
        }}
      />

      {/* ── Content ── */}
      <div className="relative z-10 flex flex-col items-center gap-8 text-center max-w-5xl mx-auto pt-20 pb-32">

        {/* Badge */}
        {badge && (
          <div className="animate-appear inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-xs text-white/60 backdrop-blur-sm">
            <span>{badge.text}</span>
            <a
              href={badge.action.href}
              className="flex items-center gap-0.5 text-white/80 font-semibold hover:text-white transition-colors"
            >
              {badge.action.text}
              <ArrowRightIcon className="h-3 w-3" />
            </a>
          </div>
        )}

        {/* Title */}
        <h1
          className={cn(
            "animate-appear",
            "font-bold tracking-tight leading-[1.08]",
            "text-5xl sm:text-7xl md:text-8xl",
            // White-to-gray gradient exactly like reference
            "bg-gradient-to-b from-white via-white/90 to-white/50 bg-clip-text text-transparent"
          )}
        >
          {title}
        </h1>

        {/* Description */}
        <p className="animate-appear opacity-0 delay-100 max-w-[480px] text-base sm:text-lg text-white/45 leading-relaxed font-normal">
          {description}
        </p>

        {/* Actions */}
        <div className="animate-appear opacity-0 delay-300 flex items-center justify-center gap-3 flex-wrap">
          {actions.map((action, index) => {
            const isPrimary = action.variant !== "ghost";
            return (
              <a
                key={index}
                href={action.href}
                className={cn(
                  "inline-flex items-center gap-2 px-6 py-2.5 rounded-md text-sm font-semibold transition-all",
                  isPrimary
                    ? "bg-white text-black hover:bg-white/90 shadow-md"
                    : "border border-white/20 text-white/80 hover:bg-white/5 hover:text-white"
                )}
              >
                {action.icon}
                {action.text}
              </a>
            );
          })}
        </div>

        {/* Optional mockup image */}
        {image && imageSrc && (
          <div className="animate-appear opacity-0 delay-700 mt-4 w-full max-w-4xl rounded-xl overflow-hidden border border-white/10 shadow-2xl">
            <Image
              src={imageSrc}
              alt={image.alt}
              width={1248}
              height={765}
              priority
              className="w-full h-auto"
            />
          </div>
        )}
      </div>
    </section>
  );
}
