import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { LoginForm } from "./form";

export default async function Page({ params }: PageProps<"/[locale]/login">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
