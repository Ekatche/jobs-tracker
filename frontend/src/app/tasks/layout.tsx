import ProtectedRoute from "@/components/auth/ProtectedRoute";

export default function TasksLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ProtectedRoute>{children}</ProtectedRoute>;
}

