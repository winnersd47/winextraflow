import PageClient from "./PageClient";

export const dynamic = "force-static";

export function generateStaticParams(): Array<{ id: string }> {
  return [];
}

export default function SignalDetailPage() {
  return <PageClient />;
}
