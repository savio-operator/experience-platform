import DemoScreen from "@/components/DemoScreen";
import { questions } from "@/lib/questions";
import { options } from "@/lib/fixtures";

export function generateStaticParams() {
  return [
    ...questions.map(question => ({ step: ["questions", question.id] })),
    ...options.map(option => ({ step: ["options", option.id] })),
    ...["brief", "options", "checkout", "booking"].map(step => ({ step: [step] })),
  ];
}

export default async function Page({ params }: { params: Promise<{ step: string[] }> }) {
  const { step } = await params;
  return <DemoScreen path={step.join("/")} />;
}
