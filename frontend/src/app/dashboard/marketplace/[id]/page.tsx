import nextDynamic from "next/dynamic";

const PageClient = nextDynamic(() => import("./PageClient"), { ssr: false });

export function generateStaticParams() {
  return [];
}

export default function StrategyDetailPage() {
  return <PageClient />;
}
