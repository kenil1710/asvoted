import { DaoView } from "@/components/DaoView";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DaoView id={Number(id) || 0} />;
}
