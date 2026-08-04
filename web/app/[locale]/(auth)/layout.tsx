import { LogoBlock } from "@/components/logo";
import { Card } from "@/components/ui";

export default function AuthLayout({ children }: LayoutProps<"/[locale]">) {
  return (
    <div className="app-gradient flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center">
          <LogoBlock />
        </div>
        <Card className="p-6 sm:p-8">{children}</Card>
      </div>
    </div>
  );
}
