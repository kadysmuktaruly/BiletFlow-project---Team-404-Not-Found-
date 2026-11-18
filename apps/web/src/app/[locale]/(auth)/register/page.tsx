import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { RegisterForm } from "./form";

export default async function Page({ params }: PageProps<"/[locale]/register">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  );
}
