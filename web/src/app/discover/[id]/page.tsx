import { notFound } from "next/navigation";
import Discover from "@/components/Discover";
import { discoveryEvents } from "@/lib/fixtures";

export function generateStaticParams() { return discoveryEvents.map(event => ({ id: event.id })); }

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!discoveryEvents.some(event => event.id === id)) notFound();
  return <Discover eventId={id} />;
}
