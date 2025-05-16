"use client";

import React from "react";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="h-screen overflow-hidden">{children}</div>;
}
