import { SecurityFeaturesContent } from "@/components/docs/sections/security-features";

export const metadata = {
  title: "Security features | Rampart docs",
  description: "Prompt injection, PII, exfiltration, and policy controls in Rampart.",
};

export default function SecurityDocPage() {
  return <SecurityFeaturesContent />;
}
