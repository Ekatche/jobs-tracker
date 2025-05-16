"use client";

import GradientBackground from "@/components/ui/GradientBackground";
import LoginForm from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <GradientBackground>
      <div className="flex items-center justify-center min-h-screen p-4">
        <LoginForm />
      </div>
    </GradientBackground>
  );
}
