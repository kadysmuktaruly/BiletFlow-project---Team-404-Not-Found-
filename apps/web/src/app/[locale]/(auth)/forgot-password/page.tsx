import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { ForgotPasswordForm } from "./form";

export default async function Page({ params }: PageProps<"/[locale]/forgot-password">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <ForgotPasswordForm />
    </Suspense>
  );
}
