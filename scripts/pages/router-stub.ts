import React from "react";
export function Link(props: any) {
  const { to, children, className, ...rest } = props || {};
  return React.createElement("a", { href: typeof to === "string" ? to : "#", className, ...rest }, children);
}
export function createFileRoute(_path: string) {
  return (opts: any) => opts;
}
