import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import { ProfilePage } from "@/components/organizer/profile-page";

export default async function Page({ params }: PageProps<"/[locale]/organizer/profile">) {
  setRequestLocale((await params).locale);
  return (
    <Suspense>
      <ProfilePage />
    </Suspense>
  );
}
