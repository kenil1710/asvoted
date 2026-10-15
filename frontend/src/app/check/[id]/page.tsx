import { CheckView } from "@/components/CheckView";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CheckView id={Number(id) || 0} />;
}
