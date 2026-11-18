import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { ResetPasswordForm } from "./form";

export default async function Page({ params }: PageProps<"/[locale]/reset-password">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
