import ProtectedRoute from "@/components/auth/ProtectedRoute";

export default function ApplicationsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ProtectedRoute>{children}</ProtectedRoute>;
}

