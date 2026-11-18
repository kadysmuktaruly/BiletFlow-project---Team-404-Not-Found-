import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { VerifyEmailForm } from "./form";

export default async function Page({ params }: PageProps<"/[locale]/verify-email">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <VerifyEmailForm />
    </Suspense>
  );
}
