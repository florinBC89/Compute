import { getMe } from "@/lib/api";
import Sidebar from "@/components/Sidebar";
import CreateEthicalForm from "@/components/CreateEthicalForm";

export const dynamic = "force-dynamic";

export default async function NewEthicalPage() {
  const me = await getMe();

  return (
    <div className="flex h-dvh flex-col overflow-hidden sm:flex-row">
      <Sidebar email={me.email} projects={me.projects} currentProjectId={null} />
      <div className="flex-1 overflow-y-auto bg-page">
        <div className="mx-auto max-w-[420px] px-6 py-10 sm:px-8">
          <h1 className="mb-6 text-[22px] font-semibold text-ink">New Ethical</h1>
          <CreateEthicalForm projects={me.projects} />
        </div>
      </div>
    </div>
  );
}
