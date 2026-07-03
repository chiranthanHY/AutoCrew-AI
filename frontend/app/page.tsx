import { HeroSection } from "@/components/ui/hero-section";
import { Icons } from "@/components/ui/icons";

export default function Home() {
  return (
    <HeroSection
      badge={{
        text: "Introducing AutoCrew AI Multi-Agent Orchestration  ·",
        action: {
          text: "Learn more",
          href: "/tasks/new",
        },
      }}
      title="Build faster with autonomous agent crews"
      description="Deploy a crew of five specialist agents—Planner, Researcher, Executor, Critic, and Verifier—to run targeted research and produce publication-ready content in minutes."
      actions={[
        {
          text: "Get Started",
          href: "/tasks/new",
          variant: "primary",
        },
        {
          text: "GitHub",
          href: "https://github.com/chiranthanHY/AutoCrew-AI",
          variant: "ghost",
          icon: <Icons.gitHub className="h-5 w-5" />,
        },
      ]}
    />
  );
}
