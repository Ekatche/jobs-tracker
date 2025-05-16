"use client";

import GradientBackground from "@/components/ui/GradientBackground";
import RegistrationForm from "@/components/auth/RegistrationForm";

export default function RegisterPage() {
  return (
    <GradientBackground>
      <div className="flex items-center justify-center min-h-screen p-4">
        <RegistrationForm />
      </div>
    </GradientBackground>
  );
}
